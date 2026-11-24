from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.pagination import Page, PageParams, optional_page_params, page_of
from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db, require_permission
from app.production.domain import permissions as P
from app.production.domain.enums import ShiftDefinitionStatus, ShiftType
from app.production.api.schemas import (
    ShiftDefinitionCreate,
    ShiftDefinitionListItem,
    ShiftDefinitionRead,
    ShiftDefinitionUpdate,
    ShiftDeletionImpact,
)
from app.production.application.services import ShiftDefinitionService


router = APIRouter(prefix="/shift-definitions", tags=["production-shift-definitions"])


@router.post("", response_model=ShiftDefinitionRead, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(P.SHIFTS_CREATE))])
def create_shift_definition(
    payload: ShiftDefinitionCreate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> ShiftDefinitionRead:
    service = ShiftDefinitionService(db)
    try:
        return service.create_shift_definition(tenant, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("", response_model=Page[ShiftDefinitionListItem] | list[ShiftDefinitionListItem],
    dependencies=[Depends(require_permission(P.SHIFTS_READ))])
def list_shift_definitions(
    page: PageParams | None = Depends(optional_page_params),
    search: str = Query(default="", max_length=80), status_filter: ShiftDefinitionStatus | None = Query(default=None, alias="status"),
    shift_type: ShiftType | None = Query(default=None),
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> list[ShiftDefinitionListItem]:
    result = ShiftDefinitionService(db).list_shift_definitions(tenant, page=page, search=search, status=status_filter, shift_type=shift_type)
    return page_of(*result, page) if page is not None else result


@router.get("/{shift_definition_id}", response_model=ShiftDefinitionRead,
    dependencies=[Depends(require_permission(P.SHIFTS_READ))])
def get_shift_definition(
    shift_definition_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> ShiftDefinitionRead:
    service = ShiftDefinitionService(db)
    shift_definition = service.get_shift_definition(tenant, shift_definition_id)
    if shift_definition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift definition not found.")
    return shift_definition


@router.patch("/{shift_definition_id}", response_model=ShiftDefinitionRead,
    dependencies=[Depends(require_permission(P.SHIFTS_UPDATE))])
def update_shift_definition(
    shift_definition_id: UUID,
    payload: ShiftDefinitionUpdate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> ShiftDefinitionRead:
    service = ShiftDefinitionService(db)
    try:
        shift_definition = service.update_shift_definition(tenant, shift_definition_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if shift_definition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift definition not found.")
    return shift_definition


@router.get("/{shift_definition_id}/deletion-impact", response_model=ShiftDeletionImpact,
    dependencies=[Depends(require_permission(P.SHIFTS_READ))])
def get_shift_deletion_impact(
    shift_definition_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> ShiftDeletionImpact:
    service = ShiftDefinitionService(db)
    impact = service.get_deletion_impact(tenant, shift_definition_id)
    if impact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift definition not found.")
    return impact


@router.delete("/{shift_definition_id}", status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission(P.SHIFTS_DELETE))])
def delete_shift_definition(
    shift_definition_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> None:
    service = ShiftDefinitionService(db)
    try:
        found = service.delete_shift_definition(tenant, shift_definition_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift definition not found.")
