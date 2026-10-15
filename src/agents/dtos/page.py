from dataclasses import dataclass
from datetime import datetime
from typing import Generic, TypeVar

T = TypeVar('T')


@dataclass(frozen=True, slots=True)
class CursorPage(Generic[T]):
    items: list[T]
    pagination: 'PaginationDTO'


@dataclass(frozen=True, slots=True)
class PaginationDTO:
    cursor: tuple[datetime, int] | None = None
    limit: int = 50
    more: bool = False
