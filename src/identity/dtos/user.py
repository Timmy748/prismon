from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class UserDTO:
    id: int
    username: str
    email: str
    password_hash: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class CreateUserDTO:
    username: str
    email: str
    password_hash: str


@dataclass(frozen=True, slots=True)
class UpdateUserDTO:
    username: str | None = None
    email: str | None = None


@dataclass(frozen=True, slots=True)
class UpdateUserPasswordDTO:
    old_password: str
    new_password: str
