"""Generic contracts for reusable workflow nodes."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class TextInput:
    text: str


class WorkflowNode[T, R](Protocol):
    async def run(self, input: T) -> R: ...
