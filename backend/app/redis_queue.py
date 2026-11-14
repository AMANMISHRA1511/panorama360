import json
from app.config import REDIS_URL

QUEUE_KEY = "p360:queue"

def client():
    import redis
    return redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=5)

def enqueue(job_id: str):
    client().rpush(QUEUE_KEY, job_id)

def store_progress(job_id: str, data: dict):
    client().setex(f"p360:progress:{job_id}", 86400, json.dumps(data))

def get_progress(job_id: str):
    try:
        value = client().get(f"p360:progress:{job_id}")
        return json.loads(value) if value else None
    except Exception:
        return None
