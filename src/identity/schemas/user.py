from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserSchema(BaseModel):
    id: int
    username: str
    email: EmailStr
    created_at: datetime
    updated_at: datetime


class CreateUserSchema(BaseModel):
    username: str
    email: str
    password_hash: str


class UpdateUserSchema(BaseModel):
    username: str | None = None
    email: EmailStr | None = None


class UpdateUserPasswordSchema(BaseModel):
    old_password: str
    new_password: str
