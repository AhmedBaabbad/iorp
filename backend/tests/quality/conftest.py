"""Quality tests that exercise defect and NCR behaviour log in as the organization root.

Since QUAL-001 every quality route requires its permission; those behavioural tests are not about
permissions, so their users are organization roots (who may do everything). Permissions themselves
are covered with explicit grants in test_quality_inspections.py, which overrides the current user.
"""
import pytest
from sqlalchemy import event

from app.foundation.infrastructure.models import User


@pytest.fixture(autouse=True)
def quality_users_are_roots(db):
    def make_root(session, _flush_context, _instances):
        for obj in session.new:
            if isinstance(obj, User):
                obj.is_organization_root = True
    event.listen(db, "before_flush", make_root)
    yield
    event.remove(db, "before_flush", make_root)
