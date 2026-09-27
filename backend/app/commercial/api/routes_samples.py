from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.commercial.api.schemas import SampleCreate, SampleDeletionImpact, SampleListItem, SampleRead, SampleUpdate
from app.commercial.application.sample_service import SampleService
from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db, require_permission


router = APIRouter(tags=["commercial-samples"])


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
) -> SampleRead:
    service = SampleService(db)
    try:
        sample = service.create_sample(tenant, customer_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if sample is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    return sample


@router.get("/samples", response_model=list[SampleListItem], dependencies=[Depends(require_permission("commercial:samples:read"))])
def list_samples(
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> list[SampleListItem]:
    service = SampleService(db)
    return service.list_samples(tenant)


@router.get("/customers/{customer_id}/samples", response_model=list[SampleListItem], dependencies=[Depends(require_permission("commercial:samples:read"))])
def list_samples_for_customer(
    customer_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> list[SampleListItem]:
    service = SampleService(db)
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
    service = SampleService(db)
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
) -> SampleRead:
    service = SampleService(db)
    try:
        sample = service.update_sample(tenant, sample_id, payload)
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
    service = SampleService(db)
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
    service = SampleService(db)
    try:
        deleted = service.delete_sample(tenant, sample_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sample not found.")
    return {"status": "deleted"}
