from enum import Enum
from typing import Protocol, Self

from project.dtos.member import MemberDTO


class ResourceActions(str, Enum):
    """Base class for resource-specific action enums."""


class PolicyDecision(str, Enum):
    ALLOW = 'allow'
    DENY = 'deny'
    NOT_APPLICABLE = 'not_applicable'


class ResourcePolicy[TResource](Protocol):
    def __call__(
        self,
        member: MemberDTO,
        resource: TResource,
        **context: object,
    ) -> PolicyDecision: ...


class ResourcePermissionVerify[TResource, TAction: ResourceActions](Protocol):
    def verify(
        self,
        member: MemberDTO,
        resource: TResource,
        action: TAction,
        **context: object,
    ) -> bool: ...


class ResourcePolicies[TResource, TAction: ResourceActions]:
    """Register and evaluate policies for actions on one resource DTO."""

    def __init__(self) -> None:
        self._policies: dict[
            tuple[type[TAction], TAction], list[ResourcePolicy[TResource]]
        ] = {}

    def register(
        self,
        action: TAction,
        policy: ResourcePolicy[TResource],
    ) -> Self:
        self._policies.setdefault((type(action), action), []).append(policy)
        return self

    def verify(
        self,
        member: MemberDTO,
        resource: TResource,
        action: TAction,
        **context: object,
    ) -> bool:
        policies = self._policies.get((type(action), action))
        if not policies:
            return False

        decisions = [policy(member, resource, **context) for policy in policies]
        if PolicyDecision.DENY in decisions:
            return False
        return PolicyDecision.ALLOW in decisions
