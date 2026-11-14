import json
import logging
import subprocess
import time
from pathlib import Path
import cv2
from sqlalchemy import select
from app.config import STORAGE_DIR
from app.database import Base, SessionLocal, engine
from app.models import Job
from app.redis_queue import QUEUE_KEY, client, store_progress
from app.services.ai_controls import apply_optional_ai
from app.services.photo_sphere_xmp import add_photo_sphere_xmp
from app.services.stitch import read_image, stitch_images, to_panorama, wrap_seam, is_equirectangular, show_missing_as_blank

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

STAGES = [(8, "Features"), (22, "Matching"), (40, "Warping"), (58, "Blending"), (76, "AI fill"), (90, "Enhance")]

def update(job, db, progress, stage, status="processing"):
    job.progress, job.stage, job.status = progress, stage, status
    db.commit()
    try:
        store_progress(job.id, {"job_id": job.id, "progress": progress, "stage": stage, "status": status, "error": job.error})
    except Exception as exc:
        log.warning("Could not update Redis progress: %s", exc)


def convert_video(job, db, path, fov):
    """Converts the first 240 frames to equirectangular video; ffmpeg encodes H.264 MP4."""
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError("Could not open input video")
    fps_input = capture.get(cv2.CAP_PROP_FPS) or 24
    skip = max(1, round(fps_input / 18))
    fps_out = max(1, min(30, fps_input / skip))
    dirname = STORAGE_DIR / job.id
    intermediate = dirname / "intermediate.mp4"
    output = dirname / "panorama.mp4"
    writer = cv2.VideoWriter(str(intermediate), cv2.VideoWriter_fourcc(*"mp4v"), fps_out, (1024, 512))
    if not writer.isOpened():
        capture.release()
        raise RuntimeError("Video writer could not initialize")
    frame_num = processed = 0
    try:
        while processed < 240:
            ok, frame = capture.read()
            if not ok:
                break
            if frame_num % skip == 0:
                # A moving ordinary video is not a 360 video. Do not
                # fabricate missing directions by stretching each frame.
                if not is_equirectangular(frame):
                    raise ValueError(
                        "360 video conversion requires actual 2:1 "
                        "equirectangular source frames; ordinary video "
                        "does not record the directions behind the camera."
                    )
                panorama, mask = to_panorama(frame, (1024, 512), fov)
                writer.write(wrap_seam(panorama, 12))
                processed += 1
                if processed % 16 == 0:
                    update(job, db, min(89, 10 + processed // 3), f"Encoding frame {processed}")
            frame_num += 1
    finally:
        capture.release()
        writer.release()
    if processed == 0:
        raise ValueError("Video has no decodable frames")
    update(job, db, 94, "H.264 encoding")
    try:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(intermediate),
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart", str(output)], check=True, timeout=180)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("ffmpeg with libx264 must be installed to create browser-compatible MP4") from exc
    finally:
        intermediate.unlink(missing_ok=True)
    return output.name, "video/mp4"


def process(job_id: str):
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if not job or job.status != "queued":
            return
        update(job, db, 2, "Reading uploads")
        try:
            info = json.loads(job.input_names)
            fov = float(info.get("fov", 90))
            ai_enabled = bool(info.get("ai_enabled", False))
            ai_strength = float(info.get("ai_strength", 0.12))
            ai_fill_small_gaps = bool(info.get("ai_fill_small_gaps", False))
            paths = [STORAGE_DIR / job.id / filename for filename in info["files"]]
            if job.mode == "video":
                filename, mime = convert_video(job, db, paths[0], fov)
            else:
                update(job, db, 8, "Features")
                images = [read_image(str(p)) for p in paths]
                update(job, db, 22, "Matching")
                if job.mode == "multi":
                    # Stitching can take minutes for many photos. Report actual
                    # feature matching, overlap checks, warping and blending.
                    # Avoid DB/Redis writes for every one of hundreds of pairs.
                    last_report_time = time.monotonic()
                    last_stage_label = ""

                    def stitching_progress(stage, done, total):
                        nonlocal last_report_time, last_stage_label
                        ranges = {
                            "Matching consecutive photos": (23, 29),
                            "Detecting image features": (30, 33),
                            "Checking photo overlaps": (34, 44),
                            "Projecting photos": (45, 57),
                            "Blending photographs": (58, 68),
                        }
                        low, high = ranges.get(stage, (22, 22))
                        percent = min(high, low + int((high - low) * done / max(total, 1)))
                        # Do not make the percentage move backward on fallback.
                        percent = max(int(job.progress), percent)
                        now = time.monotonic()
                        # Progress must reflect work, but a large input set must
                        # not make hundreds of MySQL commits per second.
                        if (now - last_report_time < 1.0 and
                            percent < int(job.progress) + 2 and
                            not (done == total and stage != last_stage_label)):
                            return
                        update(job, db, percent, f"{stage} ({done}/{total})")
                        last_report_time = now
                        last_stage_label = stage

                    panorama, coverage = stitch_images(
                        images, fov=fov, progress_callback=stitching_progress
                    )
                else:
                    update(job, db, 40, "Warping")
                    panorama, coverage = to_panorama(images[0], fov=fov)
                update(job, db, 70 if job.mode == "multi" else 58, "Blending finished")
                if job.mode == "enhance":
                    # No holes expected in valid equirectangular enhancement inputs.
                    if (coverage == 0).any():
                        raise ValueError("Enhance-only requires a 2:1 equirectangular panorama")
                photographed_fraction = float((coverage > 0).mean())
                is_partial = (job.mode != "enhance" and photographed_fraction < 0.999)
                update(job, db, 76, "Optional AI enhancement" if ai_enabled else "Preserving original pixels")
                # AI is OFF by default. Even when enabled, apply it gently only
                # to actual photographed pixels; never invent entire views.
                processed, display_coverage, method = apply_optional_ai(
                    panorama, coverage,
                    enabled=ai_enabled,
                    strength=ai_strength,
                    fill_small_gaps=ai_fill_small_gaps,
                )
                log.info("job=%s optional_processing=%s", job.id, method)
                update(job, db, 90, "Preparing output")
                if is_partial:
                    enhanced = show_missing_as_blank(processed, display_coverage)
                    mask_path = STORAGE_DIR / job.id / "coverage-mask.png"
                    cv2.imwrite(str(mask_path), (coverage > 0).astype("uint8") * 255)
                else:
                    enhanced = wrap_seam(processed)
                output = STORAGE_DIR / job.id / "panorama.jpg"
                to_save = enhanced
                if not cv2.imwrite(str(output), to_save, [cv2.IMWRITE_JPEG_QUALITY, 93]):
                    raise RuntimeError("Failed to write output image")
                # An XMP-tagged photo sphere is only valid when virtually every
                # direction is mapped to real imagery, not interpolated stripes.
                if not is_partial:
                    add_photo_sphere_xmp(output, enhanced.shape[1], enhanced.shape[0])
                filename, mime = output.name, "image/jpeg"
            job.output_name, job.mime, job.error = filename, mime, None
            if job.mode != "video" and job.mode != "enhance" and is_partial:
                update(job, db, 100,
                       f"Partial panorama ({round(photographed_fraction * 100)}% photographed)",
                       status="done")
            else:
                update(job, db, 100, "Complete", status="done")
        except Exception as exc:
            log.exception("Job %s failed", job_id)
            job.error = str(exc)[:1000]
            update(job, db, job.progress, "Failed", status="failed")


def run_worker():
    Base.metadata.create_all(engine)
    redis = client()
    log.info("Ready: listening on %s", QUEUE_KEY)
    while True:
        try:
            payload = redis.blpop(QUEUE_KEY, timeout=5)
            if payload:
                process(payload[1])
        except Exception:
            log.exception("Worker error; retrying")
            time.sleep(3)

if __name__ == "__main__":
    run_worker()
