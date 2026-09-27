import argparse
import getpass
import sys
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.security import hash_password, normalize_email, revoke_account_sessions
from app.core.password_policy import validate_password
from app.platform.infrastructure.models import PlatformAccount


def reset_password(email: str, password: str, confirmation: str | None = None) -> bool:
    with SessionLocal() as db:
        account = db.scalar(
            select(PlatformAccount).where(
                PlatformAccount.email == normalize_email(email),
                PlatformAccount.is_root.is_(True),
            )
        )
        if account is None:
            return False
        validate_password(password, confirmation if confirmation is not None else password, account.email, 12)
        account.password_hash = hash_password(password)
        account.password_changed_at = datetime.now(timezone.utc)
        account.token_version += 1
        revoke_account_sessions(db, "platform", account.id, reason="cli_password_reset")
        db.commit()
        return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    password = getpass.getpass("New password: ")
    confirmation = getpass.getpass("Confirm password: ")
    try:
        reset = reset_password(args.email, password, confirmation)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not reset:
        print("Platform Root account was not found.", file=sys.stderr)
        return 1
    print("Platform Root password reset successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
