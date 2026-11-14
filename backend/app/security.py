from datetime import datetime, timedelta, timezone
import jwt
import hashlib
import hmac
import os
import base64
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from app.config import SECRET_KEY
from app.database import get_db
from app.models import User

bearer = HTTPBearer(auto_error=False)

def hash_password(value: str) -> str:
    if len(value.encode("utf8")) > 72:
        raise ValueError("Password must be at most 72 UTF-8 bytes")
    salt = os.urandom(16)
    digest = hashlib.scrypt(value.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return "scrypt$16384$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()

def verify_password(value: str, stored: str) -> bool:
    try:
        scheme, cost, salt_b64, digest_b64 = stored.split("$")
        if scheme != "scrypt" or cost != "16384":
            return False
        salt = base64.b64decode(salt_b64, validate=True)
        digest = base64.b64decode(digest_b64, validate=True)
        proposed = hashlib.scrypt(value.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(digest, proposed)
    except (ValueError, TypeError):
        return False

def token_for(user_id: str) -> str:
    return jwt.encode({"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(days=7)}, SECRET_KEY, algorithm="HS256")

def decode_token(token: str) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        subject = payload.get("sub")
        if not isinstance(subject, str) or not subject:
            raise ValueError("Missing subject")
        return subject
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user = db.get(User, decode_token(credentials.credentials))
    if not user:
        raise HTTPException(status_code=401, detail="Account not found")
    return user
