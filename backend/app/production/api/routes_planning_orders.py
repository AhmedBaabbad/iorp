from uuid import UUID
from fastapi import APIRouter, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from app.dependencies import get_current_tenant, get_db, get_customer_lookup, require_permission
from app.production.api.planning_schemas import PlanningOrderCreate, PlanningOrderRead, ReleaseRequest
from app.production.application.allocation_service import AllocationLifecycleService, demand_quantity_summary
from app.production.application.planning_order_service import PlanningOrderService, order_response
from app.production.application.services import ProductionOrderService
from app.production.domain.compatibility import AllocationError, DemandItemCompatibilityChecker


class PlanningRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def handle(request):
            try:
                return await handler(request)
            except AllocationError as exc:
                return JSONResponse(status_code=exc.status, content={"detail": {"code": exc.code, **exc.detail}})
            except RequestValidationError:
                return JSONResponse(status_code=400, content={"detail": {"code": "INVALID_ALLOCATION_REQUEST"}})
        return handle


router = APIRouter(route_class=PlanningRoute, tags=["production-planning"])


def compatibility_checker():
    return DemandItemCompatibilityChecker()


@router.post("/planning/create-production-order", status_code=201, response_model=PlanningOrderRead,
    dependencies=[Depends(require_permission("production:planning:allocate")), Depends(require_permission("production:orders:create"))])
def create(payload: PlanningOrderCreate, db=Depends(get_db), tenant=Depends(get_current_tenant),
           customers=Depends(get_customer_lookup), checker=Depends(compatibility_checker)):
    order = PlanningOrderService(db, tenant, checker).create_order_from_planning(payload)
    return order_response(order, db, tenant, customers)


@router.get("/orders/{order_id}", response_model=PlanningOrderRead,
    dependencies=[Depends(require_permission("production:production_orders:read"))])
def detail(order_id: UUID, db=Depends(get_db), tenant=Depends(get_current_tenant), customers=Depends(get_customer_lookup)):
    order = ProductionOrderService(db).get_production_order(tenant, order_id)
    if order is None:
        raise AllocationError("PRODUCTION_ORDER_NOT_FOUND", 404)
    return order_response(order, db, tenant, customers)


@router.post("/allocations/{allocation_id}/release",
    dependencies=[Depends(require_permission("production:planning:release_allocation"))])
def release_allocation(allocation_id: UUID, payload: ReleaseRequest, db=Depends(get_db), tenant=Depends(get_current_tenant)):
    allocation = AllocationLifecycleService(db, tenant).release_allocation(allocation_id, payload.reason)
    return {
        "allocation": dict(id=allocation.id, production_order_id=allocation.production_order_id,
            production_order_number=allocation.production_order_number, production_demand_id=allocation.production_demand_id,
            production_demand_item_id=allocation.production_demand_item_id, allocated_quantity=allocation.allocated_quantity,
            unit=allocation.unit, status=allocation.status, created_at=allocation.created_at, created_by_user_id=allocation.created_by_user_id,
            released_at=allocation.released_at, released_by_user_id=allocation.released_by_user_id, release_reason=allocation.release_reason),
        "demand": demand_quantity_summary(allocation.demand),
    }
