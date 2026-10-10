"""RBAC-003: the system roles — one manager per module, executing roles under them, the factory manager oversees, the
viewer reads the business only. Each role's permissions are exactly the approved list."""
from app.foundation.domain.permission_catalog import ALL_PERMISSION_CODES
from app.foundation.domain.system_roles import RETIRED_SYSTEM_ROLES, SYSTEM_ROLE_BY_CODE, permission_matches, scope_for


def granted(role):
    return {c for c in ALL_PERMISSION_CODES if any(permission_matches(c, p) for p in SYSTEM_ROLE_BY_CODE[role]["permissions"])}


def test_the_approved_roles_and_their_sizes():
    sizes = {code: len(granted(code)) for code in SYSTEM_ROLE_BY_CODE}
    assert sizes == {"organization_admin": len(ALL_PERMISSION_CODES), "commercial_manager": 71, "sales_rep": 40, "production_manager": 74,
                     "production_supervisor": 32, "quality_manager": 55, "quality_inspector": 25, "procurement_manager": 31,
                     "shipping_manager": 32, "factory_manager": 56, "viewer": 45}
    assert not set(RETIRED_SYSTEM_ROLES) & set(SYSTEM_ROLE_BY_CODE)


def test_each_manager_owns_their_module():
    for role, module in (("commercial_manager", "commercial:"), ("production_manager", "production:"), ("quality_manager", "quality:"),
                         ("procurement_manager", "procurement:"), ("shipping_manager", "shipping:")):
        assert {c for c in ALL_PERMISSION_CODES if c.startswith(module)} <= granted(role), role


def test_only_the_administrator_sets_vat_and_currency():
    assert [r for r in SYSTEM_ROLE_BY_CODE if "masterdata:settings:update" in granted(r)] == ["organization_admin"]


def test_the_viewer_reads_the_business_but_not_the_administration():
    viewer = granted("viewer")
    assert all(c.endswith(":read") or c.startswith("reports:") for c in viewer)
    assert not [c for c in viewer if c.startswith("foundation:")]
    assert {"commercial:customers:read", "production:production_orders:read", "quality:quality_checks:read"} <= viewer


def test_executing_roles_record_but_do_not_decide():
    inspector = granted("quality_inspector")
    assert {"quality:quality_checks:measure", "quality:quality_checks:close", "quality:ncr_reports:create"} <= inspector
    assert not inspector & {"quality:rejections:decide", "quality:ncr_reports:verify", "quality:certificates:issue",
                            "quality:certificates:revoke", "quality:specifications:activate"}


def test_the_factory_manager_decides_without_the_daily_work():
    factory = granted("factory_manager")
    assert {"production:production_orders:release", "production:production_orders:close", "quality:rejections:decide",
            "quality:certificates:issue", "shipping:returns:approve", "procurement:purchase_orders:approve"} <= factory
    assert not factory & {"production:production_orders:create", "production:results:create", "quality:quality_checks:create",
                          "shipping:shipments:create", "procurement:purchase_orders:create"}


def test_the_sales_rep_works_their_own_customers_and_drafts_only():
    rep = granted("sales_rep")
    assert {"commercial:quotes:issue", "commercial:orders:create"} <= rep
    assert not rep & {"commercial:orders:confirm", "commercial:orders:cancel", "commercial:orders:delete", "production:demands:read"}
    assert all(scope_for("sales_rep", f"commercial:{r}:read") == "own" for r in ("customers", "quotes", "orders", "samples", "follow_ups", "interactions"))


def test_the_shipping_manager_no_longer_edits_sales_orders():
    assert "commercial:orders:update" not in granted("shipping_manager")


def test_a_new_organization_gets_exactly_these_roles(db, test_org):
    from app.core.storage import LocalFileStorage
    from app.foundation.infrastructure.organization_queries import FoundationOrganizationQueries
    provider = FoundationOrganizationQueries(db, LocalFileStorage("uploads"))
    roles = provider._seed_roles(test_org, provider._get_or_create_permissions(test_org.id))
    assert set(roles) == set(SYSTEM_ROLE_BY_CODE)
