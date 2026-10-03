from dataclasses import dataclass
from datetime import datetime

from project.entities.asset import AssetStatus


@dataclass(frozen=True, slots=True)
class AssetDTO:
    id: int
    project_id: int
    file: str
    type: str
    description: str | None
    status: AssetStatus
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class CreateAssetDTO:
    file: str
    asset: str
    type: str
    name: str
    description: str


@dataclass(frozen=True, slots=True)
class UpdateAssetDTO:
    file: str | None = None
    type: str | None = None
    name: str | None = None
    description: str | None = None


@dataclass(frozen=True, slots=True)
class ApproveAssetDTO:
    accept: bool
