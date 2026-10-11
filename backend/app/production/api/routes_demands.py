from datetime import date
from urllib.parse import quote
from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from fastapi.responses import JSONResponse, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.core.db import Base
from app.production.reporting import demand_export
from app.dependencies import get_current_tenant, get_db, get_customer_lookup, get_quote_lookup, require_permission, require_any_permission, permission_check
from app.production.domain import permissions as P
from app.production.domain.enums import ProductionDemandStatus
from app.production.api.demand_schemas import (
    CreateDemandRequest, DemandFromSalesOrderRequest, UpdateDemandRequest, CreateDemandItemRequest, UpdateDemandItemRequest,
    DemandResponse, DemandDetailResponse, DemandItemResponse, PaginatedDemandList,
    PaginatedPlanningList, DemandStatusRequest, ReorderRequest, PlanningFilters, SalesOrderLookup,
)
from app.production.application.demand_service import ProductionDemandService, DemandError


class DemandRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def handle(request):
            try:
                return await handler(request)
            except DemandError as exc:
                return JSONResponse(status_code=exc.status, content={"detail": {"code": exc.code}})
            except RequestValidationError:
                return JSONResponse(status_code=400, content={"detail": {"code": "invalid_request"}})
            except IntegrityError:
                return JSONResponse(status_code=409, content={"detail": {"code": "conflicting_data"}})
        return handle


router = APIRouter(route_class=DemandRoute, tags=["production-demands"])


def service(db=Depends(get_db), tenant=Depends(get_current_tenant), customers=Depends(get_customer_lookup), quotes=Depends(get_quote_lookup)):
    return ProductionDemandService(db, tenant, customers, quotes)


def allowed(action):
    return Depends(require_permission(P.code("demands", action)))


lookup_access = Depends(require_any_permission([P.DEMANDS_CREATE, P.DEMANDS_UPDATE, P.DEMANDS_READ, P.PLANNING_READ]))


@router.get("/demand-lookups/customers", dependencies=[lookup_access])
def customers(search: str = Query(default="", max_length=255), svc=Depends(service)):
    return [{"id": c.id, "code": c.customer_code, "name": c.customer_name} for c in svc.customers.find_customers(svc.db, svc.org_id, search)]


@router.get("/demand-lookups/quotes", dependencies=[lookup_access])
def quotes(customer_id: UUID, svc=Depends(service)):
    svc.validate_references(customer_id, None)
    return [{"id": q.id, "number": q.quote_number, "status": q.status} for q in svc.quotes.find_quotes(svc.db, customer_id, svc.org_id)]


@router.get("/demand-lookups/quotes/{quote_id}/items", response_model=list[CreateDemandItemRequest], dependencies=[Depends(require_any_permission([P.DEMANDS_CREATE, P.DEMANDS_UPDATE]))])
def quote_items(quote_id: UUID, customer_id: UUID, svc=Depends(service)):
    return svc.quote_items(customer_id, quote_id)


@router.get("/demand-lookups/sales-orders", response_model=list[SalesOrderLookup], dependencies=[lookup_access])
def sales_orders(customer_id: UUID, svc=Depends(service)):
    """The customer's confirmed sales orders that still have quantities for production, line by line."""
    return svc.sales_orders(customer_id)


@router.post("/demands/from-sales-order", response_model=DemandResponse, status_code=201, dependencies=[allowed("create")])
def create_from_sales_order(payload: DemandFromSalesOrderRequest, svc=Depends(service)):
    return svc.response(svc.create_from_sales_order(payload))


@router.post("/demands", response_model=DemandResponse, status_code=201, dependencies=[allowed("create")])
def create(payload: CreateDemandRequest, svc=Depends(service)):
    return svc.response(svc.create(payload))


@router.get("/demands", response_model=PaginatedDemandList, dependencies=[allowed("read")])
def list_demands(filters: PlanningFilters = Depends(), statuses: list[ProductionDemandStatus] = Query(default=[]), svc=Depends(service)):
    """`statuses` (repeatable) shows only those statuses; the screen hides fully planned and cancelled demands by default."""
    return svc.list(filters, statuses=list(dict.fromkeys(statuses)))


# Before /demands/{demand_id}, so "export.xlsx" is never read as an id.
@router.get("/demands/export.xlsx", dependencies=[allowed("read")])
def export_demands(filters: PlanningFilters = Depends(), statuses: list[ProductionDemandStatus] = Query(default=[]), svc=Depends(service)):
    """The demands the screen shows (same filters and order, every page) as a simple Arabic Excel sheet; built on request, never stored."""
    return _xlsx(demand_export.build(svc, filters, list(dict.fromkeys(statuses)), zone=_zone(svc)), "طلبات-العملاء")


@router.get("/demands/{demand_id}", response_model=DemandDetailResponse, dependencies=[allowed("read")])
def detail(demand_id: UUID, svc=Depends(service)):
    return svc.response(svc.get(demand_id), detail=True)


@router.patch("/demands/{demand_id}", response_model=DemandResponse, dependencies=[allowed("update")])
def update(demand_id: UUID, payload: UpdateDemandRequest, svc=Depends(service)):
    return svc.response(svc.update(demand_id, payload))


@router.delete("/demands/{demand_id}", dependencies=[allowed("delete")])
def delete(demand_id: UUID, svc=Depends(service)):
    svc.delete(demand_id)
    return {"message": "demand_deleted"}


@router.post("/demands/{demand_id}/items", response_model=DemandItemResponse, status_code=201, dependencies=[allowed("update")])
def add_item(demand_id: UUID, payload: CreateDemandItemRequest, svc=Depends(service)):
    return svc.add_item(demand_id, payload)


@router.patch("/demands/{demand_id}/items/{item_id}", response_model=DemandItemResponse, dependencies=[allowed("update")])
def update_item(demand_id: UUID, item_id: UUID, payload: UpdateDemandItemRequest, svc=Depends(service)):
    return svc.change_item(demand_id, item_id, payload)


@router.delete("/demands/{demand_id}/items/{item_id}", dependencies=[allowed("update")])
def delete_item(demand_id: UUID, item_id: UUID, svc=Depends(service)):
    svc.change_item(demand_id, item_id)
    return {"message": "item_deleted"}


@router.post("/demands/{demand_id}/import-quote-items", dependencies=[allowed("update")])
def import_items(demand_id: UUID, svc=Depends(service)):
    items = svc.import_quote_items(demand_id)
    return {"imported_count": len(items), "items": [DemandItemResponse.model_validate(i) for i in items]}


@router.post("/demands/{demand_id}/status", response_model=DemandResponse, dependencies=[Depends(require_any_permission([P.DEMANDS_RELEASE,P.DEMANDS_CANCEL]))])
def change_status(demand_id: UUID, payload: DemandStatusRequest, svc=Depends(service), can=Depends(permission_check)):
    required=P.DEMANDS_CANCEL if payload.status == 'cancelled' else P.DEMANDS_RELEASE
    if not can(required): raise HTTPException(403, 'Missing demand transition permission.')
    return svc.response(svc.update_status(demand_id, payload.status))


@router.get("/planning/demands/export.xlsx", dependencies=[Depends(require_permission(P.PLANNING_READ))])
def export_planning(filters: PlanningFilters = Depends(), statuses: list[ProductionDemandStatus] = Query(default=[]), svc=Depends(service)):
    """The planning queue as the screen shows it (same view, filters and order), as a simple Arabic Excel sheet."""
    return _xlsx(demand_export.build(svc, filters, list(dict.fromkeys(statuses)), planning=True, zone=_zone(svc)), "قائمة-التخطيط")


def _zone(svc):
    orgs = Base.metadata.tables["foundation_organizations"]
    return svc.db.scalar(select(orgs.c.timezone).where(orgs.c.id == svc.org_id)) or "UTC"


def _xlsx(content: bytes, name: str):
    filename = f"{name}-{date.today().isoformat()}.xlsx"
    return Response(content=content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename=\"demands-{date.today().isoformat()}.xlsx\"; filename*=UTF-8''{quote(filename)}"})


@router.get("/planning/demands", response_model=PaginatedPlanningList, dependencies=[Depends(require_permission(P.PLANNING_READ))])
def planning(filters: PlanningFilters = Depends(), statuses: list[ProductionDemandStatus] = Query(default=[]), svc=Depends(service)):
    """`statuses` narrows the view; with view=active (the default queue) it also reports what the queue hides."""
    return svc.list(filters, planning=True, statuses=list(dict.fromkeys(statuses)))


@router.post("/planning/demands/{demand_id}/reorder", dependencies=[Depends(require_permission(P.PLANNING_SEQUENCE))])
def reorder(demand_id: UUID, payload: ReorderRequest, svc=Depends(service)):
    return svc.reorder(demand_id, payload.new_position)
