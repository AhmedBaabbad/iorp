from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.audit import AuditActor, AuditRequestContext, PlatformAuditService, is_sensitive_key, sanitize_audit_value, sanitize_json
from app.core.security_models import AuthSecurityEvent
from app.platform.infrastructure.models import PlatformActivityLog
from app.main import app
from app.platform.api.routes_platform_audit import _csv_safe


@pytest.mark.parametrize("key", [
    "password", "new_password", "passwordConfirmation", "secret", "client-secret",
    "access_token", "refreshToken", "Authorization", "cookie", "session_cookie",
    "credential", "credentials", "api_key", "api-key", "apikey",
])
def test_audit_01_15_sensitive_keys_are_detected(key):
    assert is_sensitive_key(key)


@pytest.mark.parametrize("key", [
    "email", "full_name", "status", "reason", "target_id", "request_id", "organization",
])
def test_audit_16_22_safe_keys_are_retained(key):
    assert not is_sensitive_key(key)


@pytest.mark.parametrize("value,expected", [
    (None, None), (True, True), (42, 42), (1.5, 1.5), ("hello", "hello"),
    ([1, 2], [1, 2]), (("a", "b"), ["a", "b"]),
])
def test_audit_23_29_supported_values_are_normalized(value, expected):
    assert sanitize_audit_value(value) == expected


@pytest.mark.parametrize("formula", ["=1+1", "+SUM(A1:A2)", "-2+3", "@cmd", "=HYPERLINK('x')"])
def test_audit_30_34_csv_formula_injection_is_neutralized(formula):
    assert _csv_safe(formula).startswith("'")


@pytest.mark.parametrize("plain", ["success", "user@example.com", "123", " text ", None])
def test_audit_35_39_normal_csv_values_are_not_prefixed(plain):
    result = _csv_safe(plain)
    assert not result.startswith("'")


def test_audit_40_nested_secrets_are_removed():
    value = sanitize_json({"before": {"email": "a@x", "password": "never"}, "token": "never"})
    assert value == {"before": {"email": "a@x", "password": "***REDACTED***"}, "token": "***REDACTED***"}


def test_audit_41_collection_size_is_bounded():
    assert len(sanitize_audit_value(list(range(250)))) == 100


def test_audit_42_depth_is_bounded():
    value = current = {}
    for _ in range(12):
        current["child"] = {}
        current = current["child"]
    assert "[truncated]" in str(sanitize_json(value))


def test_audit_43_total_json_size_is_bounded():
    value = sanitize_json({f"field_{index}": "x" * 2000 for index in range(20)})
    assert value["truncated"] is True


def test_audit_44_service_persists_complete_sanitized_event(db):
    actor_id = uuid4(); org_id = uuid4()
    PlatformAuditService(db).record(
        event_type="organization_suspended", category="organization",
        actor=AuditActor("system"),
        target_type="organization", target_id=org_id, target_display="Factory",
        organization_id=org_id, reason="policy", changes={"password": "hidden", "status": "suspended"},
        metadata={"authorization": "hidden", "source": "console"},
        request=AuditRequestContext("req-1", "corr-1", "127.0.0.1", "pytest"),
    )
    db.commit(); saved = db.scalar(select(PlatformActivityLog).where(PlatformActivityLog.action == "organization.suspended"))
    assert saved and saved.entity_id == org_id
    assert saved.details["changes"] == {"password": "***REDACTED***", "status": "suspended"}
    assert saved.details["metadata"] == {"authorization": "***REDACTED***", "source": "console"}


def test_audit_45_service_truncates_snapshots_and_reason(db):
    PlatformAuditService(db).record(
        event_type="x" * 100, category="audit", actor=AuditActor("system", email="e" * 400, name="n" * 400),
        target_type="t" * 100, target_id="i" * 300, target_display="d" * 400, reason="r" * 500,
    )
    db.commit(); event = db.scalar(select(PlatformActivityLog).where(PlatformActivityLog.action == "x" * 80))
    assert event is not None and len(event.action) == 80 and len(event.entity_type) == 50
    assert len(event.entity_name) == 255


@pytest.mark.parametrize("path", ["/api/v1/platform/audit-logs", "/api/v1/platform/audit-logs/export.csv", f"/api/v1/platform/audit-logs/{uuid4()}"])
def test_audit_46_48_endpoints_reject_anonymous_access(client: TestClient, path):
    assert client.get(path).status_code == 401


def test_audit_49_openapi_has_no_mutating_audit_routes():
    paths = app.openapi()["paths"]
    for path, methods in paths.items():
        if "/platform/audit-logs" in path:
            assert not ({"post", "put", "patch", "delete"} & set(methods))


def test_audit_50_request_id_is_returned(client: TestClient):
    response = client.get("/health", headers={"X-Request-ID": "audit-test-1"})
    assert response.headers["X-Request-ID"] == "audit-test-1"


def test_audit_51_unsafe_request_id_is_replaced(client: TestClient):
    response = client.get("/health", headers={"X-Request-ID": "unsafe request id"})
    assert response.headers["X-Request-ID"] != "unsafe request id"
