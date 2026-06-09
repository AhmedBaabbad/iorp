from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.commercial.api.schemas import SampleCreate, SampleListItem, SampleRead, SampleUpdate
from app.commercial.application.sample_service import SampleService
from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db


router = APIRouter(tags=["commercial-samples"])


@router.post(
    "/customers/{customer_id}/samples",
    response_model=SampleRead,
    status_code=status.HTTP_201_CREATED,
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


@router.get("/samples", response_model=list[SampleListItem])
def list_samples(
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> list[SampleListItem]:
    service = SampleService(db)
    return service.list_samples(tenant)


@router.get("/customers/{customer_id}/samples", response_model=list[SampleListItem])
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


@router.get("/samples/{sample_id}", response_model=SampleRead)
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


@router.patch("/samples/{sample_id}", response_model=SampleRead)
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
