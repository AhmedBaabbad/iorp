"""Non-conformance reports (QUAL-NCR-002): one permission per step; stages are explicit endpoints."""
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.pagination import Page, PageParams, page_of, page_params
from app.core.reporting.routes import generate_response
from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_current_user, get_db, permission_check, require_any_permission, require_permission
from app.quality.api.ncr_schemas import (ActionInput, ActionRead, ActionUpdate, Alerts, AttachmentRead, ContainInput, EvidenceInput,
                                         InvestigateInput, ItemInput, ItemUpdate, NCRCreate, NCRListItem, NCRRead, NCRUpdate, ReasonInput, ReviewInput,
                                         SupplierOption, UserOption, VerifyInput)
from app.quality.application.ncr_service import NCRService
from app.quality.domain import permissions as Q
from app.quality.domain.enums import NCRSourceType
from app.quality.domain.rules import QualityError

router = APIRouter(tags=["non-conformance-reports"])
PATH = "/non-conformance-reports"
STATUSES = "^(open|investigation|action|verification|closed|cancelled)$"
UPLOAD_LIMIT = 10 * 1024 * 1024 + 1


def _error(exc: QualityError):
    return HTTPException(status_code=exc.status, detail={"code": exc.code, **exc.detail})


def _attempt(db, action):
    try:
        return action()
    except QualityError as exc:
        db.rollback()
        raise _error(exc) from exc


def _read(service, report, can):
    return NCRRead.model_validate({**NCRRead.model_validate(report).model_dump(), **service.views([report], can, detail=True)[0]})


def _run(db, tenant, can, action):
    service = NCRService(db, tenant)
    return _attempt(db, lambda: _read(service, action(service), can))


@router.get(PATH, response_model=Page[NCRListItem], dependencies=[Depends(require_permission(Q.NCR_READ))])
def list_reports(status_filter: str | None = Query(default=None, alias="status", pattern=STATUSES), source_type: NCRSourceType | None = None,
                 severity: str | None = Query(default=None, pattern="^(minor|major|critical)$"), owner_user_id: UUID | None = None,
                 open_only: bool = False, date_from: date | None = None, date_to: date | None = None,
                 search: str | None = Query(default=None, max_length=60), params: PageParams = Depends(page_params),
                 tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
    service = NCRService(db, tenant)
    rows, total = service.list(params, status=status_filter, source_type=source_type, severity=severity, owner_user_id=owner_user_id,
                               open_only=open_only, date_from=date_from, date_to=date_to, search=search)
    return page_of([NCRListItem.model_validate({**NCRListItem.model_validate(r).model_dump(), **v}) for r, v in zip(rows, service.views(rows, can))],
                   total, params)


@router.post(PATH, response_model=NCRRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission(Q.NCR_CREATE))])
def create_report(payload: NCRCreate, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                  can=Depends(permission_check)):
    """A new report (NCR-YYYY-NNNN), open, with what it affects."""
    return _run(db, tenant, can, lambda s: s.create(payload))


@router.get(f"{PATH}/lookups/users", response_model=list[UserOption],
            dependencies=[Depends(require_any_permission([Q.NCR_CREATE, Q.NCR_UPDATE]))])
def user_options(q: str = Query(default="", max_length=60), tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    """The organization's users, to own a report or a corrective action."""
    return NCRService(db, tenant).user_options(q)


@router.get(f"{PATH}/lookups/suppliers", response_model=list[SupplierOption],
            dependencies=[Depends(require_any_permission([Q.NCR_CREATE, Q.NCR_UPDATE]))])
def supplier_options(q: str = Query(default="", max_length=60), tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    """The organization's registered suppliers (procurement), to name the one a report is about."""
    return NCRService(db, tenant).supplier_options(q)


@router.get(f"{PATH}/{{report_id}}", response_model=NCRRead, dependencies=[Depends(require_permission(Q.NCR_READ))])
def get_report(report_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
    return _run(db, tenant, can, lambda s: s.get(report_id))


@router.patch(f"{PATH}/{{report_id}}", response_model=NCRRead, dependencies=[Depends(require_permission(Q.NCR_UPDATE))])
def update_report(report_id: UUID, payload: NCRUpdate, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                  can=Depends(permission_check)):
    """Its details, source, owner, due date, the action with the supplier, and costs — until it is closed or cancelled."""
    return _run(db, tenant, can, lambda s: s.update(report_id, payload))


@router.get(f"{PATH}/{{report_id}}/document.pdf", dependencies=[Depends(require_permission(Q.NCR_READ))])
def ncr_document(report_id: UUID, lang: str = Query("ar", pattern="^(ar|en)$"), current=Depends(get_current_user), db: Session = Depends(get_db)):
    """The report as a PDF with the company's identity (it can be sent to a supplier)."""
    return generate_response("quality.ncr", dict(report_id=str(report_id), lang=lang), "pdf", current, db)


# ── items ────────────────────────────────────────────────────────────────────────────────────────
@router.post(f"{PATH}/{{report_id}}/items", response_model=NCRRead, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_permission(Q.NCR_UPDATE))])
def add_item(report_id: UUID, payload: ItemInput, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
             can=Depends(permission_check)):
    return _run(db, tenant, can, lambda s: s.add_item(report_id, payload))


@router.patch(f"{PATH}/{{report_id}}/items/{{item_id}}", response_model=NCRRead, dependencies=[Depends(require_permission(Q.NCR_UPDATE))])
def update_item(report_id: UUID, item_id: UUID, payload: ItemUpdate, tenant: TenantContext = Depends(get_current_tenant),
                db: Session = Depends(get_db), can=Depends(permission_check)):
    """Its quantity, the decision on it (return to supplier, use as is, sort, rework, regrade, recycle, scrap, hold)…"""
    return _run(db, tenant, can, lambda s: s.update_item(report_id, item_id, payload))


@router.delete(f"{PATH}/{{report_id}}/items/{{item_id}}", response_model=NCRRead, dependencies=[Depends(require_permission(Q.NCR_UPDATE))])
def remove_item(report_id: UUID, item_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                can=Depends(permission_check)):
    return _run(db, tenant, can, lambda s: s.remove_item(report_id, item_id))


# ── stages ───────────────────────────────────────────────────────────────────────────────────────
@router.post(f"{PATH}/{{report_id}}/contain", response_model=NCRRead, dependencies=[Depends(require_permission(Q.NCR_CONTAIN))])
def contain(report_id: UUID, payload: ContainInput, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
            can=Depends(permission_check)):
    """What was done at once to stop it spreading; the investigation starts."""
    return _run(db, tenant, can, lambda s: s.contain(report_id, payload.containment))


@router.post(f"{PATH}/{{report_id}}/investigate", response_model=NCRRead, dependencies=[Depends(require_permission(Q.NCR_INVESTIGATE))])
def investigate(report_id: UUID, payload: InvestigateInput, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                can=Depends(permission_check)):
    """The root cause; then corrective actions, or closed when none is needed (with the reason)."""
    return _run(db, tenant, can, lambda s: s.investigate(report_id, payload))


@router.post(f"{PATH}/{{report_id}}/submit", response_model=NCRRead, dependencies=[Depends(require_permission(Q.NCR_SUBMIT))])
def submit(report_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
    """Every action finished: the report goes to verification."""
    return _run(db, tenant, can, lambda s: s.submit(report_id))


@router.post(f"{PATH}/{{report_id}}/verify", response_model=NCRRead, dependencies=[Depends(require_permission(Q.NCR_VERIFY))])
def verify(report_id: UUID, payload: VerifyInput, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
           can=Depends(permission_check)):
    """Effective: closed (and reviewed again after review_days). Not effective (why): back to corrective actions."""
    return _run(db, tenant, can, lambda s: s.verify(report_id, payload.effective, payload.notes, payload.review_days))


@router.post(f"{PATH}/{{report_id}}/review-effectiveness", response_model=NCRRead, dependencies=[Depends(require_permission(Q.NCR_VERIFY))])
def review_effectiveness(report_id: UUID, payload: ReviewInput, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                         can=Depends(permission_check)):
    """Some time after closing: the problem did not come back (effective), or it did (why) and the report reopens to its actions."""
    return _run(db, tenant, can, lambda s: s.review_effectiveness(report_id, payload.effective, payload.notes))


@router.post(f"{PATH}/{{report_id}}/cancel", response_model=NCRRead, dependencies=[Depends(require_permission(Q.NCR_CANCEL))])
def cancel(report_id: UUID, payload: ReasonInput, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
           can=Depends(permission_check)):
    return _run(db, tenant, can, lambda s: s.cancel(report_id, payload.reason))


# ── corrective actions ───────────────────────────────────────────────────────────────────────────
@router.post(f"{PATH}/{{report_id}}/actions", response_model=NCRRead, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_permission(Q.NCR_UPDATE))])
def add_action(report_id: UUID, payload: ActionInput, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
               can=Depends(permission_check)):
    return _run(db, tenant, can, lambda s: s.add_action(report_id, payload))


@router.patch(f"{PATH}/{{report_id}}/actions/{{action_id}}", response_model=NCRRead, dependencies=[Depends(require_permission(Q.NCR_UPDATE))])
def update_action(report_id: UUID, action_id: UUID, payload: ActionUpdate, tenant: TenantContext = Depends(get_current_tenant),
                  db: Session = Depends(get_db), can=Depends(permission_check)):
    return _run(db, tenant, can, lambda s: s.update_action(report_id, action_id, payload))


@router.post(f"{PATH}/{{report_id}}/actions/{{action_id}}/complete", response_model=NCRRead,
             dependencies=[Depends(require_permission(Q.NCR_ACTIONS_COMPLETE))])
def complete_action(report_id: UUID, action_id: UUID, payload: EvidenceInput, tenant: TenantContext = Depends(get_current_tenant),
                    db: Session = Depends(get_db), can=Depends(permission_check)):
    """Done, with the evidence (what was changed, where it can be seen)."""
    return _run(db, tenant, can, lambda s: s.complete_action(report_id, action_id, payload.evidence))


@router.post(f"{PATH}/{{report_id}}/actions/{{action_id}}/cancel", response_model=NCRRead, dependencies=[Depends(require_permission(Q.NCR_CANCEL))])
def cancel_action(report_id: UUID, action_id: UUID, payload: ReasonInput, tenant: TenantContext = Depends(get_current_tenant),
                  db: Session = Depends(get_db), can=Depends(permission_check)):
    return _run(db, tenant, can, lambda s: s.cancel_action(report_id, action_id, payload.reason))


@router.get("/ncr-actions/alerts", response_model=Alerts, dependencies=[Depends(require_any_permission([Q.NCR_ACTIONS_READ, Q.NCR_READ]))])
def alerts(tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
    """What needs the current user's attention: their actions late or due soon, their reports past due, reviews due."""
    return NCRService(db, tenant).alerts(can)


@router.get("/ncr-actions", response_model=Page[ActionRead], dependencies=[Depends(require_any_permission([Q.NCR_ACTIONS_READ, Q.NCR_READ]))])
def all_actions(status_filter: str | None = Query(default=None, alias="status", pattern="^(open|done|cancelled)$"), mine: bool = False,
                overdue: bool = False, search: str | None = Query(default=None, max_length=60), params: PageParams = Depends(page_params),
                tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    """Corrective actions across reports: what is open, whose, and what is late (one page, ARCH-PAGE-001)."""
    rows, total = NCRService(db, tenant).all_actions(params, status=status_filter, owner_user_id=tenant.user_id if mine else None,
                                                     overdue=overdue, search=search)
    return page_of(rows, total, params)


# ── files ────────────────────────────────────────────────────────────────────────────────────────
@router.post(f"{PATH}/{{report_id}}/attachments", response_model=list[AttachmentRead], status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_any_permission([Q.NCR_CREATE, Q.NCR_UPDATE]))])
async def upload_attachment(report_id: UUID, file: UploadFile = File(...), tenant: TenantContext = Depends(get_current_tenant),
                            db: Session = Depends(get_db)):
    """A photo or a document (an image or a PDF, 10 MB at most)."""
    content = await file.read(UPLOAD_LIMIT)
    return _attempt(db, lambda: NCRService(db, tenant).add_attachment(report_id, file.filename, content))


@router.get(f"{PATH}/{{report_id}}/attachments/{{attachment_id}}", dependencies=[Depends(require_permission(Q.NCR_READ))])
def attachment(report_id: UUID, attachment_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    path, content_type, name = _attempt(db, lambda: NCRService(db, tenant).attachment_file(report_id, attachment_id))
    return FileResponse(path, media_type=content_type, filename=name, content_disposition_type="inline")


@router.delete(f"{PATH}/{{report_id}}/attachments/{{attachment_id}}", response_model=list[AttachmentRead],
               dependencies=[Depends(require_permission(Q.NCR_UPDATE))])
def remove_attachment(report_id: UUID, attachment_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    return _attempt(db, lambda: NCRService(db, tenant).remove_attachment(report_id, attachment_id))
