from datetime import timedelta
import pytest
from app.core.security import hash_password
from app.core.tenancy import TenantContext
from app.core.utils import utc_now
from app.foundation.infrastructure.models import User, UserRole
from tests.foundation.test_users_ux import users, remove, BASE  # noqa: F401
from tests.commercial.test_customer_sales_owner import _make_role


@pytest.mark.parametrize('activated_by',['password','login','seen'])
def test_activation_guard_precedes_every_history_query(users,monkeypatch,activated_by):
    from app.foundation.application import permanent_deletion
    e=users
    if activated_by=='password':e.target.password_hash=hash_password('Activated123!')
    elif activated_by=='login':e.target.last_login_at=utc_now()
    else:e.target.last_seen_at=utc_now()
    e.db.commit()
    def forbidden(*args):raise AssertionError('Activated accounts must not scan references')
    monkeypatch.setattr(permanent_deletion,'reference_tables',forbidden)
    response=remove(e)
    assert response.status_code==409 and response.json()['code']=='USER_DELETE_ACTIVATED'
    assert e.client.get(f'{BASE}/{e.target.id}').json()['delete_block']=={'code':'USER_DELETE_ACTIVATED','tables':[]}


def test_invited_account_without_links_can_be_cancelled(users):
    assert remove(users).status_code==200


def test_assigned_customer_blocks_invitation_cancellation(users):
    from app.commercial.infrastructure.models import Customer
    e=users
    e.db.add(Customer(organization_id=e.org.id,customer_code='INVITE',name='Assigned',sales_owner_user_id=e.target.id,created_by_user_id=e.actor.id));e.db.commit()
    response=remove(e)
    assert response.status_code==409 and response.json()['code']=='USER_DELETE_HAS_HISTORY'
    assert response.json()['details']['tables']==['customers']


def grant(e,extra):
    e.current.auth_user.permissions.update(extra)
    e.current.tenant=TenantContext(e.actor.id,e.org.id,permissions=frozenset(e.current.auth_user.permissions))


def test_selection_endpoints_hide_archived_inactive_and_keep_historical_names(users):
    from app.foundation.application.user_directory import FoundationUserDirectory
    from app.commercial.application.sales_owner_eligibility import SalesOwnerEligibilityService
    from app.commercial.application.follow_up_eligibility import FollowUpAssigneeEligibilityService
    from app.commercial.infrastructure.complaint_queries import eligible_users
    from app.commercial.infrastructure.models import Customer
    e=users
    codes={'commercial:customers:read','commercial:customers:update','commercial:follow_ups:read','commercial:follow_ups:update','commercial:complaints:read','commercial:complaints:update','procurement:purchase_orders:approve','foundation:delegations:manage','quality:ncr_reports:create'}
    grant(e,codes)
    role=_make_role(e.db,e.org,'selector',codes)
    good=e.target
    e.db.add(UserRole(user_id=good.id,role_id=role.id))
    excluded=[]
    for state in ['inactive','locked','archived']:
        user=User(organization_id=e.org.id,email=f'{state}@example.com',full_name=state,password_hash='!',status=state if state!='archived' else 'active',archived_at=utc_now() if state=='archived' else None)
        e.db.add(user);e.db.flush();e.db.add(UserRole(user_id=user.id,role_id=role.id));excluded.append(user.id)
    customer=Customer(organization_id=e.org.id,customer_code='SELECT',name='Select',sales_owner_user_id=good.id)
    e.db.add(customer);e.db.commit()
    for path in [f'{BASE}?selection=true','/api/v1/commercial/customers/eligible-sales-owners','/api/v1/commercial/follow-ups/eligible-assignees','/api/v1/quality/non-conformance-reports/lookups/users']:
        response=e.client.get(path);assert response.status_code==200,response.text
        ids={row['id'] for row in response.json()}
        assert str(good.id) in ids and not ids.intersection(map(str,excluded))
    options=e.client.get('/api/v1/delegations/options');assert options.status_code==200,options.text
    for kind in ['delegates','delegators']:
        assert not {str(identifier) for identifier in excluded}.intersection(row['id'] for row in options.json()[kind])
    directory=FoundationUserDirectory()
    assert not set(excluded).intersection(directory.active_users(e.db,e.org.id))
    assert directory.names(e.db,e.org.id,excluded)==dict(zip(excluded,['inactive','locked','archived']))
    assert not set(excluded).intersection(row.id for row in SalesOwnerEligibilityService(e.db).list_eligible_users(e.org.id))
    assert not set(excluded).intersection(row.id for row in FollowUpAssigneeEligibilityService(e.db).list_eligible_users(e.org.id))
    assert not set(excluded).intersection(row['id'] for row in eligible_users(e.db,e.current.tenant,customer))
    for identifier in excluded:
        assert not SalesOwnerEligibilityService(e.db).is_user_eligible(identifier,e.org.id)
        assert not FollowUpAssigneeEligibilityService(e.db).is_user_eligible(identifier,e.org.id)


def test_transfer_deactivate_archive_and_restore_preserve_records(users):
    from app.commercial.infrastructure.models import Customer,FollowUp
    from app.commercial.domain.enums import FollowUpStatus,FollowUpPriority
    e=users
    codes={'commercial:customers:assign_owner','commercial:customers:read','commercial:customers:update','commercial:follow_ups:assign','commercial:follow_ups:read','commercial:follow_ups:update','foundation:users:activate'}
    grant(e,codes)
    role=_make_role(e.db,e.org,'replacement',codes)
    replacement=User(organization_id=e.org.id,email='replacement@example.com',full_name='Replacement',password_hash='!',status='active')
    e.db.add(replacement);e.db.flush();e.db.add(UserRole(user_id=replacement.id,role_id=role.id))
    e.target.password_hash=hash_password('Activated123!')
    customer=Customer(organization_id=e.org.id,customer_code='MOVE',name='Keep customer',sales_owner_user_id=e.target.id,created_by_user_id=e.actor.id)
    e.db.add(customer);e.db.flush()
    follow=FollowUp(customer_id=customer.id,assigned_user_id=e.target.id,created_by_user_id=e.actor.id,due_date=utc_now()+timedelta(days=1),priority=FollowUpPriority.MEDIUM,status=FollowUpStatus.PENDING,reason='Keep follow-up')
    e.db.add(follow);e.db.commit()
    target=e.target.id;other=replacement.id
    assert e.client.get(f'{BASE}/{target}/deactivation-impact').json()['total_blocking_items']==2
    assert e.client.post(f'{BASE}/{target}/deactivate',json={'reason':'Offboarding'}).status_code==409
    for path in ['customers/reassign-by-owner','follow-ups/reassign-by-user']:
        response=e.client.post('/api/v1/commercial/'+path,json={'from_user_id':str(target),'to_user_id':str(other)})
        assert response.status_code==200,response.text
    assert e.client.get(f'{BASE}/{target}/deactivation-impact').json()['total_blocking_items']==0
    assert e.client.post(f'{BASE}/{target}/deactivate',json={'reason':'Offboarding'}).status_code==200
    archived=e.client.post(f'{BASE}/{target}/archive',json={'reason':'Employment ended'})
    assert archived.status_code==200,archived.text
    assert archived.json()['archived_at'] and archived.json()['archived_by_name']==e.actor.full_name and archived.json()['archived_reason']=='Employment ended'
    e.db.refresh(customer);e.db.refresh(follow)
    assert customer.sales_owner_user_id==other and follow.assigned_user_id==other
    assert remove(e).json()['code']=='USER_DELETE_ACTIVATED'
    restored=e.client.post(f'{BASE}/{target}/restore',json={'reason':'Archive correction'})
    assert restored.status_code==200 and restored.json()['archived_at'] is None and restored.json()['status']=='inactive'
