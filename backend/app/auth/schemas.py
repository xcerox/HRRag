from pydantic import BaseModel, EmailStr
import datetime


class LoginRequest(BaseModel):
    email: EmailStr


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    email: str
    created_at: datetime.datetime
    last_login: datetime.datetime
