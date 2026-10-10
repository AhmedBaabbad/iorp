from types import SimpleNamespace
from uuid import uuid4
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.main import app
from app.dependencies import get_current_user, get_current_tenant
from app.core.auth import AuthenticatedUser
from app.core.tenancy import TenantContext
from app.commercial.infrastructure.models import Customer, Sample


def auth(org,user,permissions):
    tenant=TenantContext(user,org,permissions=frozenset(permissions))
    current=SimpleNamespace(user=SimpleNamespace(id=user,is_organization_root=False),tenant=tenant,
        auth_user=AuthenticatedUser(user,org,'test@example.test',permissions=frozenset(permissions)))
    app.dependency_overrides[get_current_user]=lambda:current
    app.dependency_overrides[get_current_tenant]=lambda:tenant


@pytest.mark.parametrize('resource,action',[
    *[('quotes',a) for a in ['issue','accept','reject','expire','revise']],
    *[('orders',a) for a in ['confirm','cancel','revise']],
    ('follow-ups','cancel'),('follow-ups','reopen'),
])
def test_update_does_not_authorize_business_decisions(client,resource,action):
    permission_resource=resource.replace('-','_')
    auth(uuid4(),uuid4(),[f'commercial:{permission_resource}:update'])
    response=client.post(f'/api/v1/commercial/{resource}/{uuid4()}/{action}',json={'reason':'Audit'})
    assert response.status_code==403,response.text


@pytest.mark.parametrize('payload',[{'status':'cancelled'},{'status':'delivered'},{'status':'in_preparation'},{'sample_decision':'accepted'}])
def test_sample_patch_cannot_bypass_action_permissions(client,db,test_org,test_user,payload):
    c=Customer(organization_id=test_org.id,customer_code='ACTION-C',name='Action customer')
    db.add(c);db.flush()
    s=Sample(customer_id=c.id,sample_code='ACTION-S',product_type='legacy',request_date=datetime.now(timezone.utc),created_by_user_id=test_user.id)
    db.add(s);db.commit()
    auth(test_org.id,test_user.id,['commercial:samples:update'])
    response=client.patch(f'/api/v1/commercial/samples/{s.id}',json=payload)
    assert response.status_code==403,response.text
    db.refresh(s)
    assert s.status=='requested' and s.sample_decision is None


@pytest.mark.parametrize('new_status',['ready_for_planning','cancelled'])
def test_demand_update_does_not_authorize_transition(client,new_status):
    from app.production.domain import permissions as P
    auth(uuid4(),uuid4(),[P.DEMANDS_UPDATE])
    r=client.post(f'/api/v1/production/demands/{uuid4()}/status',json={'status':new_status})
    assert r.status_code==403,r.text


def test_issuer_cannot_change_certificate_settings(client):
    from app.quality.domain import permissions as Q
    auth(uuid4(),uuid4(),[Q.COA_ISSUE])
    assert client.patch('/api/v1/quality/quality-settings',json={}).status_code==403


@pytest.mark.parametrize('path,permission',[
    ('production/shift-rosters/{id}/close','production:shift_rosters:update'),
    *[(f'shipping/shipments/{{id}}/{action}','shipping:shipments:update') for action in ['ready','reopen','reschedule']],
    *[(f'quality/non-conformance-reports/{{id}}/actions/{{id}}/{action}','quality:ncr_reports:update') for action in ['complete','cancel']],
])
def test_operational_decisions_require_action_permission(client,path,permission):
    auth(uuid4(),uuid4(),[permission])
    response=client.post('/api/v1/'+path.replace('{id}',str(uuid4())),json={})
    assert response.status_code==403,response.text


def test_scoped_policy_denies_unassigned_record():
    from app.core.authorization.scoped_policy import ScopedAuthorizationPolicy
    from app.core.interfaces.authorization_policy import AuthorizationContext, AccessScope
    for scope in [AccessScope.OWN,AccessScope.TEAM]:
        ctx=AuthorizationContext(uuid4(),uuid4(),False,'commercial:customers:read',effective_scope=scope)
        assert not ScopedAuthorizationPolicy().can_access_record(ctx,None)


@pytest.mark.parametrize('filename,manager_code,permission_code',[
    ('2026_11_04_0900_f6a1b2k6_action_permissions.py','commercial_manager','commercial:orders:confirm'),
    ('2026_11_04_1000_f6a1b2k7_execution_permissions.py','shipping_manager','shipping:shipments:ready'),
])
def test_action_migration_preserves_custom_roles_and_downgrade(db,test_org,filename,manager_code,permission_code):
    from app.foundation.infrastructure.models import Role, Permission, RolePermission
    spec=importlib.util.spec_from_file_location('rbac_migration',Path(__file__).parents[1]/'alembic/versions'/filename)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    manager=Role(organization_id=test_org.id,name='Manager',code=manager_code,is_system=True)
    custom=Role(organization_id=test_org.id,name='Custom',code='custom_test')
    db.add_all([manager,custom]);db.commit()
    bind=db.connection();migration.op=Operations(MigrationContext.configure(bind))
    migration.upgrade()
    p=db.scalar(sa.select(Permission).where(Permission.organization_id==test_org.id,Permission.code==permission_code))
    assert p is not None
    assert db.scalar(sa.select(RolePermission).where(RolePermission.role_id==manager.id,RolePermission.permission_id==p.id))
    assert not db.scalar(sa.select(RolePermission).where(RolePermission.role_id==custom.id))
    grant=RolePermission(role_id=custom.id,permission_id=p.id,scope='organization')
    db.add(grant);db.flush();gid=grant.id
    migration.downgrade();db.expire_all()
    assert db.get(RolePermission,gid) is not None
    assert not db.scalar(sa.select(RolePermission).where(RolePermission.role_id==manager.id))
