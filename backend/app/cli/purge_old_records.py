"""Removes what is no longer worth keeping (run daily):
    python -m app.cli.purge_old_records
- read notifications older than 90 days (an announcement's are kept with it);
- routine security entries (sign-ins) older than 90 days, other security entries older than a year;
- the activity log's months past 12 months: their holders are told, reminded, and the months deleted 30 days later if
  nobody archived them (activity_archive.py).
The audit trail is never purged.
"""
from app.core.db import SessionLocal
import app.main  # noqa: F401  (every table and provider registered)
from app.foundation.application.activity_archive import run_daily as activity_archive
from app.foundation.application.security_log import purge as purge_security
from app.notifications.application.service import purge as purge_notifications


def main() -> int:
    with SessionLocal() as db:
        print(f"notifications removed: {purge_notifications(db)}")
        print(f"security log entries removed: {purge_security(db)}")
        print(f"activity log months: {activity_archive(db)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
