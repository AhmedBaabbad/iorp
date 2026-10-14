from datetime import date
from sqlalchemy import event, select, func
import pytest


def test_governance_change_rolls_back_when_mandatory_audit_fails(db, test_org, test_user):
    from app.foundation.application.services import FoundationService
    from app.foundation.api.schemas import RoleCreateRequest
    from app.foundation.infrastructure.models import Role, TenantAuditEntry
    def fail(*args): raise RuntimeError('simulated audit outage')
    event.listen(TenantAuditEntry, 'before_insert', fail)
    try:
        with pytest.raises(RuntimeError, match='audit outage'):
            FoundationService(db).create_role_for_tenant(test_org.id, RoleCreateRequest(name='Must rollback', code='must_rollback'), test_user)
    finally:
        event.remove(TenantAuditEntry, 'before_insert', fail)
    assert db.scalar(select(func.count()).select_from(Role).where(Role.code == 'must_rollback')) == 0


@pytest.mark.parametrize('commit_succeeded', [False, True])
def test_file_compensation_preserves_committed_file_and_removes_uncommitted(db, test_org, test_user, tmp_path, monkeypatch, commit_succeeded):
    from app.shipping.application.attachment_service import AttachmentService
    from app.shipping.infrastructure.models import Shipment, ShippingAttachment
    from app.core.storage import LocalFileStorage
    from app.core.tenancy import TenantContext
    row = Shipment(organization_id=test_org.id, shipment_no='AUDIT', delivery_method='factory_delivery', status='dispatched',
                   shipment_date=date.today(), customer_name='Test', created_by_user_id=test_user.id)
    db.add(row); db.commit()
    service = AttachmentService(db, TenantContext(test_user.id, test_org.id), LocalFileStorage(str(tmp_path)))
    original_commit = db.commit
    def fail():
        if commit_succeeded: original_commit()
        raise RuntimeError('lost connection during commit')
    monkeypatch.setattr(db, 'commit', fail)
    with pytest.raises(RuntimeError):
        service.add_to_shipment(row.id, 'document', 'test.pdf', b'%PDF-synthetic-test\n%%EOF')
    assert len(list(tmp_path.rglob('*.pdf'))) == int(commit_succeeded)
    assert db.scalar(select(func.count()).select_from(ShippingAttachment)) == int(commit_succeeded)


def test_readiness_is_503_without_leaking_database_error(client, monkeypatch):
    def unavailable(): raise RuntimeError('sensitive-database-connection-details')
    monkeypatch.setattr('app.core.db.check_database_connection', unavailable)
    response = client.get('/health/ready')
    assert response.status_code == 503 and response.json() == {'status': 'not_ready'}
    assert client.get('/health').status_code == 200
    monkeypatch.setattr('app.core.db.check_database_connection', lambda: True)
    assert client.get('/health/ready').json() == {'status': 'ready'}
