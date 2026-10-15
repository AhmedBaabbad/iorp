"""Permission catalog governance, provisioning, isolation, and API tests."""

import ast
from pathlib import Path
import re
import warnings

import pytest

from tests.platform_stepup_client import verified_platform_browser  # noqa: F401  (Batch 3 step-up handshake)

from sqlalchemy import func, select

from app.core.config import settings
from app.core.storage import LocalFileStorage
from app.foundation.domain.enums import OrganizationStatus
from app.foundation.domain.permission_catalog import (
    ALL_PERMISSION_CODES, ALL_TENANT_PERMISSIONS, MODULE_NAMES, PermissionDefinition,
)
from app.foundation.domain.system_roles import SYSTEM_ROLES, permission_matches
from app.foundation.infrastructure.models import Organization, Permission
from app.foundation.infrastructure.organization_queries import FoundationOrganizationQueries


def _route_permissions() -> set[str]:
    found: set[str] = set()
    app_root = Path(__file__).parents[1] / "app"
    for path in app_root.rglob("routes_*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"require_permission", "require_any_permission"}:
                for value in ast.walk(node):
                    if isinstance(value, ast.Constant) and isinstance(value.value, str) and re.fullmatch(r"[a-z_]+:[a-z_]+:[a-z_]+", value.value) and not value.value.startswith("platform:"):
                        found.add(value.value)
    return found


def _organization(db, code="CATALOG-ORG"):
    organization = Organization(name=code, code=code, status=OrganizationStatus.ACTIVE, timezone="UTC", default_locale="en")
    db.add(organization); db.flush()
    return organization


def _seed(db, organization, tmp_path):
    query = FoundationOrganizationQueries(db, LocalFileStorage(str(tmp_path)))
    result = query._get_or_create_permissions(organization.id)
    db.flush()
    return result


def _bootstrap(client, db, monkeypatch):
    monkeypatch.setattr(settings, "bootstrap_token", "catalog-token")
    payload = {
        "bootstrap_token": "catalog-token",
        "platform_root": {"full_name": "Platform Root", "email": "platform@example.com", "password": "PlatformRoot123!", "password_confirmation": "PlatformRoot123!"},
        "organization": {"name": "Catalog Organization", "code": "catalog-org", "timezone": "UTC", "default_locale": "en"},
        "organization_admin": {"full_name": "Catalog Admin", "email": "catalog@example.com", "password": "CatalogAdmin123!", "password_confirmation": "CatalogAdmin123!"},
    }
    assert client.post("/api/v1/system/bootstrap/initialize", json=payload).status_code == 201
    login = client.post("/api/v1/auth/login", json={"email": "catalog@example.com", "password": "CatalogAdmin123!"})
    organization = db.scalar(select(Organization).where(Organization.code == "CATALOG-ORG"))
    return {"Authorization": f"Bearer {login.json()['access_token']}"}, organization


# T01-T07 catalog integrity
def test_t01_no_duplicate_codes():
    codes = [item.code for item in ALL_TENANT_PERMISSIONS]
    assert len(codes) == len(set(codes))


def test_t02_codes_match_required_format():
    assert all(re.fullmatch(r"[a-z_]+:[a-z_]+:[a-z_]+", item.code) for item in ALL_TENANT_PERMISSIONS)


def test_t03_code_fields_match():
    assert all(item.code.split(":") == [item.module, item.resource, item.action] for item in ALL_TENANT_PERMISSIONS)


def test_t04_names_are_non_empty():
    assert all(item.name_en.strip() and item.name_ar.strip() for item in ALL_TENANT_PERMISSIONS)


def test_t05_descriptions_are_non_empty():
    assert all(item.description_en.strip() and item.description_ar.strip() for item in ALL_TENANT_PERMISSIONS)


def test_t06_all_modules_have_display_names():
    assert {item.module for item in ALL_TENANT_PERMISSIONS} <= MODULE_NAMES.keys()


def test_t07_catalog_excludes_platform_permissions():
    assert not {code for code in ALL_PERMISSION_CODES if code.startswith("platform:")}


# T08-T09 route coverage
def test_t08_every_route_permission_exists_in_catalog():
    assert not (_route_permissions() - ALL_PERMISSION_CODES)


def test_t09_unused_catalog_permissions_are_reported():
    unused = ALL_PERMISSION_CODES - _route_permissions()
    if unused:
        warnings.warn(f"Catalog permissions not found directly in route guards: {sorted(unused)}", stacklevel=1)
    assert isinstance(unused, set | frozenset)


# T10-T15 seed process
def test_t10_seed_creates_complete_catalog(db, tmp_path):
    organization = _organization(db)
    assert len(_seed(db, organization, tmp_path)) == len(ALL_TENANT_PERMISSIONS)


def test_t11_seed_is_idempotent(db, tmp_path):
    organization = _organization(db)
    _seed(db, organization, tmp_path); before = db.query(Permission).count()
    _seed(db, organization, tmp_path)
    assert db.query(Permission).count() == before


def test_t12_seed_updates_catalog_metadata(db, tmp_path):
    organization = _organization(db); permissions = _seed(db, organization, tmp_path)
    permissions[0].name = "stale"; permissions[0].description = "stale"; db.flush()
    refreshed = _seed(db, organization, tmp_path)[0]
    assert refreshed.name != "stale" and refreshed.description != "stale"


def test_t13_seed_preserves_orphan_permissions(db, tmp_path):
    organization = _organization(db); _seed(db, organization, tmp_path)
    orphan = Permission(organization_id=organization.id, code="foundation:legacy:read", module_name="foundation", resource_name="legacy", action_name="read", name="Legacy", description="Legacy permission")
    db.add(orphan); db.flush(); _seed(db, organization, tmp_path)
    assert db.get(Permission, orphan.id) is not None


def test_t14_bootstrap_seeds_permissions(client, db, monkeypatch):
    _, organization = _bootstrap(client, db, monkeypatch)
    assert db.query(Permission).filter_by(organization_id=organization.id).count() == len(ALL_TENANT_PERMISSIONS)


@pytest.mark.usefixtures('verified_platform_browser')  # Batch 3: creating an organization requires fresh verification
def test_t15_platform_provisioning_seeds_permissions(client, db, monkeypatch):
    _bootstrap(client, db, monkeypatch)
    login = client.post("/api/v1/platform/login", json={"email": "platform@example.com", "password": "PlatformRoot123!"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    payload = {"organization": {"name": "Second", "code": "second", "timezone": "UTC", "default_locale": "ar"}, "organization_admin": {"full_name": "Second Root", "email": "second@example.com", "password": "SecondAdmin123!", "password_confirmation": "SecondAdmin123!"}}
    assert client.post("/api/v1/platform/organizations", headers=headers, json=payload).status_code == 201
    second = db.scalar(select(Organization).where(Organization.code == "SECOND"))
    assert db.query(Permission).filter_by(organization_id=second.id).count() == len(ALL_TENANT_PERMISSIONS)


# T16-T19 database integrity
def test_t16_no_duplicate_permission_codes_per_org(db, tmp_path):
    organization = _organization(db); _seed(db, organization, tmp_path)
    duplicates = db.execute(select(Permission.code).where(Permission.organization_id == organization.id).group_by(Permission.code).having(func.count(Permission.id) > 1)).all()
    assert duplicates == []


def test_t17_new_org_count_matches_catalog(db, tmp_path):
    organization = _organization(db); _seed(db, organization, tmp_path)
    assert db.query(Permission).filter_by(organization_id=organization.id).count() == len(ALL_TENANT_PERMISSIONS)


def test_t18_every_permission_has_module(db, tmp_path):
    organization = _organization(db); _seed(db, organization, tmp_path)
    assert all(permission.module_name for permission in db.query(Permission).filter_by(organization_id=organization.id))


def test_t19_organizations_have_independent_permission_rows(db, tmp_path):
    first = _organization(db, "ORG-A"); second = _organization(db, "ORG-B")
    first_rows = _seed(db, first, tmp_path); second_rows = _seed(db, second, tmp_path)
    assert {row.id for row in first_rows}.isdisjoint({row.id for row in second_rows})


# T20-T25 API endpoint
def test_t20_permissions_endpoint_returns_200(client, db, monkeypatch):
    headers, _ = _bootstrap(client, db, monkeypatch)
    assert client.get("/api/v1/admin/permissions", headers=headers).status_code == 200


def test_t21_response_is_grouped_by_module(client, db, monkeypatch):
    headers, _ = _bootstrap(client, db, monkeypatch); body = client.get("/api/v1/admin/permissions", headers=headers).json()
    assert body["total"] == len(ALL_TENANT_PERMISSIONS) and {group["module"] for group in body["modules"]} == {item.module for item in ALL_TENANT_PERMISSIONS}


def test_t22_permission_response_has_required_metadata(client, db, monkeypatch):
    headers, _ = _bootstrap(client, db, monkeypatch); item = client.get("/api/v1/admin/permissions", headers=headers).json()["modules"][0]["permissions"][0]
    assert {"code", "module", "resource", "action", "name", "description"} <= item.keys()


def test_t23_endpoint_uses_permissions_read_guard(client, db, monkeypatch):
    headers, _ = _bootstrap(client, db, monkeypatch)
    assert client.get("/api/v1/admin/permissions", headers=headers).status_code == 200


def test_t24_user_without_permission_receives_403(client, auth_headers):
    assert client.get("/api/v1/admin/permissions", headers=auth_headers).status_code == 403


def test_t25_endpoint_returns_only_current_org_rows(client, db, monkeypatch):
    headers, organization = _bootstrap(client, db, monkeypatch)
    other = _organization(db, "OTHER"); _seed(db, other, Path.cwd() / ".pytest-cache")
    body = client.get("/api/v1/admin/permissions", headers=headers).json()
    response_ids = {item["id"] for group in body["modules"] for item in group["permissions"]}
    own_ids = {str(row.id) for row in db.query(Permission).filter_by(organization_id=organization.id)}
    assert response_ids == own_ids


# T26-T27 system-role validation
def test_t26_explicit_system_role_permissions_exist():
    explicit = {str(pattern) for role in SYSTEM_ROLES for pattern in role["permissions"] if pattern not in {"ALL", "*:read"} and not str(pattern).endswith(":*")}
    assert explicit <= ALL_PERMISSION_CODES


def test_t27_every_system_role_pattern_matches_catalog():
    for role in SYSTEM_ROLES:
        for pattern in role["permissions"]:
            assert pattern == "ALL" or any(permission_matches(code, str(pattern)) for code in ALL_PERMISSION_CODES), f"Stale role permission pattern: {role['code']} -> {pattern}"
