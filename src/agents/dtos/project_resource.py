from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EmbeddingSourceDTO:
    name: str
    description: str | None
    project_id: int
    status: str
