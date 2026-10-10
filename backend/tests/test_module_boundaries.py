import ast
import inspect
import importlib
from pathlib import Path
from typing import Protocol

from app.core.interfaces.follow_up_queries import FollowUpQueryInterface
from app.core.interfaces.organization_queries import OrganizationProvisioningInterface
from app.core.interfaces.product_catalog import ProductCatalog

APP_ROOT = Path(__file__).parents[1] / "app"


def _imports(path: Path) -> set[str]:
    found: set[str] = set()
    for file in path.rglob("*.py"):
        tree = ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.add(node.module)
    return found


def _model_tables(module) -> list[str]:
    return [
        value.__tablename__
        for _, value in inspect.getmembers(module, inspect.isclass)
        if value.__module__ == module.__name__ and hasattr(value, "__tablename__")
    ]


def test_b01_foundation_does_not_import_platform():
    assert not {item for item in _imports(APP_ROOT / "foundation") if item.startswith("app.platform")}


def test_b02_platform_does_not_import_foundation():
    assert not {item for item in _imports(APP_ROOT / "platform") if item.startswith("app.foundation")}


def test_b03_platform_tables_use_system_prefix():
    from app.platform.infrastructure import models

    tables = _model_tables(models)
    assert tables and all(table.startswith("system_") for table in tables)


def test_b04_foundation_tables_use_foundation_prefix():
    from app.foundation.infrastructure import models

    tables = _model_tables(models)
    assert tables and all(table.startswith("foundation_") for table in tables)


def test_b05_platform_routes_never_use_tenant_auth():
    imports = _imports(APP_ROOT / "platform" / "api")
    assert "app.dependencies.get_current_user" not in imports
    source = "\n".join(
        file.read_text(encoding="utf-8")
        for file in (APP_ROOT / "platform" / "api").glob("routes_*.py")
    )
    assert "get_current_user" not in source
    assert "get_current_platform_account" in source


def test_b06_tenant_routes_never_use_platform_auth():
    source = "\n".join(
        file.read_text(encoding="utf-8")
        for file in (APP_ROOT / "foundation" / "api").glob("routes_*.py")
    )
    assert "get_current_platform_account" not in source
    assert "get_current_user" in source


def test_b07_modules_import_independently():
    import app.foundation
    import app.platform

    assert app.foundation and app.platform


def test_b08_core_interfaces_are_protocols():
    for interface in (
        OrganizationProvisioningInterface,
        FollowUpQueryInterface,
        ProductCatalog,
    ):
        assert issubclass(interface, Protocol)
        assert getattr(interface, "_is_protocol", False)


def test_b09_operational_modules_do_not_import_platform():
    for module in ("commercial", "production", "quality", "shipping", "procurement", "masterdata", "workforce"):
        assert not {
            item
            for item in _imports(APP_ROOT / module)
            if item.startswith("app.platform")
        }


def test_b10_application_starts_and_bootstrap_status_responds(client):
    response = client.get("/api/v1/system/bootstrap/status")
    assert response.status_code == 200


def test_tenant_create_update_schemas_do_not_accept_organization_scope():
    modules = (
        "app.foundation.api.schemas",
        "app.commercial.api.schemas",
        "app.production.api.schemas",
        "app.quality.api.schemas",
        "app.shipping.api.schemas",
        "app.procurement.api.schemas",
        "app.masterdata.api.schemas",
        "app.quality.api.ncr_schemas",
        "app.workforce.api.schemas",
    )
    violations = []
    for module_name in modules:
        module = importlib.import_module(module_name)
        for name, schema in inspect.getmembers(module, inspect.isclass):
            if schema.__module__ != module_name:
                continue
            if "Create" not in name and "Update" not in name:
                continue
            fields = getattr(schema, "model_fields", {})
            forbidden = {"organization_id", "is_organization_root"}.intersection(fields)
            if forbidden:
                violations.append(f"{module_name}.{name}: {sorted(forbidden)}")
    assert violations == []


def test_b11_master_data_is_reached_only_through_core():
    """MD-001: master data imports no business module, none imports it; they ask core/interfaces/product_catalog."""
    operational = ("app.commercial", "app.production", "app.quality", "app.shipping", "app.procurement", "app.workforce", "app.foundation")
    assert not {item for item in _imports(APP_ROOT / "masterdata") if item.startswith(operational)}
    for module in ("commercial", "production", "quality", "shipping", "procurement", "workforce"):
        assert not {item for item in _imports(APP_ROOT / module) if item.startswith("app.masterdata")}, module
    # The platform's permission catalog and system roles read every module's permission codes (pure), as for the others.
    assert {item for item in _imports(APP_ROOT / "foundation") if item.startswith("app.masterdata")} <= {"app.masterdata.domain"}
    from app.masterdata.infrastructure import models

    tables = _model_tables(models)
    assert tables and all(table.startswith("masterdata_") for table in tables)
