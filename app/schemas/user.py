from pydantic import BaseModel


class CreateUserRequest(BaseModel):
    username: str
    email: str
    password: str


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