from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UserDTO:
    id: int
    username: str
    email: str
