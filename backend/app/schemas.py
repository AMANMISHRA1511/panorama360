from pydantic import BaseModel, EmailStr, Field
from datetime import datetime

class AuthData(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)

class JobData(BaseModel):
    id: str
    title: str
    mode: str
    status: str
    progress: int
    stage: str
    error: str | None
    mime: str | None
    created_at: datetime
    asset_url: str | None
    original_url: str | None
    share_url: str

class ShareData(BaseModel):
    id: str
    title: str
    status: str
    mime: str | None
    asset_url: str | None
    created_at: datetime
