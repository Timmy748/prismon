from dataclasses import dataclass, field
from datetime import datetime

from project.dtos.tag import TagDTO
from project.entities.asset import AssetStatus


@dataclass(frozen=True, slots=True)
class AssetDTO:
    id: int
    project_id: int
    created_by_member_id: int
    file: str | None
    type: str
    description: str | None
    status: AssetStatus
    created_at: datetime
    updated_at: datetime
    tags: list[TagDTO] = field(default_factory=list)
    name: str = ''
    file_extension: str | None = None
    content_type: str | None = None


@dataclass(frozen=True, slots=True)
class CreateAssetDTO:
    file: str
    asset: str
    type: str
    name: str
    description: str


@dataclass(frozen=True, slots=True)
class StartAssetUploadDTO:
    type: str
    name: str
    description: str = ''
    content_type: str = 'application/octet-stream'
    original_filename: str | None = None


@dataclass(frozen=True, slots=True)
class AssetUploadDTO:
    asset: AssetDTO
    upload_url: str
    expires_at: datetime
    required_headers: dict[str, str]


@dataclass(frozen=True, slots=True)
class AssetUploadCompletionDTO:
    asset_id: int | None
    obsolete_file_key: str | None
    already_completed: bool
    ignored: bool = False


@dataclass(frozen=True, slots=True)
class UpdateAssetDTO:
    file: str | None = None
    type: str | None = None
    name: str | None = None
    description: str | None = None


@dataclass(frozen=True, slots=True)
class ApproveAssetDTO:
    accept: bool
