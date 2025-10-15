from pydantic import BaseModel, ConfigDict
from typing import Optional


class CreateUserRequest(BaseModel):
    username: str
    email: str
    password: str
    full_name: Optional[str] = None


class GoogleUser(BaseModel):
    sub: str
    email: str
    name: str
    picture: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str] = None
    is_active: bool
    
    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    user: UserResponse