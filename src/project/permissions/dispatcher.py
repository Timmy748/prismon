from typing import Any

from project.dtos.member import MemberDTO
from project.permissions.api_key_policies import API_KEY_POLICIES
from project.permissions.asset_policies import ASSET_POLICIES
from project.permissions.authorization import (
    ResourceActions,
    ResourcePermissionVerify,
)
from project.permissions.document_policies import DOCUMENT_POLICIES
from project.permissions.dtos import (
    ApiKeyPermissionDTO,
    AssetPermissionDTO,
    DocumentPermissionDTO,
    MemberPermissionDTO,
    ProjectPermissionDTO,
    TagPermissionDTO,
)
from project.permissions.member_policies import MEMBER_POLICIES
from project.permissions.project_policies import PROJECT_POLICIES
from project.permissions.tag_policies import TAG_POLICIES

RESOURCE_POLICIES: dict[type[object], ResourcePermissionVerify[Any, Any]] = {
    ProjectPermissionDTO: PROJECT_POLICIES,
    MemberPermissionDTO: MEMBER_POLICIES,
    DocumentPermissionDTO: DOCUMENT_POLICIES,
    AssetPermissionDTO: ASSET_POLICIES,
    TagPermissionDTO: TAG_POLICIES,
    ApiKeyPermissionDTO: API_KEY_POLICIES,
}


def verify_resource_permission(
    member: MemberDTO,
    resource: object,
    action: ResourceActions,
    **context: object,
) -> bool:
    policies = RESOURCE_POLICIES.get(type(resource))
    if policies is None:
        return False
    return policies.verify(member, resource, action, **context)
