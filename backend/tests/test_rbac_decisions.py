from tests.route_inventory import discover_routes
"""RBAC-002: every decision has its own permission; a sales representative sees and works only their own customers'
quotations, sales orders and samples; interactions and evaluations can be corrected or removed with their own
permissions; every permission has a readable Arabic and English name."""
import re

import pytest
from fastapi.routing import APIRoute

from app.core.security import hash_password
from app.core.storage import LocalFileStorage
from app.foundation.domain.enums import UserStatus
from app.foundation.domain.permission_catalog import ALL_PERMISSION_CODES, PERMISSION_BY_CODE
from app.foundation.domain.permission_labels import LABELS
from app.foundation.infrastructure.models import User, UserRole
from app.foundation.infrastructure.organization_queries import FoundationOrganizationQueries
from app.main import app

API = "/api/v1/commercial"
PASSWORD = "Test1234!"


def _route_policy(method, path):
    for route in discover_routes(app):
        if isinstance(route, APIRoute) and route.path == path and method in route.methods:
            def calls(dep):
                yield dep.call
                for child in dep.dependencies:
                    yield from calls(child)
            return [c.permission_policy for c in calls(route.dependant) if hasattr(c, "permission_policy")]
    raise AssertionError(f"no route {method} {path}")


@pytest.mark.parametrize("method,path,code", [
    ("DELETE", "/api/v1/admin/users/{user_id}", "foundation:users:deactivate"),
    ("POST", "/api/v1/shipping/shipments/{shipment_id}/fail", "shipping:shipments:fail"),
    ("POST", "/api/v1/shipping/shipments/{shipment_id}/close", "shipping:shipments:close"),
    ("POST", "/api/v1/shipping/returns/{return_id}/reject", "shipping:returns:reject"),
    ("POST", "/api/v1/procurement/purchase-orders/{order_id}/send", "procurement:purchase_orders:send"),
    ("POST", "/api/v1/procurement/purchase-orders/{order_id}/close", "procurement:purchase_orders:close"),
    ("POST", "/api/v1/quality/non-conformance-reports/{report_id}/contain", "quality:ncr_reports:contain"),
    ("POST", "/api/v1/quality/non-conformance-reports/{report_id}/investigate", "quality:ncr_reports:investigate"),
    ("POST", "/api/v1/quality/non-conformance-reports/{report_id}/submit", "quality:ncr_reports:submit"),
    ("POST", "/api/v1/masterdata/products/legacy/map", "masterdata:products:map_legacy"),
    ("POST", "/api/v1/masterdata/lists/{list_name}/legacy/map", "masterdata:lists:map_legacy"),
    ("PATCH", "/api/v1/commercial/customers/{customer_id}/interactions/{interaction_id}", "commercial:interactions:update"),
    ("DELETE", "/api/v1/commercial/customers/{customer_id}/interactions/{interaction_id}", "commercial:interactions:delete"),
    ("PATCH", "/api/v1/commercial/sample-evaluations/{evaluation_id}", "commercial:evaluations:update"),
    ("DELETE", "/api/v1/commercial/sample-evaluations/{evaluation_id}", "commercial:evaluations:delete"),
])
def test_each_decision_needs_its_own_permission(method, path, code):
    assert ("all", (code,)) in _route_policy(method, path)


def test_issuing_a_replacement_certificate_also_needs_revoke():
    policies = _route_policy("POST", "/api/v1/quality/quality-certificates/{certificate_id}/issue")
    assert ("all", ("quality:certificates:issue",)) in policies and ("in_handler", ("quality:certificates:revoke",)) in policies


def test_every_permission_has_a_readable_name_in_both_languages():
    assert set(LABELS) == set(ALL_PERMISSION_CODES)
    for code, (ar, en, description_ar, description_en) in LABELS.items():
        assert ar and en and description_ar and description_en, code
        assert re.search(r"[؀-ۿ]", ar) and not re.search(r"[؀-ۿ]", en), code
        assert PERMISSION_BY_CODE[code].name_ar == ar and PERMISSION_BY_CODE[code].name_en == en
    assert PERMISSION_BY_CODE["commercial:customers:update"].name_ar == "تعديل بيانات عميل"


def test_the_vague_write_permissions_are_gone():
    assert not [c for c in ALL_PERMISSION_CODES if c.startswith("commercial:") and c.endswith(":write")]


# ── A sales representative and their own customers ──────────────────────────────────────────────────────────────

@pytest.fixture
def two_reps(client, db, test_org, test_user):
    """test_user: commercial manager (sees all). rep_a and rep_b: sales representatives (their own customers only)."""
    provider = FoundationOrganizationQueries(db, LocalFileStorage("uploads"))
    roles = provider._seed_roles(test_org, provider._get_or_create_permissions(test_org.id))
    reps = []
    for name in ("a", "b"):
        user = User(organization_id=test_org.id, full_name=f"Rep {name.upper()}", email=f"rep-{name}@example.com",
                    password_hash=hash_password(PASSWORD), status=UserStatus.ACTIVE)
        db.add(user)
        db.flush()
        db.add(UserRole(user_id=user.id, role_id=roles["sales_rep"].id))
        reps.append(user)
    db.add(UserRole(user_id=test_user.id, role_id=roles["commercial_manager"].id))
    db.commit()

    def login(email):
        return {"Authorization": f"Bearer {client.post('/api/v1/auth/login', json={'email': email, 'password': PASSWORD}).json()['access_token']}"}

    manager = login("test@example.com")
    customers = [client.post(f"{API}/customers", headers=manager, json={"name": f"Customer of {u.full_name}", "sales_owner_user_id": str(u.id)}).json()["id"]
                 for u in reps]
    return dict(manager=manager, a=login("rep-a@example.com"), b=login("rep-b@example.com"), customers=customers)


def _quote(client, headers, customer):
    body = {"issue_date": "2026-06-09T10:00:00Z", "valid_until": "2026-07-09T10:00:00Z", "currency": "SAR",
            "items": [{"line_no": 1, "product_type": "pp_strap", "quantity": "10", "unit": "kg", "unit_price": "2"}]}
    return client.post(f"{API}/customers/{customer}/quotes", headers=headers, json=body)


def test_a_rep_sees_and_works_only_their_customers_quotations(client, two_reps):
    a_customer, b_customer = two_reps["customers"]
    mine = _quote(client, two_reps["a"], a_customer)
    assert mine.status_code == 201, mine.text
    assert _quote(client, two_reps["a"], b_customer).status_code == 404  # not one of theirs
    theirs = _quote(client, two_reps["b"], b_customer).json()

    assert [q["id"] for q in client.get(f"{API}/quotes", headers=two_reps["a"]).json()["items"]] == [mine.json()["id"]]
    assert client.get(f"{API}/quotes", headers=two_reps["manager"]).json()["total"] == 2
    assert client.get(f"{API}/quotes/{theirs['id']}", headers=two_reps["a"]).status_code == 404
    assert client.patch(f"{API}/quotes/{theirs['id']}", headers=two_reps["a"], json={"notes": "x"}).status_code == 404
    assert client.post(f"{API}/quotes/{theirs['id']}/issue", headers=two_reps["a"]).status_code in (400, 404)
    assert client.get(f"{API}/quotes/{theirs['id']}/document.pdf", headers=two_reps["a"]).status_code == 404
    assert client.post(f"{API}/quotes/{mine.json()['id']}/issue", headers=two_reps["a"]).json()["status"] == "issued"


def test_a_rep_drafts_orders_for_their_customers_but_the_manager_confirms(client, two_reps):
    a_customer, b_customer = two_reps["customers"]
    body = {"order_date": "2026-06-09T10:00:00Z", "customer_reference": "PO-1",
            "items": [{"line_no": 1, "product_type": "pp_strap", "quantity": "5", "unit": "kg"}]}
    order = client.post(f"{API}/customers/{a_customer}/orders", headers=two_reps["a"], json=body)
    assert order.status_code == 201, order.text
    assert client.post(f"{API}/customers/{b_customer}/orders", headers=two_reps["a"], json=body).status_code == 404
    assert client.get(f"{API}/orders", headers=two_reps["b"]).json()["total"] == 0
    assert client.post(f"{API}/orders/{order.json()['id']}/confirm", headers=two_reps["a"]).status_code == 403
    assert client.post(f"{API}/orders/{order.json()['id']}/confirm", headers=two_reps["manager"]).json()["status"] == "confirmed"


def test_interactions_are_corrected_and_removed_with_their_own_permissions(client, two_reps):
    a_customer, _ = two_reps["customers"]
    made = client.post(f"{API}/customers/{a_customer}/interactions", headers=two_reps["a"],
                       json={"interaction_type": "call", "interaction_date": "2026-06-01T10:00:00Z", "subject": "First call"}).json()
    path = f"{API}/customers/{a_customer}/interactions/{made['id']}"
    fixed = client.patch(path, headers=two_reps["a"], json={"subject": "First call (corrected)"})
    assert fixed.status_code == 200 and fixed.json()["subject"] == "First call (corrected)"
    assert client.patch(path, headers=two_reps["b"], json={"subject": "x"}).status_code == 404  # not theirs
    assert client.delete(path, headers=two_reps["a"]).status_code == 403  # a rep may correct, not delete
    assert client.delete(path, headers=two_reps["manager"]).status_code == 204
    assert client.get(f"{API}/customers/{a_customer}/interactions", headers=two_reps["manager"]).json()["total"] == 0
