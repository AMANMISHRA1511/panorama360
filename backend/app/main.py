import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from app.config import CORS_ORIGINS, SECRET_KEY
from app.database import Base, SessionLocal, engine
from app.models import Job, User
from app.security import decode_token
from app.redis_queue import get_progress
from app.ml.inference import weights_state
from app.routers import auth, jobs, assets

log = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    if SECRET_KEY == "dev-only-insecure-change-before-deploy":
        log.warning("Development SECRET_KEY in use. Change for any network-exposed deployment!")
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(title="Panorama 360 API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True,
                   allow_methods=["GET", "POST", "DELETE", "OPTIONS"], allow_headers=["Authorization", "Content-Type"])
app.include_router(auth.router)
app.include_router(jobs.router)
app.include_router(assets.router)

@app.get("/health")
def health():
    return {"status": "ok", "ai": weights_state()}

@app.websocket("/ws/progress/{job_id}")
async def websocket_progress(websocket: WebSocket, job_id: str, token: str = ""):
    try:
        user_id = decode_token(token)
    except HTTPException:
        await websocket.close(code=1008, reason="Unauthorized")
        return
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if not job or job.user_id != user_id:
            await websocket.close(code=1008, reason="Job not found")
            return
    await websocket.accept()
    try:
        for _ in range(1500):  # max ~10 minutes; client can reconnect
            data = get_progress(job_id)
            if not data:
                with SessionLocal() as db:
                    job = db.get(Job, job_id)
                    if not job or job.user_id != user_id:
                        break
                    data = {"job_id": job.id, "status": job.status, "progress": job.progress,
                            "stage": job.stage, "error": job.error}
            await websocket.send_json(data)
            if data["status"] in ("done", "failed"):
                break
            await asyncio.sleep(.4)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        try:
            await websocket.close()
        except RuntimeError:
            pass
