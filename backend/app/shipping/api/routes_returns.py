"""Returns (SHIP-004): goods coming back after they left, each numbered (RT-…) against its delivery note.

Delivery returns are opened by a shipment's delivery outcome; customer returns are registered here. One permission
per action: approve (or reject), receive at the factory, cancel.
"""
from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.reporting.routes import generate_response
from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_current_user, get_db, permission_check, require_any_permission, require_permission
from app.core import files
from app.shipping.api.routes_shipments import attempt, send_file
from app.shipping.api.schemas import AttachmentRead, NoteInput, ReasonInput, ReceiveInput, ReturnCreate, ReturnListItem, ReturnRead
from app.shipping.application.attachment_service import AttachmentService
from app.shipping.application.return_service import ReturnService
from app.shipping.domain import permissions as P

router = APIRouter(tags=["shipping"])
PATH = "/returns"
# Whoever works on a return may add its photos and papers.
WORKS_ON_RETURNS = [P.RETURNS_CREATE, P.RETURNS_APPROVE, P.RETURNS_REJECT, P.RETURNS_RECEIVE]


def _read(service, found, can, detail=True):
    model = ReturnRead if detail else ReturnListItem
    return model.model_validate({**model.model_validate(found).model_dump(), **service.views([found], can, detail)[0]})


def _run(db, tenant, can, action):
    service = ReturnService(db, tenant)
    return attempt(db, lambda: _read(service, action(service), can))


@router.get(PATH, response_model=list[ReturnListItem], dependencies=[Depends(require_permission(P.RETURNS_READ))])
def list_returns(status_filter: str | None = Query(default=None, alias="status", pattern="^(requested|approved|rejected|received|cancelled)$"),
                 kind: str | None = Query(default=None, pattern="^(delivery|customer)$"), shipment_id: UUID | None = None,
                 customer_id: UUID | None = None, date_from: date | None = None, date_to: date | None = None,
                 search: str | None = Query(default=None, max_length=60), tenant: TenantContext = Depends(get_current_tenant),
                 db: Session = Depends(get_db), can=Depends(permission_check)):
    service = ReturnService(db, tenant)
    rows = service.list(status_filter, kind, shipment_id, customer_id, date_from, date_to + timedelta(days=1) if date_to else None, search)
    return [ReturnListItem.model_validate({**ReturnListItem.model_validate(r).model_dump(), **v}) for r, v in zip(rows, service.views(rows, can))]


@router.post(PATH, response_model=ReturnRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission(P.RETURNS_CREATE))])
def create_return(payload: ReturnCreate, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                  can=Depends(permission_check)):
    """A customer returns (some of) what a delivered note brought: at most what was delivered less earlier returns."""
    return _run(db, tenant, can, lambda s: s.create(payload))


@router.get(f"{PATH}/{{return_id}}", response_model=ReturnRead, dependencies=[Depends(require_permission(P.RETURNS_READ))])
def get_return(return_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
    return _run(db, tenant, can, lambda s: s.get(return_id))


@router.post(f"{PATH}/{{return_id}}/approve", response_model=ReturnRead, dependencies=[Depends(require_permission(P.RETURNS_APPROVE))])
def approve_return(return_id: UUID, payload: NoteInput, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                   can=Depends(permission_check)):
    """Accepted: the goods may come back. A late return (after the return window) needs a note."""
    return _run(db, tenant, can, lambda s: s.approve(return_id, payload.note))


@router.post(f"{PATH}/{{return_id}}/reject", response_model=ReturnRead, dependencies=[Depends(require_permission(P.RETURNS_REJECT))])
def reject_return(return_id: UUID, payload: ReasonInput, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                  can=Depends(permission_check)):
    return _run(db, tenant, can, lambda s: s.reject(return_id, payload.reason))


@router.post(f"{PATH}/{{return_id}}/receive", response_model=ReturnRead, dependencies=[Depends(require_permission(P.RETURNS_RECEIVE))])
def receive_return(return_id: UUID, payload: ReceiveInput, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                   can=Depends(permission_check)):
    """The goods are back at the factory: what actually arrived, line by line."""
    return _run(db, tenant, can, lambda s: s.receive(return_id, payload))


@router.post(f"{PATH}/{{return_id}}/cancel", response_model=ReturnRead, dependencies=[Depends(require_permission(P.RETURNS_CANCEL))])
def cancel_return(return_id: UUID, payload: ReasonInput, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                  can=Depends(permission_check)):
    """A customer's return withdrawn before its goods arrived."""
    return _run(db, tenant, can, lambda s: s.cancel(return_id, payload.reason))


@router.get(f"{PATH}/{{return_id}}/document.pdf", dependencies=[Depends(require_permission(P.RETURNS_READ))])
def return_note(return_id: UUID, lang: str = Query("ar", pattern="^(ar|en)$"), current=Depends(get_current_user), db: Session = Depends(get_db)):
    """The return note as a PDF with the company's external identity."""
    return generate_response("shipping.return_note", dict(return_id=str(return_id), lang=lang), "pdf", current, db)


@router.post(f"{PATH}/{{return_id}}/attachments", response_model=list[AttachmentRead], status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_any_permission(WORKS_ON_RETURNS))])
async def upload_return_attachment(return_id: UUID, kind: str = Form("photo"), file: UploadFile = File(...),
                                   tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    """Photos of the returned goods, or the customer's papers: an image or a PDF, 10 MB at most."""
    content = await file.read(files.read_limit('attachment'))
    return attempt(db, lambda: AttachmentService(db, tenant).add_to_return(return_id, kind, file.filename, content))


@router.get(f"{PATH}/{{return_id}}/attachments/{{attachment_id}}", dependencies=[Depends(require_permission(P.RETURNS_READ))])
def return_attachment(return_id: UUID, attachment_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    return send_file(attempt(db, lambda: AttachmentService(db, tenant).file(attachment_id, return_id=return_id)))


@router.delete(f"{PATH}/{{return_id}}/attachments/{{attachment_id}}", response_model=list[AttachmentRead],
               dependencies=[Depends(require_any_permission(WORKS_ON_RETURNS))])
def remove_return_attachment(return_id: UUID, attachment_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    return attempt(db, lambda: AttachmentService(db, tenant).remove(attachment_id, return_id=return_id))
