from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class UploadIntentDTO:
    id: int
    project_id: int
    asset_id: int | None
    document_id: int | None
    object_key: str
    final_file_key: str
    started_by_member_id: int
    target_status: str
    expires_at: datetime
    previous_file_key: str | None
    created_at: datetime
    file_extension: str | None = None
    content_type: str = 'application/octet-stream'
