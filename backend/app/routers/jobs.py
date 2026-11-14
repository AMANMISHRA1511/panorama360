import json
import secrets
from pathlib import Path
from uuid import uuid4
import cv2
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.config import STORAGE_DIR, MAX_FILE_BYTES, MAX_VIDEO_BYTES, PUBLIC_BASE_URL
from app.database import get_db
from app.models import Job, User
from app.redis_queue import enqueue
from app.schemas import JobData
from app.security import current_user

router = APIRouter(tags=["Conversions"])
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".avi"}


def serialize(job: Job) -> dict:
    return dict(id=job.id, title=job.title, mode=job.mode, status=job.status,
                progress=job.progress, stage=job.stage, error=job.error, mime=job.mime,
                created_at=job.created_at, asset_url=f"/assets/{job.id}?kind=output" if job.output_name else None,
                original_url=f"/assets/{job.id}?kind=original" if job.original_name else None,
                share_url=f"{PUBLIC_BASE_URL}/s/{job.share_token}")


def owned_job(db, user, job_id):
    job = db.get(Job, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(404, "Project not found")
    return job


async def write_upload(upload: UploadFile, directory: Path, video=False):
    extension = Path(upload.filename or "").suffix.lower()
    allowed = VIDEO_EXTENSIONS if video else IMAGE_EXTENSIONS
    if extension not in allowed:
        raise HTTPException(422, "Unsupported file type. Use " + ", ".join(sorted(allowed)))
    destination = directory / f"{uuid4().hex}{extension}"
    total = 0
    limit = MAX_VIDEO_BYTES if video else MAX_FILE_BYTES
    try:
        with destination.open("wb") as f:
            while chunk := await upload.read(1024 * 1024):
                total += len(chunk)
                if total > limit:
                    raise HTTPException(413, f"File exceeds {limit // (1024*1024)} MB limit")
                f.write(chunk)
        if total == 0:
            raise HTTPException(422, "Empty files cannot be processed")
        if video:
            capture = cv2.VideoCapture(str(destination))
            valid, _ = capture.read()
            capture.release()
            if not valid:
                raise HTTPException(422, "Cannot decode video; try an H.264 MP4")
        elif cv2.imread(str(destination)) is None:
            raise HTTPException(422, "Cannot decode image file")
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()
    return destination.name


async def submit(mode: str, files: list[UploadFile], db: Session, user: User, title: str, fov: float,
                 ai_enabled: bool = False, ai_strength: float = 0.12, ai_fill_small_gaps: bool = False):
    if not 0 <= ai_strength <= 0.25:
        raise HTTPException(422, "AI intensity must be between 0 and 0.25")
    if not 20 <= fov <= 160:
        raise HTTPException(422, "Field of view must be 20–160°")
    if mode == "multi" and not 2 <= len(files) <= 32:
        raise HTTPException(422, "Choose 2–32 overlapping photos")
    if mode != "multi" and len(files) != 1:
        raise HTTPException(422, "Choose one file")
    job = Job(id=str(uuid4()), user_id=user.id, mode=mode, title=(title.strip() or "Untitled panorama")[:200],
              share_token=secrets.token_urlsafe(24), stage="Queued")
    directory = STORAGE_DIR / job.id
    directory.mkdir(parents=True, exist_ok=True)
    uploaded_names = []
    try:
        for file in files:
            uploaded_names.append(await write_upload(file, directory, video=(mode == "video")))
        job.input_names = json.dumps({"files": uploaded_names, "fov": fov,
                                      "ai_enabled": ai_enabled, "ai_strength": ai_strength,
                                      "ai_fill_small_gaps": ai_fill_small_gaps})
        job.original_name = uploaded_names[0]
        db.add(job)
        db.commit()
        try:
            enqueue(job.id)
        except Exception:
            job.status, job.stage, job.error = "failed", "Queue unavailable", "Redis worker queue is unavailable"
            db.commit()
            raise HTTPException(503, "Redis queue is unavailable. Start Redis and the worker.")
    except Exception:
        if not job.id or job.status != "failed":
            for p in directory.iterdir():
                p.unlink(missing_ok=True)
            directory.rmdir()
        raise
    return serialize(job)


@router.post("/convert/single", response_model=JobData, status_code=202)
async def single(file: UploadFile = File(...), title: str = Form("New panorama"), fov: float = Form(90),
                 ai_enabled: bool = Form(False), ai_strength: float = Form(0.12),
                 ai_fill_small_gaps: bool = Form(False), db: Session = Depends(get_db), user: User = Depends(current_user)):
    return await submit("single", [file], db, user, title, fov, ai_enabled, ai_strength, ai_fill_small_gaps)

@router.post("/convert/multi", response_model=JobData, status_code=202)
async def multi(files: list[UploadFile] = File(...), title: str = Form("Stitched panorama"), fov: float = Form(90),
                ai_enabled: bool = Form(False), ai_strength: float = Form(0.12),
                ai_fill_small_gaps: bool = Form(False), db: Session = Depends(get_db), user: User = Depends(current_user)):
    return await submit("multi", files, db, user, title, fov, ai_enabled, ai_strength, ai_fill_small_gaps)

@router.post("/convert/video", response_model=JobData, status_code=202)
async def video(file: UploadFile = File(...), title: str = Form("360 video"), fov: float = Form(90),
                db: Session = Depends(get_db), user: User = Depends(current_user)):
    return await submit("video", [file], db, user, title, fov)

@router.post("/enhance", response_model=JobData, status_code=202)
async def enhance(file: UploadFile = File(...), title: str = Form("Enhanced panorama"),
                  ai_enabled: bool = Form(False), ai_strength: float = Form(0.12),
                  ai_fill_small_gaps: bool = Form(False), db: Session = Depends(get_db), user: User = Depends(current_user)):
    return await submit("enhance", [file], db, user, title, 90, ai_enabled, ai_strength, ai_fill_small_gaps)

@router.post("/generate/missing-angles", response_model=JobData, status_code=202)
async def missing_angles(files: list[UploadFile] = File(...), title: str = Form("Filled panorama"), fov: float = Form(90),
                         ai_enabled: bool = Form(False), ai_strength: float = Form(0.12),
                         ai_fill_small_gaps: bool = Form(False), db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not 1 <= len(files) <= 32:
        raise HTTPException(422, "Choose 1–32 photos")
    if len(files) == 1:
        return await submit("fill", files, db, user, title, fov, ai_enabled, ai_strength, ai_fill_small_gaps)
    return await submit("multi", files, db, user, title, fov, ai_enabled, ai_strength, ai_fill_small_gaps)

@router.get("/result/{job_id}", response_model=JobData)
def result(job_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return serialize(owned_job(db, user, job_id))

@router.get("/gallery", response_model=list[JobData])
def gallery(db: Session = Depends(get_db), user: User = Depends(current_user)):
    jobs = db.scalars(select(Job).where(Job.user_id == user.id).order_by(Job.created_at.desc()).limit(200)).all()
    return [serialize(j) for j in jobs]

@router.delete("/gallery/{job_id}")
def delete(job_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    job = owned_job(db, user, job_id)
    if job.status == "processing":
        raise HTTPException(409, "Cannot delete while processing")
    directory = STORAGE_DIR / job.id
    if directory.exists():
        for path in directory.iterdir():
            if path.is_file():
                path.unlink(missing_ok=True)
        directory.rmdir()
    db.delete(job)
    db.commit()
    return {"deleted": True}
