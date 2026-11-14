"""Bounded list/presence queries and SQL-only security history checks."""
from uuid import uuid4
import pytest
from sqlalchemy import event, select
from app.core.db import Base
from app.core.utils import utc_now
from app.foundation.infrastructure.models import User, TenantSecurityEvent
from app.foundation.infrastructure.permanent_deletion import personal_security_condition, detach_personal_security, reference_tables
from tests.foundation.test_users_ux import users, BASE  # noqa: F401


def queries(db, action):
    statements = []
    def capture(connection, cursor, statement, *args):
        statements.append(statement)
    event.listen(db.bind, 'before_cursor_execute', capture)
    try:
        response = action()
    finally:
        event.remove(db.bind, 'before_cursor_execute', capture)
    return response, statements


def test_user_list_has_two_queries_for_twenty_users_without_reference_scan(users, monkeypatch):
    from app.foundation.application import permanent_deletion
    e = users
    def forbidden(*args):
        raise AssertionError('List must never compute deletion eligibility')
    monkeypatch.setattr(permanent_deletion, 'deletion_block', forbidden)
    # Warm up lazy fixture/current-context loads before measuring endpoint work.
    assert e.client.get(BASE).status_code == 200
    first, initial = queries(e.db, lambda: e.client.get(BASE))
    for number in range(18):
        e.db.add(User(organization_id=e.org.id, email=f'perf{number}@example.com',
            full_name=f'Performance {number}', password_hash='!', status='active'))
    e.db.commit()
    assert e.client.get(BASE).status_code == 200
    response, statements = queries(e.db, lambda: e.client.get(BASE))
    assert response.status_code == first.status_code == 200
    assert len(response.json()) == 20
    assert len(initial) == len(statements) == 2
    assert all('can_delete_permanently' not in row and 'delete_block' not in row for row in response.json())
    assert all('foundation_security_events' not in sql for sql in statements)


def test_presence_is_one_scoped_query(users, monkeypatch):
    from app.foundation.application import permanent_deletion
    e = users
    e.target.last_seen_at = utc_now(); e.db.commit()
    identifier = e.target.id
    def forbidden(*args):
        raise AssertionError('Presence must not scan deletion references')
    monkeypatch.setattr(permanent_deletion, 'deletion_block', forbidden)
    assert e.client.get(BASE).status_code == 200
    response, statements = queries(e.db, lambda: e.client.get(f'{BASE}/{identifier}/presence'))
    assert response.status_code == 200 and response.json()['is_online'] is True
    assert set(response.json()) == {'last_seen_at', 'is_online'}
    assert len(statements) == 1 and 'foundation_users' in statements[0]
    assert 'organization_id' in statements[0]
    assert e.client.get(f'{BASE}/{uuid4()}/presence').status_code == 404
    from app.foundation.infrastructure.models import Organization
    other = Organization(name='Other', code='PERF-OTHER', status='active')
    e.db.add(other); e.db.flush()
    foreign = User(organization_id=other.id, email='foreign-perf@example.com', full_name='Other', password_hash='!', status='active')
    e.db.add(foreign); e.db.commit()
    assert e.client.get(f'{BASE}/{foreign.id}/presence').status_code == 404
    e.current.auth_user.permissions.discard('foundation:users:read')
    assert e.client.get(f'{BASE}/{identifier}/presence').status_code == 403


@pytest.mark.parametrize('kind,details,personal', [
    ('tenant.token_refreshed', None, True),
    ('tenant.login_success', {}, True),
    ('tenant.login_failed', {'user_id': None}, True),
    ('tenant.sessions_ended', {'reason': 'ended_by_user'}, True),
    ('tenant.sessions_ended', {'reason': 'session_limit'}, True),
    ('tenant.sessions_ended', {'reason': 'admin_action'}, False),
    ('tenant.sessions_ended', {}, False),
    ('user.locked', {}, False),
    ('tenant.unknown_future_event', {}, False),
    ('tenant.token_refreshed', [], False),
    ('tenant.login_success', 'invalid', False),
    ('tenant.login_success', {'target_user_id': 'someone-else'}, False),
])
def test_personal_security_sql_predicate(users, kind, details, personal):
    e = users
    row = TenantSecurityEvent(organization_id=e.org.id, actor_id=e.target.id, event_type=kind, details=details)
    e.db.add(row); e.db.commit()
    table = Base.metadata.tables['foundation_security_events']
    assert e.db.scalar(select(personal_security_condition(e.db,e.target.id,e.org.id)).where(table.c.id==row.id)) is personal


def test_thousands_of_personal_events_detach_with_one_update(users):
    e = users
    e.db.execute(TenantSecurityEvent.__table__.insert(), [dict(organization_id=e.org.id,
        actor_id=e.target.id,event_type='tenant.token_refreshed',details={'user_id':str(e.target.id)}) for _ in range(2000)])
    e.db.commit()
    # Load user values before counting, so detached ORM instances add no noise.
    _ = e.target.email
    history, probes = queries(e.db, lambda: reference_tables(e.db,e.target.id,e.org.id))
    assert history == []
    security_probes = [sql for sql in probes if 'foundation_security_events' in sql]
    assert len(security_probes) == 1
    assert security_probes[0].startswith('SELECT 1') and 'LIMIT' in security_probes[0]
    result, statements = queries(e.db, lambda: detach_personal_security(e.db,e.target))
    assert result == {'foundation_security_events':2000}
    assert len(statements) == 1 and statements[0].lstrip().upper().startswith('UPDATE ')
    e.db.rollback()
