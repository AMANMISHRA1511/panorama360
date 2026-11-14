from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.schemas import AuthData
from app.security import hash_password, verify_password, token_for

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/signup", status_code=201)
def signup(data: AuthData, db: Session = Depends(get_db)):
    email = data.email.lower().strip()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Email already registered")
    user = User(email=email, password_hash=hash_password(data.password))
    db.add(user)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(409, "Could not register that email")
    return {"access_token": token_for(user.id), "token_type": "bearer", "user": {"id": user.id, "email": user.email}}

@router.post("/login")
def login(data: AuthData, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email.lower().strip()))
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    return {"access_token": token_for(user.id), "token_type": "bearer", "user": {"id": user.id, "email": user.email}}
