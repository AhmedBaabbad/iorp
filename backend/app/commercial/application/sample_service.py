from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.commercial.api.schemas import SampleCreate, SampleEvaluationCreate, SampleUpdate
from app.commercial.domain.enums import SampleStatus
from app.commercial.infrastructure.models import Sample, SampleEvaluation
from app.commercial.infrastructure.repositories import (
    CustomerRepository,
    SampleEvaluationRepository,
    SampleRepository,
)
from app.core.tenancy import TenantContext


class SampleService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.customers = CustomerRepository(db)
        self.samples = SampleRepository(db)
        self.sample_evaluations = SampleEvaluationRepository(db)

    def create_sample(
        self,
        tenant: TenantContext,
        customer_id: UUID,
        data: SampleCreate,
    ) -> Sample | None:
        customer = self.customers.get_by_id(tenant.organization_id, customer_id)
        if customer is None:
            return None

        existing = self.samples.get_by_code_for_customer(
            tenant.organization_id, customer.id, data.sample_code
        )
        if existing is not None:
            raise ValueError(
                f"Sample code '{data.sample_code}' already exists for this customer."
            )

        sample = Sample(
            customer_id=customer.id,
            created_by_user_id=tenant.user_id,
            status=SampleStatus.REQUESTED,
            **data.model_dump(),
        )

        try:
            self.samples.add(sample)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Sample could not be saved due to invalid or duplicate data.") from exc

        self.db.refresh(sample)
        return sample

    def list_samples(self, tenant: TenantContext) -> list[Sample]:
        return self.samples.list_by_organization(tenant.organization_id)

    def list_samples_for_customer(
        self,
        tenant: TenantContext,
        customer_id: UUID,
    ) -> list[Sample] | None:
        customer = self.customers.get_by_id(tenant.organization_id, customer_id)
        if customer is None:
            return None

        return self.samples.list_by_customer(tenant.organization_id, customer_id)

    def get_sample(self, tenant: TenantContext, sample_id: UUID) -> Sample | None:
        return self.samples.get_by_id(tenant.organization_id, sample_id)

    def update_sample(
        self,
        tenant: TenantContext,
        sample_id: UUID,
        data: SampleUpdate,
    ) -> Sample | None:
        sample = self.samples.get_by_id(tenant.organization_id, sample_id)
        if sample is None:
            return None

        payload = data.model_dump(exclude_unset=True)
        if "status" in payload and payload["status"] == SampleStatus.EVALUATED:
            raise ValueError(
                "Sample status 'evaluated' can only be set by creating a sample evaluation."
            )

        new_sample_code = payload.get("sample_code")
        if new_sample_code is not None and new_sample_code != sample.sample_code:
            existing = self.samples.get_by_code_for_customer(
                tenant.organization_id, sample.customer_id, new_sample_code
            )
            if existing is not None and existing.id != sample.id:
                raise ValueError(
                    f"Sample code '{new_sample_code}' already exists for this customer."
                )

        for field, value in payload.items():
            setattr(sample, field, value)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Sample could not be saved due to invalid or duplicate data.") from exc

        self.db.refresh(sample)
        return sample

    def create_sample_evaluation(
        self,
        tenant: TenantContext,
        sample_id: UUID,
        data: SampleEvaluationCreate,
    ) -> SampleEvaluation | None:
        sample = self.samples.get_by_id(tenant.organization_id, sample_id)
        if sample is None:
            return None

        if sample.status == SampleStatus.CANCELLED:
            raise ValueError("Cannot evaluate a cancelled sample.")

        sample.status = SampleStatus.EVALUATED

        evaluation = SampleEvaluation(
            sample_id=sample.id,
            evaluated_by_user_id=tenant.user_id,
            **data.model_dump(),
        )

        try:
            self.sample_evaluations.add(evaluation)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Sample evaluation could not be saved due to invalid data.") from exc

        self.db.refresh(evaluation)
        return evaluation

    def list_sample_evaluations(
        self,
        tenant: TenantContext,
        sample_id: UUID,
    ) -> list[SampleEvaluation] | None:
        sample = self.samples.get_by_id(tenant.organization_id, sample_id)
        if sample is None:
            return None

        return self.sample_evaluations.list_by_sample(tenant.organization_id, sample_id)

    def get_sample_evaluation(
        self,
        tenant: TenantContext,
        evaluation_id: UUID,
    ) -> SampleEvaluation | None:
        return self.sample_evaluations.get_by_id(tenant.organization_id, evaluation_id)
