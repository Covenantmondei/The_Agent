from pydantic import BaseModel
from typing import Optional


class CreateUserRequest(BaseModel):
    username: str
    email: str
    password: str
    full_name: Optional[str] = None


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class GoogleUser(BaseModel):
    sub: str
    email: str
    name: str
    picture: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserResponse(CreateUserRequest):
    id: int
    is_active: bool

    class Config:
        orm_mode = True