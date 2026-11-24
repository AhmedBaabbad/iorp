from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.pagination import Page, PageParams, optional_page_params, page_of
from app.commercial.application.visibility import SAMPLES_READ, visible_owner
from app.commercial.api.schemas import SampleEvaluationCreate, SampleEvaluationRead, SampleEvaluationUpdate
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
    service = SampleService(db, visible_owner(db, tenant, SAMPLES_READ))
    try:
        evaluation = service.create_sample_evaluation(tenant, sample_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if evaluation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sample not found.")
    return evaluation

@router.get("/samples/{sample_id}/evaluations", response_model=Page[SampleEvaluationRead] | list[SampleEvaluationRead], dependencies=[Depends(require_permission("commercial:evaluations:read"))])
def list_sample_evaluations(
    sample_id: UUID, page: PageParams | None = Depends(optional_page_params),
    search: str = Query(default="", max_length=80), status_filter: str | None = Query(default=None, alias="status", pattern="^(accepted|rejected|needs_modification)$"),
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> list[SampleEvaluationRead]:
    service = SampleService(db, visible_owner(db, tenant, SAMPLES_READ))
    evaluations = service.list_sample_evaluations(tenant, sample_id, page=page, search=search, status=status_filter)
    if evaluations is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sample not found.")
    return page_of(*evaluations, page) if page is not None else evaluations


@router.get("/sample-evaluations/{evaluation_id}", response_model=SampleEvaluationRead, dependencies=[Depends(require_permission("commercial:evaluations:read"))])
def get_sample_evaluation(
    evaluation_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> SampleEvaluationRead:
    service = SampleService(db, visible_owner(db, tenant, SAMPLES_READ))
    evaluation = service.get_sample_evaluation(tenant, evaluation_id)
    if evaluation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sample evaluation not found.",
        )
    return evaluation


@router.patch("/sample-evaluations/{evaluation_id}", response_model=SampleEvaluationRead,
              dependencies=[Depends(require_permission("commercial:evaluations:update"))])
def update_sample_evaluation(evaluation_id: UUID, payload: SampleEvaluationUpdate, tenant: TenantContext = Depends(get_current_tenant),
                             db: Session = Depends(get_db)) -> SampleEvaluationRead:
    """Corrects an evaluation (RBAC-002)."""
    try:
        evaluation = SampleService(db, visible_owner(db, tenant, SAMPLES_READ)).update_sample_evaluation(tenant, evaluation_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if evaluation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sample evaluation not found.")
    return evaluation


@router.delete("/sample-evaluations/{evaluation_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_permission("commercial:evaluations:delete"))])
def delete_sample_evaluation(evaluation_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)) -> None:
    if not SampleService(db, visible_owner(db, tenant, SAMPLES_READ)).delete_sample_evaluation(tenant, evaluation_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sample evaluation not found.")
