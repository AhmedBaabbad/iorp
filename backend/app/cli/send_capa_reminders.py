"""Daily corrective-action digest (QUAL-CAPA-001): one email per person with actions late or due soon, reports past their
due date, or effectiveness reviews due. Run once a day by the server's scheduler:

    python -m app.cli.send_capa_reminders
"""
import sys

from sqlalchemy import select

from app.core.db import Base, SessionLocal
from app.core.utils import utc_now
from app.quality.application.capa_notices import send_digests


def run(today=None) -> int:
    today = today or utc_now().date()
    orgs = Base.metadata.tables["foundation_organizations"]
    sent = 0
    with SessionLocal() as db:
        for organization_id in db.scalars(select(orgs.c.id).where(orgs.c.status == "active")).all():
            sent += send_digests(db, organization_id, today)
    return sent


def main() -> int:
    print(f"Corrective-action digests sent: {run()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
