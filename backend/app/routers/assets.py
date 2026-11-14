from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.config import STORAGE_DIR
from app.database import get_db
from app.models import Job, User
from app.routers.jobs import owned_job
from app.security import current_user

router = APIRouter(tags=["Assets and sharing"])

def send_file(job: Job, kind: str):
    if kind not in ("original", "output"):
        raise HTTPException(422, "kind must be original or output")
    filename = job.original_name if kind == "original" else job.output_name
    if not filename:
        raise HTTPException(404, "Asset is not ready")
    path = STORAGE_DIR / job.id / filename
    if path.name != filename or not path.is_file():
        raise HTTPException(404, "Asset not found")
    mime = ("video/mp4" if filename.endswith(".mp4") else
            "image/png" if filename.endswith(".png") else
            "image/webp" if filename.endswith(".webp") else "image/jpeg")
    return FileResponse(path, media_type=mime, filename=filename, content_disposition_type="inline")

@router.get("/assets/{job_id}")
def private_asset(job_id: str, kind: str = Query("output"), db: Session = Depends(get_db),
                  user: User = Depends(current_user)):
    return send_file(owned_job(db, user, job_id), kind)

@router.get("/share/{token}")
def public_share(token: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.share_token == token).first()
    if not job or job.status != "done":
        raise HTTPException(404, "Shared panorama not available")
    return {"id": job.id, "title": job.title, "status": job.status, "mime": job.mime,
            "created_at": job.created_at, "asset_url": f"/share/{token}/asset"}

@router.get("/share/{token}/asset")
def public_asset(token: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.share_token == token).first()
    if not job or job.status != "done":
        raise HTTPException(404, "Shared panorama not available")
    return send_file(job, "output")
