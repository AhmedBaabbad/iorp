"""Who is who in an organization (PROJECT-NOTIFY-001), answered by foundation (users, roles, delegations) for modules that
must reach people without reading foundation's tables: the active users, the holders of a permission, a role's members,
and names."""
from typing import Protocol
from uuid import UUID


class UserDirectoryInterface(Protocol):
    def active_users(self, db, organization_id: UUID) -> set[UUID]: ...

    def holders(self, db, organization_id: UUID, permission: str) -> set[UUID]:
        """Active users holding it through a role, as the organization's root, or by a delegation in force."""
        ...

    def role_members(self, db, organization_id: UUID, role_id: UUID) -> set[UUID]: ...

    def roles(self, db, organization_id: UUID) -> list[dict]:
        """[{id, code, name}] of the organization's roles."""
        ...

    def names(self, db, organization_id: UUID, user_ids) -> dict[UUID, str]: ...


class _NoDirectory:
    def active_users(self, db, organization_id):
        return set()

    def holders(self, db, organization_id, permission):
        return set()

    def role_members(self, db, organization_id, role_id):
        return set()

    def roles(self, db, organization_id):
        return []

    def names(self, db, organization_id, user_ids):
        return {}


_provider: UserDirectoryInterface = _NoDirectory()


def register_user_directory(provider: UserDirectoryInterface) -> None:
    global _provider
    _provider = provider


def directory() -> UserDirectoryInterface:
    return _provider
