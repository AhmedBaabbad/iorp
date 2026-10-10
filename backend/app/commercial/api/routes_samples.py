from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.commercial.application.visibility import SAMPLES_READ, visible_owner
from app.commercial.api.schemas import SampleCreate, SampleDeletionImpact, SampleListItem, SamplePage, SampleRead, SampleUpdate, SampleProductDefinition
from app.commercial.domain.enums import SampleStatus
from app.commercial.infrastructure.repositories import ListFilters
from app.core.pagination import PageParams, page_of, page_params
from app.commercial.application.sample_service import SampleService
from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db, require_permission, require_any_permission, permission_check
from app.commercial.domain.action_permissions import SAMPLE_STATUS_PERMISSIONS
from app.core.interfaces.product_catalog import ProductSpecificationError


router = APIRouter(tags=["commercial-samples"])


@router.get('/samples/product-options',response_model=list[SampleProductDefinition],
    dependencies=[Depends(require_any_permission(['commercial:samples:create','commercial:samples:update','commercial:samples:read']))])
def sample_product_options(tenant:TenantContext=Depends(get_current_tenant),db:Session=Depends(get_db)):
    """Only product identities/templates from Master Data; no write permission to Master Data is granted."""
    return SampleService(db, visible_owner(db, tenant, SAMPLES_READ)).product_options(tenant)


@router.post(
    "/customers/{customer_id}/samples",
    response_model=SampleRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("commercial:samples:create"))],
)
def create_sample(
    customer_id: UUID,
    payload: SampleCreate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    can=Depends(permission_check),
) -> SampleRead:
    if payload.status != SampleStatus.REQUESTED and not can(SAMPLE_STATUS_PERMISSIONS[payload.status]):
        raise HTTPException(403, 'Missing sample lifecycle permission.')
    service = SampleService(db, visible_owner(db, tenant, SAMPLES_READ))
    try:
        sample = service.create_sample(tenant, customer_id, payload)
    except ProductSpecificationError as exc:
        raise HTTPException(422,detail={'code':exc.code,'property_key':exc.property_key}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if sample is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    return sample


@router.get("/samples", response_model=SamplePage, dependencies=[Depends(require_permission("commercial:samples:read"))])
def list_samples(
    search: str | None = Query(None, max_length=120),
    status_filter: SampleStatus | None = Query(None, alias="status"),
    customer_id: UUID | None = None,
    params: PageParams = Depends(page_params),
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> SamplePage:
    """One page of samples (ARCH-PAGE-001): search by code, product or customer; filter by status or customer."""
    filters = ListFilters(search=(search or "").strip() or None, status=status_filter.value if status_filter else None, customer_id=customer_id)
    items, total = SampleService(db, visible_owner(db, tenant, SAMPLES_READ)).page_samples(tenant, filters, params)
    return SamplePage(**page_of(items, total, params))


@router.get("/customers/{customer_id}/samples", response_model=list[SampleListItem], dependencies=[Depends(require_permission("commercial:samples:read"))])
def list_samples_for_customer(
    customer_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> list[SampleListItem]:
    service = SampleService(db, visible_owner(db, tenant, SAMPLES_READ))
    samples = service.list_samples_for_customer(tenant, customer_id)
    if samples is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    return samples


@router.get("/samples/{sample_id}", response_model=SampleRead, dependencies=[Depends(require_permission("commercial:samples:read"))])
def get_sample(
    sample_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> SampleRead:
    service = SampleService(db, visible_owner(db, tenant, SAMPLES_READ))
    sample = service.get_sample(tenant, sample_id)
    if sample is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sample not found.")
    return sample


@router.patch("/samples/{sample_id}", response_model=SampleRead, dependencies=[Depends(require_permission("commercial:samples:update"))])
def update_sample(
    sample_id: UUID,
    payload: SampleUpdate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    can=Depends(permission_check),
) -> SampleRead:
    service = SampleService(db, visible_owner(db, tenant, SAMPLES_READ))
    existing = service.get_sample(tenant, sample_id)
    if existing is None:
        raise HTTPException(404, 'Sample not found.')
    if payload.status is not None and payload.status != existing.status and not can(SAMPLE_STATUS_PERMISSIONS[payload.status]):
        raise HTTPException(403, 'Missing sample lifecycle permission.')
    if 'sample_decision' in payload.model_fields_set and (payload.sample_decision or 'pending') != (existing.sample_decision or 'pending') and not can('commercial:samples:decide'):
        raise HTTPException(403, 'Missing sample decision permission.')
    try:
        sample = service.update_sample(tenant, sample_id, payload)
    except ProductSpecificationError as exc:
        raise HTTPException(422,detail={'code':exc.code,'property_key':exc.property_key}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if sample is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sample not found.")
    return sample


@router.get("/samples/{sample_id}/deletion-impact", response_model=SampleDeletionImpact, dependencies=[Depends(require_permission("commercial:samples:read"))])
def get_sample_deletion_impact(
    sample_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> SampleDeletionImpact:
    service = SampleService(db, visible_owner(db, tenant, SAMPLES_READ))
    impact = service.get_deletion_impact(tenant, sample_id)
    if impact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sample not found.")
    return impact


@router.delete("/samples/{sample_id}", dependencies=[Depends(require_permission("commercial:samples:delete"))])
def delete_sample(
    sample_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    service = SampleService(db, visible_owner(db, tenant, SAMPLES_READ))
    try:
        deleted = service.delete_sample(tenant, sample_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sample not found.")
    return {"status": "deleted"}
