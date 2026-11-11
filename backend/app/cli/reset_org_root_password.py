import getpass
import sys

from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.core.password_policy import validate_password
from app.core.security import hash_password, revoke_account_sessions
from app.foundation.infrastructure.models import Organization, User


def reset_password(organization_code: str, password: str, confirmation: str) -> str | None:
    with SessionLocal() as db:
        organization = db.scalar(
            select(Organization).where(
                func.lower(Organization.code) == organization_code.strip().lower()
            )
        )
        if organization is None:
            return None
        root = db.scalar(
            select(User).where(
                User.organization_id == organization.id,
                User.is_organization_root.is_(True),
            )
        )
        if root is None:
            return None
        validate_password(password, confirmation, root.email)
        root.password_hash = hash_password(password)
        root.token_version += 1
        revoke_account_sessions(db, "tenant", root.id, reason="cli_password_reset")
        db.commit()
        return root.email


def main() -> int:
    with SessionLocal() as db:
        organizations = list(db.scalars(select(Organization).order_by(Organization.code)))
    print("Available organizations:")
    for organization in organizations:
        print(f"  [{organization.code}] {organization.name}")
    code = input("Enter organization code: ").strip()
    while True:
        password = getpass.getpass("New password: ")
        confirmation = getpass.getpass("Confirm password: ")
        try:
            email = reset_password(code, password, confirmation)
            break
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
    if email is None:
        print("Organization or Organization Root was not found.", file=sys.stderr)
        return 1
    print(f"Password reset successfully for {email}.")
    print("All previous sessions have been invalidated.")
    print("The user must log in with the new password.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
