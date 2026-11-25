"""Test parameters and product specifications (QUAL-SPEC-001). One permission per action; errors answer {"code": ...}."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.pagination import Page, PageParams, optional_page_params, page_of
from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db, permission_check, require_any_permission, require_permission
from app.quality.api.specification_schemas import (
    NumericPropertyRead, ParameterCreate, ParameterRead, ParameterUpdate, SpecificationCopy, SpecificationCreate, SpecificationListItem, SpecificationRead, SpecificationUpdate,
)
from app.quality.application.specification_service import SpecificationService
from app.quality.domain import permissions as Q
from app.quality.domain.rules import QualityError

router = APIRouter(tags=["quality-specifications"])


def _error(exc: QualityError):
    return HTTPException(status_code=exc.status, detail={"code": exc.code, **exc.detail})


def _actions(can):
    return lambda action: can(f"quality:specifications:{action}")


def _read(service, spec, can, detail=True):
    model = SpecificationRead if detail else SpecificationListItem
    return model.model_validate({**model.model_validate(spec).model_dump(), **service.view(spec, detail, _actions(can))})


# ── test parameters ─────────────────────────────────────────────────────────────────────────────

@router.get("/quality-test-parameters", response_model=Page[ParameterRead] | list[ParameterRead],
            dependencies=[Depends(require_any_permission([Q.SPECS_READ, Q.CHECKS_MEASURE]))])
def list_parameters(active: bool = False, page: PageParams | None = Depends(optional_page_params), search: str = Query(default="", max_length=80),
                    status_filter: str | None = Query(default=None, alias="status", pattern="^(active|inactive)$"), tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    result = SpecificationService(db, tenant).parameters(active_only=active, page=page, search=search, status=status_filter)
    return page_of(*result, page) if page is not None else result


@router.post("/quality-test-parameters", response_model=ParameterRead, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_permission(Q.SPECS_CREATE))])
def create_parameter(payload: ParameterCreate, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    try:
        return SpecificationService(db, tenant).create_parameter(payload)
    except QualityError as exc:
        raise _error(exc) from exc


@router.post("/quality-test-parameters/standard", response_model=list[ParameterRead], dependencies=[Depends(require_permission(Q.SPECS_CREATE))])
def add_standard_parameters(tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    """Adds the strapping-band parameters (width, thickness, weight, length, strength, elongation, visual checks) once."""
    return SpecificationService(db, tenant).add_standard_parameters()


@router.patch("/quality-test-parameters/{parameter_id}", response_model=ParameterRead, dependencies=[Depends(require_permission(Q.SPECS_UPDATE))])
def update_parameter(parameter_id: UUID, payload: ParameterUpdate, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    try:
        return SpecificationService(db, tenant).update_parameter(parameter_id, payload)
    except QualityError as exc:
        raise _error(exc) from exc


# ── specifications ──────────────────────────────────────────────────────────────────────────────

@router.get("/quality-specifications", response_model=Page[SpecificationListItem] | list[SpecificationListItem], dependencies=[Depends(require_permission(Q.SPECS_READ))])
def list_specifications(status_filter: str | None = Query(default=None, alias="status", pattern="^(draft|active|superseded)$"),
                        product_type: str | None = Query(default=None, max_length=120), search: str | None = Query(default=None, max_length=60),
                        page: PageParams | None = Depends(optional_page_params), tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
    service = SpecificationService(db, tenant)
    result = service.list(status_filter, product_type, search, page=page)
    rows, total = result if page is not None else (result, 0)
    items = [_read(service, row, can, detail=False) for row in rows]
    return page_of(items, total, page) if page is not None else items


@router.post("/quality-specifications", response_model=SpecificationRead, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_permission(Q.SPECS_CREATE))])
def create_specification(payload: SpecificationCreate, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                         can=Depends(permission_check)):
    """A new specification (revision 1) as a draft."""
    service = SpecificationService(db, tenant)
    try:
        return _read(service, service.create(payload), can)
    except QualityError as exc:
        db.rollback()
        raise _error(exc) from exc


@router.get("/quality-specifications/numeric-properties", response_model=list[NumericPropertyRead], dependencies=[Depends(require_any_permission([Q.SPECS_READ, Q.SPECS_CREATE, Q.SPECS_UPDATE]))])
def numeric_template_properties(tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    from app.core.interfaces.product_catalog import numeric_properties
    return [dict(key=p.key, name_ar=p.name_ar, name_en=p.name_en) for p in numeric_properties(db, tenant.organization_id)]


@router.post("/quality-specifications/{spec_id}/copy", response_model=SpecificationRead, status_code=201,
             dependencies=[Depends(require_permission(Q.SPECS_CREATE))])
def copy_specification(spec_id: UUID, payload: SpecificationCopy, tenant: TenantContext = Depends(get_current_tenant),
                       db: Session = Depends(get_db), can=Depends(permission_check)):
    service = SpecificationService(db, tenant)
    try:
        return _read(service, service.copy(spec_id, payload), can)
    except QualityError as exc:
        db.rollback()
        raise _error(exc) from exc


@router.get("/quality-specifications/{spec_id}", response_model=SpecificationRead, dependencies=[Depends(require_permission(Q.SPECS_READ))])
def get_specification(spec_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
    service = SpecificationService(db, tenant)
    try:
        return _read(service, service.get(spec_id), can)
    except QualityError as exc:
        raise _error(exc) from exc


@router.patch("/quality-specifications/{spec_id}", response_model=SpecificationRead, dependencies=[Depends(require_permission(Q.SPECS_UPDATE))])
def update_specification(spec_id: UUID, payload: SpecificationUpdate, tenant: TenantContext = Depends(get_current_tenant),
                         db: Session = Depends(get_db), can=Depends(permission_check)):
    """A draft only; the lines, when given, replace the current ones."""
    service = SpecificationService(db, tenant)
    try:
        return _read(service, service.update(spec_id, payload), can)
    except QualityError as exc:
        db.rollback()
        raise _error(exc) from exc


@router.post("/quality-specifications/{spec_id}/activate", response_model=SpecificationRead, dependencies=[Depends(require_permission(Q.SPECS_ACTIVATE))])
def activate_specification(spec_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
    """Puts the draft into force; the revision in force with the same code becomes superseded."""
    service = SpecificationService(db, tenant)
    try:
        return _read(service, service.activate(spec_id), can)
    except QualityError as exc:
        raise _error(exc) from exc


@router.post("/quality-specifications/{spec_id}/revise", response_model=SpecificationRead, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_permission(Q.SPECS_CREATE))])
def revise_specification(spec_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
    """A new draft revision copying this one's lines."""
    service = SpecificationService(db, tenant)
    try:
        return _read(service, service.revise(spec_id), can)
    except QualityError as exc:
        raise _error(exc) from exc
