from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status


@dataclass(frozen=True)
class TenantContext:
    user_id: UUID
    organization_id: UUID
    roles: frozenset[str] = frozenset()
    permissions: frozenset[str] = frozenset()
    is_organization_root: bool = False


def validate_same_organization(
    entity_org_id: UUID,
    current_org_id: UUID,
    entity_name: str = "entity",
) -> None:
    """Reject a cross-tenant entity reference at the application boundary."""
    if entity_org_id != current_org_id:
        # Keep externally observable behavior indistinguishable from a missing
        # resource. Callers must not learn that an identifier exists elsewhere.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{entity_name.capitalize()} not found.",
        )
