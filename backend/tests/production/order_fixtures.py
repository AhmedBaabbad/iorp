"""Historical standalone orders for execution/CRUD regression fixtures.

Public creation is allocation-only; execution tests may still exercise historical
orders without demand provenance. Planning creation is covered by API tests.
"""
from uuid import UUID
import httpx
from app.main import app
from app.dependencies import get_db
from app.core.tenancy import TenantContext
from app.core.security import decode_access_token
from app.foundation.infrastructure.models import User
from app.production.api.schemas import ProductionOrderCreate, ProductionOrderRead
from app.production.application.services import ProductionOrderService


def historical_order(client, auth_headers, payload):
    dependency = app.dependency_overrides[get_db]()
    db = next(dependency)
    try:
        claims = decode_access_token(auth_headers["Authorization"].split(" ", 1)[1])
        user = db.get(User, UUID(claims["sub"]))
        order = ProductionOrderService(db).create_production_order(TenantContext(user.id, user.organization_id), ProductionOrderCreate(**payload))
        return httpx.Response(201, json=ProductionOrderRead.model_validate(order).model_dump(mode="json"))
    finally:
        dependency.close()
