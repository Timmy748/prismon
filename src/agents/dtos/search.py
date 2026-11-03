from dataclasses import dataclass
from typing import Literal

ResourceType = Literal['document', 'asset']


@dataclass(frozen=True, slots=True)
class HybridSearchCandidate:
    resource_type: ResourceType
    resource_id: int
    rank: int
    rrf_score: float
    bm25_rank: int | None = None
    dense_rank: int | None = None
