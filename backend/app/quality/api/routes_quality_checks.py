"""Quality checks (QUAL-001): one permission per action; lifecycle actions are explicit endpoints."""
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.pagination import Page, PageParams, page_of, page_params
from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db, permission_check, require_any_permission, require_permission
from app.quality.api.inspection_schemas import (
    InspectableOrder, MeasurementInput, PlanCandidate, PlanInput, QualityCheckClose, QualityCheckCreate, QualityCheckListItem, QualityCheckRead, QualityCheckUpdate,
    ReasonInput, SampleOption,
)
from app.quality.application.measurement_service import MeasurementService
from app.quality.application.check_service import QualityCheckService
from app.quality.domain import permissions as Q
from app.quality.domain.enums import DefectCategory, QualityCheckResult, QualityCheckStatus, QualityCheckType
from app.quality.domain.rules import QualityError

router = APIRouter(prefix="/quality-checks", tags=["quality-checks"])


def _error(exc: QualityError):
    return HTTPException(status_code=exc.status, detail={"code": exc.code, **exc.detail})


def _read(service, check, can):
    # Validated as a whole, so the nested history and rejection rows are typed.
    return QualityCheckRead.model_validate({**QualityCheckRead.model_validate(check).model_dump(), **service.views([check], can, detail=True)[0]})


@router.post("", response_model=QualityCheckRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission(Q.CHECKS_CREATE))])
def create_quality_check(payload: QualityCheckCreate, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                         can=Depends(permission_check)):
    """Opens an inspection (code QI-YYYY-NNNN). Production lots need a running, held or completed order."""
    service = QualityCheckService(db, tenant)
    try:
        return _read(service, service.create(payload), can)
    except QualityError as exc:
        raise _error(exc) from exc


@router.get("", response_model=Page[QualityCheckListItem], dependencies=[Depends(require_permission(Q.CHECKS_READ))])
def list_quality_checks(
    production_order_id: UUID | None = Query(default=None), check_type: QualityCheckType | None = Query(default=None),
    status_filter: QualityCheckStatus | None = Query(default=None, alias="status"), result: QualityCheckResult | None = Query(default=None),
    date_from: date | None = Query(default=None), date_to: date | None = Query(default=None), search: str | None = Query(default=None, max_length=60),
    defect_category: DefectCategory | None = Query(default=None), params: PageParams = Depends(page_params),
    tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check),
):
    service = QualityCheckService(db, tenant)
    checks, total = service.list(params, production_order_id=production_order_id, check_type=check_type, status=status_filter, result=result,
                                 date_from=date_from, date_to=date_to, search=search, defect_category=defect_category)
    return page_of([QualityCheckListItem.model_validate(c).model_copy(update=v) for c, v in zip(checks, service.views(checks, can))], total, params)


# Lookups before /{check_id}: the orders and samples a check may be opened on.
@router.get("/lookups/orders", response_model=list[InspectableOrder],
            dependencies=[Depends(require_any_permission([Q.CHECKS_CREATE, Q.REJECTIONS_CREATE]))])
def inspectable_orders(q: str = Query(default="", max_length=60), check_type: QualityCheckType | None = None,
                       tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    """Orders a check of this type can be opened on; a reinspection also lists closed orders."""
    return QualityCheckService(db, tenant).inspectable_orders(q, check_type)


@router.get("/lookups/samples", response_model=list[SampleOption], dependencies=[Depends(require_permission(Q.CHECKS_CREATE))])
def inspectable_samples(q: str = Query(default="", max_length=60), tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    return QualityCheckService(db, tenant).samples(q)


@router.get("/{check_id}", response_model=QualityCheckRead, dependencies=[Depends(require_permission(Q.CHECKS_READ))])
def get_quality_check(check_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
    service = QualityCheckService(db, tenant)
    try:
        return _read(service, service.get(check_id), can)
    except QualityError as exc:
        raise _error(exc) from exc


@router.patch("/{check_id}", response_model=QualityCheckRead, dependencies=[Depends(require_permission(Q.CHECKS_UPDATE))])
def update_quality_check(check_id: UUID, payload: QualityCheckUpdate, tenant: TenantContext = Depends(get_current_tenant),
                         db: Session = Depends(get_db), can=Depends(permission_check)):
    """Details while the check is open or under inspection; status and result change only through the actions."""
    service = QualityCheckService(db, tenant)
    try:
        return _read(service, service.update(check_id, payload), can)
    except QualityError as exc:
        raise _error(exc) from exc


@router.post("/{check_id}/start", response_model=QualityCheckRead, dependencies=[Depends(require_permission(Q.CHECKS_START))])
def start_quality_check(check_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
    service = QualityCheckService(db, tenant)
    try:
        return _read(service, service.start(check_id), can)
    except QualityError as exc:
        raise _error(exc) from exc


@router.post("/{check_id}/close", response_model=QualityCheckRead, dependencies=[Depends(require_permission(Q.CHECKS_CLOSE))])
def close_quality_check(check_id: UUID, payload: QualityCheckClose, tenant: TenantContext = Depends(get_current_tenant),
                        db: Session = Depends(get_db), can=Depends(permission_check)):
    """Records the result and quantities; a rejected quantity opens a rejection awaiting a decision."""
    service = QualityCheckService(db, tenant)
    try:
        return _read(service, service.close(check_id, payload), can)
    except QualityError as exc:
        raise _error(exc) from exc


@router.post("/{check_id}/cancel", response_model=QualityCheckRead, dependencies=[Depends(require_permission(Q.CHECKS_CANCEL))])
def cancel_quality_check(check_id: UUID, payload: ReasonInput, tenant: TenantContext = Depends(get_current_tenant),
                         db: Session = Depends(get_db), can=Depends(permission_check)):
    service = QualityCheckService(db, tenant)
    try:
        return _read(service, service.cancel(check_id, payload.reason), can)
    except QualityError as exc:
        raise _error(exc) from exc


# ── measurement plan and readings (QUAL-SPEC-001) ──────────────────────────────────────────────

@router.get("/{check_id}/specifications", response_model=list[PlanCandidate], dependencies=[Depends(require_permission(Q.CHECKS_MEASURE))])
def plan_candidates(check_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    """Every specification in force, those for the inspected product first, with the lot values each still needs."""
    service = QualityCheckService(db, tenant)
    try:
        return [PlanCandidate(id=s.id, code=s.code, revision=s.revision, title=s.title, product_type=s.product_type, grade=s.grade,
                              matches_product=matches, missing_keys=missing)
                for s, matches, missing in MeasurementService(db, tenant).candidates(service.get(check_id))]
    except QualityError as exc:
        raise _error(exc) from exc


@router.post("/{check_id}/plan", response_model=QualityCheckRead, dependencies=[Depends(require_permission(Q.CHECKS_MEASURE))])
def apply_plan(check_id: UUID, payload: PlanInput, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
               can=Depends(permission_check)):
    """Copies a specification in force into the check, with its limits resolved for the lot; nothing measured yet."""
    service = QualityCheckService(db, tenant)
    try:
        check = service.get(check_id)
        MeasurementService(db, tenant).apply(check, payload.specification_id, lot_values=payload.lot_values)
        return _read(service, check, can)
    except QualityError as exc:
        raise _error(exc) from exc


@router.put("/{check_id}/measurements/{measurement_id}", response_model=QualityCheckRead, dependencies=[Depends(require_permission(Q.CHECKS_MEASURE))])
def record_measurement(check_id: UUID, measurement_id: UUID, payload: MeasurementInput, tenant: TenantContext = Depends(get_current_tenant),
                       db: Session = Depends(get_db), can=Depends(permission_check)):
    """Readings (numeric) or conforming / not (attribute); the verdict is computed against the plan's limits."""
    service = QualityCheckService(db, tenant)
    try:
        check = service.get(check_id)
        MeasurementService(db, tenant).record(check, measurement_id, payload)
        return _read(service, check, can)
    except QualityError as exc:
        raise _error(exc) from exc
