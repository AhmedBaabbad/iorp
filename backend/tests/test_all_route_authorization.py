from tests.route_inventory import discover_routes
"""Black-box deny tests for every registered static tenant policy, not only route metadata."""
import re
from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi.routing import APIRoute
from app.main import app
from app.dependencies import get_current_user, get_current_tenant
from app.core.auth import AuthenticatedUser
from app.core.tenancy import TenantContext
from app.foundation.domain.permission_catalog import ALL_PERMISSION_CODES


def calls(dep):
    yield dep.call
    for child in dep.dependencies: yield from calls(child)


def policies(route):
    return [getattr(c,'permission_policy') for c in calls(route.dependant) if hasattr(c,'permission_policy')]


ROUTES=[r for r in discover_routes(app) if isinstance(r,APIRoute)]
from tests.route_inventory import require_nonempty
STATIC=require_nonempty([r for r in ROUTES if any(p[0] in ('all','any') for p in policies(r))], 'static permission routes')

PUBLIC_OR_SELF = {
    '/api/v1/platform/mfa', '/api/v1/platform/mfa/enroll', '/api/v1/platform/mfa/confirm',
    '/api/v1/platform/mfa/step-up', '/api/v1/platform/mfa/disable', '/api/v1/platform/mfa/recovery',
    # ADR-010: authenticated owner only; current password + dual mailbox verification.
    '/api/v1/auth/me/email-change', '/api/v1/auth/me/email-change/confirm',
    '/health', '/health/ready', '/api/v1/auth/login','/api/v1/auth/refresh','/api/v1/auth/logout',
    '/api/v1/auth/me','/api/v1/auth/me/profile','/api/v1/auth/me/effective-access',
    '/api/v1/auth/change-password','/api/v1/auth/forgot-password','/api/v1/auth/reset-password',
    '/api/v1/platform/login','/api/v1/platform/refresh','/api/v1/platform/logout','/api/v1/platform/me',
    '/api/v1/platform/account/change-password','/api/v1/platform/change-password',
    '/api/v1/platform/auth/forgot-password','/api/v1/platform/auth/reset-password',
    '/api/v1/system/bootstrap/status','/api/v1/system/bootstrap/initialize',
    '/api/v1/dashboard/summary', # authenticated, filters each metric by its source permission
    '/api/v1/system/file-policy', # public: upload types and sizes only, nothing of any organization
    '/api/v1/organization/storage', # any user of the session's own organization: the limits and its own usage
    '/api/v1/approvals/{resource_type}/{resource_id}', # the module owning the document decides who reads its signatures
    '/api/v1/organization/logo', # GET: any user of the session's own organization (the sidebar); POST/DELETE keep their permission
    # the session's own notifications only (PROJECT-NOTIFY-001): every query filters on the signed-in user
    '/api/v1/notifications','/api/v1/notifications/summary','/api/v1/notifications/read-all',
    '/api/v1/notifications/{item_id}/read','/api/v1/notifications/{item_id}/acknowledge',
    '/api/v1/notifications/{item_id}/hide','/api/v1/notifications/hide-read',
    # the signed-in user's own sessions (SEC-001)
    '/api/v1/auth/sessions','/api/v1/auth/sessions/end',
}


def test_every_api_route_declares_a_policy_or_documented_public_self_boundary():
    missing=[r.path for r in ROUTES if r.path not in PUBLIC_OR_SELF and not policies(r)
             and not any(hasattr(c,'platform_permission') for c in calls(r.dependant))]
    assert not missing,missing


def test_reports_deny_generation_without_definition_permission(client):
    from app.core.reporting.registry import registry
    org,user=uuid4(),uuid4()
    tenant=TenantContext(user_id=user,organization_id=org)
    current=SimpleNamespace(user=SimpleNamespace(id=user,is_organization_root=False,full_name='Audit'),tenant=tenant,
        auth_user=AuthenticatedUser(user,org,'audit@example.test'))
    app.dependency_overrides[get_current_user]=lambda:current
    app.dependency_overrides[get_current_tenant]=lambda:tenant
    for key in require_nonempty(registry.definitions, 'report definitions'):
        for format in ['preview','pdf']:
            response=client.post(f'/api/v1/reports/{key}/{format}',json={})
            assert response.status_code==403,(key,format,response.text[:100])


def test_static_codes_are_registered():
    missing=[(r.path,code) for r in STATIC for mode,codes in policies(r) if mode in ('all','any')
             for code in codes if code not in ALL_PERMISSION_CODES]
    assert not missing,missing


@pytest.mark.parametrize('route',STATIC,ids=lambda r:','.join(sorted(r.methods))+' '+r.path)
def test_no_permissions_cannot_access_operational_route(client,route):
    org,user=uuid4(),uuid4()
    tenant=TenantContext(organization_id=org,user_id=user,is_organization_root=False)
    current=SimpleNamespace(user=SimpleNamespace(id=user,is_organization_root=False),tenant=tenant,
        auth_user=AuthenticatedUser(user,org,'audit@example.test'))
    app.dependency_overrides[get_current_user]=lambda:current
    app.dependency_overrides[get_current_tenant]=lambda:tenant
    path=re.sub(r'\{[^}]+\}',str(uuid4()),route.path)
    response=client.request(next(iter(route.methods)),path,json={})
    assert response.status_code==403,(route.path,response.status_code,response.text[:200])
