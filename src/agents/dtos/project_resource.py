from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EmbeddingSourceDTO:
    name: str
    description: str | None
