"""Shipments and delivery notes (SHIP-001, SHIP-004): one permission per action; lifecycle steps are explicit endpoints."""
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.reporting.routes import generate_response
from app.core.tenancy import TenantContext
from app.dependencies import (get_current_tenant, get_current_user, get_db, permission_check, require_any_permission,
                              require_permission)
from app.shipping.api.schemas import (AttachmentRead, CustomerOption, DeliverInput, DispatchInput, FailInput, ProductionOrderOption,
                                      ReasonInput, RescheduleInput, SettingsRead, SettingsUpdate, ShipmentCreate, ShipmentListItem,
                                      ShipmentRead, ShipmentUpdate)
from app.shipping.application.attachment_service import AttachmentService
from app.shipping.application.shipment_service import ShipmentService
from app.shipping.domain import permissions as P
from app.shipping.domain.rules import ShippingError

router = APIRouter(tags=["shipping"])
PATH = "/shipments"
STATUSES = "^(draft|ready|dispatched|delivered|partially_delivered|returned|not_delivered|cancelled)$"
UPLOAD_LIMIT = 10 * 1024 * 1024 + 1


def _error(exc: ShippingError):
    return HTTPException(status_code=exc.status, detail={"code": exc.code, **exc.detail})


def attempt(db, action):
    """Run a service call, answering a shipping error as {"code": ...}."""
    try:
        return action()
    except ShippingError as exc:
        db.rollback()
        raise _error(exc) from exc


def send_file(found):
    path, content_type, name = found
    return FileResponse(path, media_type=content_type, filename=name, content_disposition_type="inline")


def _read(service, shipment, can, detail=True):
    model = ShipmentRead if detail else ShipmentListItem
    return model.model_validate({**model.model_validate(shipment).model_dump(), **service.views([shipment], can, detail)[0]})


def _run(db, tenant, can, action):
    service = ShipmentService(db, tenant)
    try:
        return _read(service, action(service), can)
    except ShippingError as exc:
        db.rollback()
        raise _error(exc) from exc


@router.get(PATH, response_model=list[ShipmentListItem], dependencies=[Depends(require_permission(P.SHIPMENTS_READ))])
def list_shipments(status_filter: str | None = Query(default=None, alias="status", pattern=STATUSES),
                   method: str | None = Query(default=None, pattern="^(pickup|factory_delivery|carrier)$"), customer_id: UUID | None = None,
                   date_from: date | None = None, date_to: date | None = None, search: str | None = Query(default=None, max_length=60),
                   tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
    service = ShipmentService(db, tenant)
    rows = service.list(status_filter, method, customer_id, date_from, date_to, search)
    return [ShipmentListItem.model_validate({**ShipmentListItem.model_validate(s).model_dump(), **v}) for s, v in zip(rows, service.views(rows, can))]


@router.get(f"{PATH}/lookups/customers", response_model=list[CustomerOption],
            dependencies=[Depends(require_any_permission([P.SHIPMENTS_CREATE, P.SHIPMENTS_UPDATE]))])
def customer_options(q: str = Query(default="", max_length=60), tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    """Registered customers to ship to, with the contacts a delivery note copies (name, phone, email, city)."""
    return ShipmentService(db, tenant).customer_options(q)


@router.get(f"{PATH}/lookups/production-orders", response_model=list[ProductionOrderOption],
            dependencies=[Depends(require_any_permission([P.SHIPMENTS_CREATE, P.SHIPMENTS_UPDATE]))])
def production_order_options(q: str = Query(default="", max_length=60), tenant: TenantContext = Depends(get_current_tenant),
                             db: Session = Depends(get_db)):
    """Production orders a line may come from (its batch), newest first; drafts and cancelled ones are left out."""
    return ShipmentService(db, tenant).production_order_options(q)


@router.post(PATH, response_model=ShipmentRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission(P.SHIPMENTS_CREATE))])
def create_shipment(payload: ShipmentCreate, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                    can=Depends(permission_check)):
    """A draft delivery note (numbered DN-YYYY-NNNN) for a registered or a named customer."""
    return _run(db, tenant, can, lambda s: s.create(payload))


@router.get(f"{PATH}/{{shipment_id}}", response_model=ShipmentRead, dependencies=[Depends(require_permission(P.SHIPMENTS_READ))])
def get_shipment(shipment_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
    return _run(db, tenant, can, lambda s: s.get(shipment_id))


@router.patch(f"{PATH}/{{shipment_id}}", response_model=ShipmentRead, dependencies=[Depends(require_permission(P.SHIPMENTS_UPDATE))])
def update_shipment(shipment_id: UUID, payload: ShipmentUpdate, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                    can=Depends(permission_check)):
    """A draft only; the lines, when given, replace the current ones."""
    return _run(db, tenant, can, lambda s: s.update(shipment_id, payload))


@router.post(f"{PATH}/{{shipment_id}}/ready", response_model=ShipmentRead, dependencies=[Depends(require_permission(P.SHIPMENTS_UPDATE))])
def ready_shipment(shipment_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
    """Complete and ready for loading: needs the customer, at least one line and the delivery method's details."""
    return _run(db, tenant, can, lambda s: s.ready(shipment_id))


@router.post(f"{PATH}/{{shipment_id}}/reopen", response_model=ShipmentRead, dependencies=[Depends(require_permission(P.SHIPMENTS_UPDATE))])
def reopen_shipment(shipment_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
    return _run(db, tenant, can, lambda s: s.reopen(shipment_id))


@router.post(f"{PATH}/{{shipment_id}}/dispatch", response_model=ShipmentRead, dependencies=[Depends(require_permission(P.SHIPMENTS_DISPATCH))])
def dispatch_shipment(shipment_id: UUID, payload: DispatchInput | None = None, tenant: TenantContext = Depends(get_current_tenant),
                      db: Session = Depends(get_db), can=Depends(permission_check)):
    """The goods left the factory (factory delivery or carrier), with the gate weighbridge reading when there is one."""
    return _run(db, tenant, can, lambda s: s.dispatch(shipment_id, payload))


@router.post(f"{PATH}/{{shipment_id}}/deliver", response_model=ShipmentRead, dependencies=[Depends(require_permission(P.SHIPMENTS_DELIVER))])
def deliver_shipment(shipment_id: UUID, payload: DeliverInput, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                     can=Depends(permission_check)):
    """Received by the customer (or collected at the factory for a pickup), in full or in part: a refused part opens a
    delivery return (RT-…) for the goods coming back."""
    return _run(db, tenant, can, lambda s: s.deliver(shipment_id, payload))


@router.post(f"{PATH}/{{shipment_id}}/fail", response_model=ShipmentRead, dependencies=[Depends(require_permission(P.SHIPMENTS_DELIVER))])
def fail_shipment(shipment_id: UUID, payload: FailInput, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                  can=Depends(permission_check)):
    """Not received: the load comes back to the factory under a delivery return."""
    return _run(db, tenant, can, lambda s: s.fail(shipment_id, payload))


@router.post(f"{PATH}/{{shipment_id}}/reschedule", response_model=ShipmentRead, dependencies=[Depends(require_permission(P.SHIPMENTS_UPDATE))])
def reschedule_shipment(shipment_id: UUID, payload: RescheduleInput | None = None, tenant: TenantContext = Depends(get_current_tenant),
                        db: Session = Depends(get_db), can=Depends(permission_check)):
    """A returned note, its goods back at the factory, sets out again under the same number (next attempt)."""
    return _run(db, tenant, can, lambda s: s.reschedule(shipment_id, payload or RescheduleInput()))


@router.post(f"{PATH}/{{shipment_id}}/close", response_model=ShipmentRead, dependencies=[Depends(require_permission(P.SHIPMENTS_CANCEL))])
def close_shipment(shipment_id: UUID, payload: ReasonInput, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                   can=Depends(permission_check)):
    """Not delivered after all: a returned (or rescheduled, not yet left) note is closed."""
    return _run(db, tenant, can, lambda s: s.close(shipment_id, payload.reason))


@router.post(f"{PATH}/{{shipment_id}}/cancel", response_model=ShipmentRead, dependencies=[Depends(require_permission(P.SHIPMENTS_CANCEL))])
def cancel_shipment(shipment_id: UUID, payload: ReasonInput, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                    can=Depends(permission_check)):
    return _run(db, tenant, can, lambda s: s.cancel(shipment_id, payload.reason))


@router.get(f"{PATH}/{{shipment_id}}/document.pdf", dependencies=[Depends(require_permission(P.SHIPMENTS_READ))])
def delivery_note(shipment_id: UUID, lang: str = Query("ar", pattern="^(ar|en)$"), current=Depends(get_current_user), db: Session = Depends(get_db)):
    """The delivery note as a PDF with the company's external identity."""
    return generate_response("shipping.delivery_note", dict(shipment_id=str(shipment_id), lang=lang), "pdf", current, db)


@router.post(f"{PATH}/{{shipment_id}}/attachments", response_model=list[AttachmentRead], status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_permission(P.SHIPMENTS_DELIVER))])
async def upload_shipment_attachment(shipment_id: UUID, kind: str = Form("proof_of_delivery"), file: UploadFile = File(...),
                                     tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    """The signed delivery note (proof of delivery) or another document: an image or a PDF, 10 MB at most."""
    content = await file.read(UPLOAD_LIMIT)
    return attempt(db, lambda: AttachmentService(db, tenant).add_to_shipment(shipment_id, kind, file.filename, content))


@router.get(f"{PATH}/{{shipment_id}}/attachments/{{attachment_id}}", dependencies=[Depends(require_permission(P.SHIPMENTS_READ))])
def shipment_attachment(shipment_id: UUID, attachment_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    return send_file(attempt(db, lambda: AttachmentService(db, tenant).file(attachment_id, shipment_id=shipment_id)))


@router.delete(f"{PATH}/{{shipment_id}}/attachments/{{attachment_id}}", response_model=list[AttachmentRead],
               dependencies=[Depends(require_permission(P.SHIPMENTS_DELIVER))])
def remove_shipment_attachment(shipment_id: UUID, attachment_id: UUID, tenant: TenantContext = Depends(get_current_tenant),
                               db: Session = Depends(get_db)):
    return attempt(db, lambda: AttachmentService(db, tenant).remove(attachment_id, shipment_id=shipment_id))


@router.get("/settings", response_model=SettingsRead, dependencies=[Depends(require_permission(P.SHIPMENTS_READ))])
def read_settings(tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    return ShipmentService(db, tenant).settings()


@router.patch("/settings", response_model=SettingsRead, dependencies=[Depends(require_permission(P.SETTINGS_UPDATE))])
def update_settings(payload: SettingsUpdate, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    """Number prefixes (DN- and RT- by default; numbers already issued keep theirs), the return window in days after
    delivery, and the weight tolerance (%) between what left and what was received."""
    return ShipmentService(db, tenant).update_settings(payload)
