from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.commercial.api.schemas import SampleEvaluationCreate, SampleEvaluationRead
from app.commercial.application.sample_service import SampleService
from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db, require_permission


router = APIRouter(tags=["commercial-evaluations"])


@router.post(
    "/samples/{sample_id}/evaluations",
    response_model=SampleEvaluationRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("commercial:evaluations:create"))],
)
def create_sample_evaluation(
    sample_id: UUID,
    payload: SampleEvaluationCreate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> SampleEvaluationRead:
    service = SampleService(db)
    try:
        evaluation = service.create_sample_evaluation(tenant, sample_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if evaluation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sample not found.")
    return evaluation

@router.get("/samples/{sample_id}/evaluations", response_model=list[SampleEvaluationRead], dependencies=[Depends(require_permission("commercial:evaluations:read"))])
def list_sample_evaluations(
    sample_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> list[SampleEvaluationRead]:
    service = SampleService(db)
    evaluations = service.list_sample_evaluations(tenant, sample_id)
    if evaluations is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sample not found.")
    return evaluations


@router.get("/sample-evaluations/{evaluation_id}", response_model=SampleEvaluationRead, dependencies=[Depends(require_permission("commercial:evaluations:read"))])
def get_sample_evaluation(
    evaluation_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> SampleEvaluationRead:
    service = SampleService(db)
    evaluation = service.get_sample_evaluation(tenant, evaluation_id)
    if evaluation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sample evaluation not found.",
        )
    return evaluation
