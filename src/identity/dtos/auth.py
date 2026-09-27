from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LoginDTO:
    email: str
    password: str


@dataclass(frozen=True, slots=True)
class AuthenticationDTO:
    access_token: str
    refresh_token: str
