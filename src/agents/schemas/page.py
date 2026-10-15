from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar('T')


class PageSchema(BaseModel, Generic[T]):
    items: list[T]
    limit: int
    more: bool
    cursor: str | None
