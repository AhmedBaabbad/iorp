from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.core.auth import AuthenticatedUser
from app.core.tenancy import TenantContext
from app.dependencies import get_current_user
from app.main import app
from app.quality.infrastructure.models import QualityCheck
from app.commercial.infrastructure.models import Customer


def test_commercial_followups_and_sample_decisions(client, db, test_org, test_user, monkeypatch):
    from datetime import timedelta
    from app.commercial.infrastructure.models import Sample, FollowUp
    from app.commercial.application import dashboard_service
    now = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(dashboard_service, 'utc_now', lambda: now)
    own = Customer(organization_id=test_org.id, customer_code='DASH', name='Customer')
    foreign = Customer(organization_id=uuid4(), customer_code='FOREIGN', name='Foreign')
    db.add_all([own, foreign]); db.flush()
    for customer, hours, status in [(own, -1, 'pending'), (own, 0, 'in_progress'), (own, 24, 'pending'),
                                   (own, 168, 'pending'), (own, -2, 'completed'), (own, -3, 'cancelled'),
                                   (foreign, -5, 'pending')]:
        db.add(FollowUp(customer_id=customer.id, assigned_user_id=test_user.id, due_date=now + timedelta(hours=hours),
                        status=status, reason='Test'))
    for customer, decision, status in [(own, 'accepted', 'evaluated'), (own, 'rejected', 'evaluated'),
                                        (own, None, 'delivered'), (own, 'pending', 'requested'),
                                        (own, 'accepted', 'cancelled'), (foreign, 'accepted', 'evaluated')]:
        db.add(Sample(customer_id=customer.id, sample_code=str(uuid4()), product_type='Test', request_date=now,
                      created_by_user_id=test_user.id, sample_decision=decision, status=status))
    db.commit()
    login(test_org.id, test_user.id, ['commercial:samples:read', 'commercial:follow_ups:read'])
    response = client.get('/api/v1/commercial/dashboard')
    assert response.status_code == 200, response.text
    cards = {c['key']: float(c['value']) for c in response.json()['cards']}
    for key in ['overdue_follow_ups', 'due_today_follow_ups', 'upcoming_follow_ups', 'samples_accepted',
                'samples_rejected', 'samples_awaiting_evaluation']:
        assert cards[key] == 1, (key, cards)
    assert cards['samples_pending_decision'] == 2
    assert {'overdue_follow_up', 'due_follow_up', 'sample_to_evaluate'} == {a['kind'] for a in response.json()['attention']}
    login(test_org.id, test_user.id, ['commercial:customers:read'])
    keys = {c['key'] for c in client.get('/api/v1/commercial/dashboard').json()['cards']}
    assert not keys.intersection(cards)


def test_commercial_sample_and_followup_cards_respect_own_grants(client, db, test_org, test_user):
    from app.commercial.infrastructure.models import Sample, FollowUp
    from app.foundation.infrastructure.models import Role, Permission, RolePermission, UserRole
    role = Role(organization_id=test_org.id, code='commercial_dashboard_own', name='Own')
    db.add(role); db.flush()
    db.add(UserRole(user_id=test_user.id, role_id=role.id))
    permissions = ['commercial:samples:read', 'commercial:follow_ups:read']
    for code in permissions:
        permission = Permission(organization_id=test_org.id, code=code, name=code, description=code,
                                module_name='commercial', resource_name=code.split(':')[1], action_name='read')
        db.add(permission); db.flush()
        db.add(RolePermission(role_id=role.id, permission_id=permission.id, scope='own'))
    for owner in [test_user.id, uuid4()]:
        customer = Customer(organization_id=test_org.id, customer_code=str(owner), name='Customer', sales_owner_user_id=owner)
        db.add(customer); db.flush()
        db.add(Sample(customer_id=customer.id, sample_code=str(uuid4()), product_type='Test',
                      request_date=datetime.now(timezone.utc), created_by_user_id=test_user.id, sample_decision='accepted'))
        db.add(FollowUp(customer_id=customer.id, assigned_user_id=owner,
                        due_date=datetime(2020, 1, 1, tzinfo=timezone.utc), reason='Test'))
    db.commit()
    login(test_org.id, test_user.id, permissions)
    response = client.get('/api/v1/commercial/dashboard')
    assert response.status_code == 200, response.text
    cards = {c['key']: float(c['value']) for c in response.json()['cards']}
    assert cards['samples_accepted'] == cards['overdue_follow_ups'] == 1

READ = {
    'commercial': ['commercial:customers:read', 'commercial:quotes:read', 'commercial:orders:read', 'commercial:samples:read', 'commercial:follow_ups:read'],
    'quality': ['quality:quality_checks:read', 'quality:quality_defects:read', 'quality:rejections:read', 'quality:ncr_reports:read', 'quality:certificates:read'],
    'shipping': ['shipping:shipments:read', 'shipping:returns:read'],
    'procurement': ['procurement:suppliers:read', 'procurement:purchase_orders:read', 'procurement:receipts:read'],
}


def login(org, user, permissions):
    tenant = TenantContext(user, org, permissions=frozenset(permissions))
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        user=SimpleNamespace(id=user, is_organization_root=False), tenant=tenant,
        auth_user=AuthenticatedUser(user, org, 'dashboard@example.test', permissions=frozenset(permissions)))


@pytest.mark.parametrize('module', READ)
def test_each_dashboard_handles_empty_database_and_rejects_unauthorized_user(client, test_org, test_user, module):
    login(test_org.id, test_user.id, [])
    assert client.get(f'/api/v1/{module}/dashboard').status_code == 403
    login(test_org.id, test_user.id, READ[module])
    response = client.get(f'/api/v1/{module}/dashboard?period=1w')
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['module'] == module and body['period'] == '1w'
    assert body['cards'] and all(c['value'] is None or float(c['value']) == 0 for c in body['cards'])
    assert client.get(f'/api/v1/{module}/dashboard?period=invalid').status_code == 422


def test_quality_uses_inspection_counts_not_mixed_units_and_filters_tenant(client, db, test_org, test_user):
    now = datetime.now(timezone.utc)
    for org, result, quantity, unit in [(test_org.id, 'accepted', 1000, 'kg'), (test_org.id, 'rejected', 1, 'roll'), (uuid4(), 'accepted', 2000, 'kg')]:
        db.add(QualityCheck(organization_id=org, inspection_code=str(uuid4()), check_datetime=now, closed_at=now,
            check_type='in_process_inspection', status='closed', result=result, unit=unit, qty_inspected=quantity,
            qty_accepted=quantity if result == 'accepted' else 0, qty_rejected=quantity if result == 'rejected' else 0, checked_by_user_id=test_user.id))
    db.commit()
    login(test_org.id, test_user.id, ['quality:quality_checks:read'])
    response = client.get('/api/v1/quality/dashboard')
    assert response.status_code == 200, response.text
    cards = {c['key']: c['value'] for c in response.json()['cards']}
    assert float(cards['checks_closed']) == 2
    assert float(cards['acceptance_rate']) == 50
    assert 'open_ncrs' not in cards and 'certificates' not in cards


def test_commercial_customer_count_respects_own_scope(client, db, test_org, test_user):
    from app.foundation.infrastructure.models import Role, Permission, RolePermission, UserRole
    role = Role(organization_id=test_org.id, code='dashboard_own', name='Own dashboard')
    permission = Permission(organization_id=test_org.id, code='commercial:customers:read', name='Read', description='Read customers', module_name='commercial', resource_name='customers', action_name='read')
    db.add_all([role, permission]); db.flush()
    db.add_all([UserRole(user_id=test_user.id, role_id=role.id), RolePermission(role_id=role.id, permission_id=permission.id, scope='own')])
    db.add_all([Customer(organization_id=test_org.id, customer_code='OWN', name='Own', sales_owner_user_id=test_user.id),
        Customer(organization_id=test_org.id, customer_code='OTHER', name='Other', sales_owner_user_id=uuid4())])
    db.commit()
    login(test_org.id, test_user.id, ['commercial:customers:read'])
    response = client.get('/api/v1/commercial/dashboard')
    assert response.status_code == 200, response.text
    cards = {c['key']: c['value'] for c in response.json()['cards']}
    assert float(cards['active_customers']) == 1 and 'quotes_issued' not in cards
