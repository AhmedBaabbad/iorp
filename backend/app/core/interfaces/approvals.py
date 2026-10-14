"""Sign-offs (PROJECT-GOV-004): what a module calls when a person signs an approval step, and what a document reads back.

Foundation keeps the record (who held the authority, who signed, under which delegation); a module never writes it
directly nor reads foundation's models. The signer is always the session's user; nothing sent by a screen names them.
"""
from typing import Protocol
from uuid import UUID


class ApprovalAuthorityError(PermissionError):
    """The session's user holds the approval neither through a role nor by a delegation in force (answered 403)."""


class ApprovalsInterface(Protocol):
    def record(self, db, tenant, resource_type: str, resource_id: UUID, step: str, permission_code: str, notes: str | None = None) -> dict: ...

    def signatures(self, db, organization_id: UUID, resource_type: str, resource_ids: list[UUID]) -> dict[UUID, list[dict]]: ...


class _NoApprovals:
    def record(self, *args, **kwargs) -> dict:
        return {}

    def signatures(self, db, organization_id, resource_type, resource_ids):
        return {i: [] for i in resource_ids}


_provider: ApprovalsInterface = _NoApprovals()
# resource type -> (its read permission, can(db, tenant, id) -> bool): each module registers its own visibility rule.
_visibility: dict[str, tuple[str, object]] = {}


def register_visibility(resource_type: str, read_permission: str, visible) -> None:
    """A module declares who may read a document's signatures: the read permission, and its own visibility rule (an
    organization check, or e.g. a sales representative's own customers)."""
    _visibility[resource_type] = (read_permission, visible)


def visible(db, tenant, resource_type, resource_id) -> bool:
    found = _visibility.get(resource_type)
    if found is None:
        return False
    permission, rule = found
    if not (tenant.is_organization_root or permission in (tenant.permissions or ())):
        return False
    return bool(rule(db, tenant, resource_id))


def in_organization(table_name: str):
    """A visibility rule for documents readable across the organization: the row exists in the user's organization."""
    def rule(db, tenant, resource_id):
        from sqlalchemy import select
        from app.core.db import Base
        table = Base.metadata.tables[table_name]
        return db.scalar(select(table.c.id).where(table.c.id == resource_id, table.c.organization_id == tenant.organization_id)) is not None
    return rule


def register_approvals(provider: ApprovalsInterface) -> None:
    global _provider
    _provider = provider


def record(db, tenant, resource_type, resource_id, step, permission_code, notes=None) -> dict:
    """Records the step signed now by the session's user: directly, or under a delegation in force (in the same
    transaction as the decision). Raises PermissionError if the user holds neither."""
    return _provider.record(db, tenant, resource_type, resource_id, step, permission_code, notes)


def signatures(db, organization_id, resource_type, resource_ids) -> dict:
    """{resource id: [{step, authority_name, signer_name, delegated, signed_at}, …]} oldest first."""
    return _provider.signatures(db, organization_id, resource_type, list(resource_ids))


def sign(db, tenant, resource_type, resource_id, step, permission_code, notes=None) -> dict:
    """record(), for a decision about to be committed: raises ApprovalAuthorityError (403) when there is no authority."""
    try:
        return record(db, tenant, resource_type, resource_id, step, permission_code, notes)
    except ApprovalAuthorityError:
        db.rollback()
        raise


def signed_name(signed: dict | None, fallback: str | None, lang: str) -> str:
    """How a document names who signed: "Mohammed — on behalf of Ahmed" under a delegation, else the person."""
    if signed and signed.get("delegated"):
        return (f"{signed['signer_name']} — بالتفويض عن {signed['authority_name']}" if lang == "ar"
                else f"{signed['signer_name']} — on behalf of {signed['authority_name']}")
    return (signed or {}).get("signer_name") or fallback or ""


def latest(signed: list[dict], step: str) -> dict | None:
    found = [s for s in signed if s["step"] == step]
    return found[-1] if found else None
