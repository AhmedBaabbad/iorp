from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.commercial.api.schemas import SampleCreate, SampleDeletionImpact, SampleEvaluationCreate, SampleUpdate
from app.commercial.domain.enums import SampleStatus
from app.commercial.infrastructure.models import Sample, SampleEvaluation
from app.commercial.infrastructure.repositories import (
    CustomerRepository,
    QuoteRepository,
    SampleEvaluationRepository,
    SampleRepository,
)
from app.core.tenancy import TenantContext
from app.foundation.application.services import FoundationService


class SampleService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.customers = CustomerRepository(db)
        self.samples = SampleRepository(db)
        self.sample_evaluations = SampleEvaluationRepository(db)
        self.quotes = QuoteRepository(db)

    def create_sample(
        self,
        tenant: TenantContext,
        customer_id: UUID,
        data: SampleCreate,
    ) -> Sample | None:
        customer = self.customers.get_by_id(tenant.organization_id, customer_id)
        if customer is None:
            return None

        year = datetime.now(timezone.utc).year
        highest = self.samples.get_highest_sample_code_sequence(tenant.organization_id, year)
        self.samples.ensure_code_counter(tenant.organization_id, year, highest)
        counter = self.samples.get_code_counter_for_update(tenant.organization_id, year)
        if counter is None:
            raise ValueError("Sample code counter could not be initialized.")
        counter.last_value += 1
        sample_code = f"RFS-{year}-{counter.last_value:03d}"

        payload = data.model_dump()
        if not payload["is_sample_requested"]:
            payload["requested_sample_quantity"] = None

        requested_status = payload.pop("status", SampleStatus.REQUESTED)
        if requested_status == SampleStatus.EVALUATED:
            raise ValueError(
                "Sample status 'evaluated' can only be set by creating a sample evaluation."
            )

        sample = Sample(
            customer_id=customer.id,
            sample_code=sample_code,
            created_by_user_id=tenant.user_id,
            status=requested_status,
            **payload,
        )

        try:
            self.samples.add(sample)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Sample could not be saved due to invalid or duplicate data.") from exc

        self.db.refresh(sample)
        return self._attach_sample_created_by_name(tenant, sample)

    def get_deletion_impact(
        self,
        tenant: TenantContext,
        sample_id: UUID,
    ) -> SampleDeletionImpact | None:
        sample = self.samples.get_by_id(tenant.organization_id, sample_id)
        if sample is None:
            return None

        quotes = self.quotes.count_by_sample(sample.id)
        return SampleDeletionImpact(
            evaluations=self.sample_evaluations.count_by_sample(sample.id),
            quotes=quotes,
            is_blocked=quotes > 0,
        )

    def delete_sample(self, tenant: TenantContext, sample_id: UUID) -> bool:
        sample = self.samples.get_by_id(tenant.organization_id, sample_id)
        if sample is None:
            return False

        if self.quotes.count_by_sample(sample.id) > 0:
            raise ValueError(
                "Cannot delete a sample that is referenced by quotes. Remove the quotes first.",
            )

        self.sample_evaluations.delete_for_sample(sample_id)
        self.samples.delete(sample)
        self.db.commit()
        return True

    def list_samples(self, tenant: TenantContext) -> list[Sample]:
        samples = self.samples.list_by_organization(tenant.organization_id)
        return [self._attach_sample_created_by_name(tenant, sample) for sample in samples]

    def list_samples_for_customer(
        self,
        tenant: TenantContext,
        customer_id: UUID,
    ) -> list[Sample] | None:
        customer = self.customers.get_by_id(tenant.organization_id, customer_id)
        if customer is None:
            return None

        samples = self.samples.list_by_customer(tenant.organization_id, customer_id)
        return [self._attach_sample_created_by_name(tenant, sample) for sample in samples]

    def get_sample(self, tenant: TenantContext, sample_id: UUID) -> Sample | None:
        sample = self.samples.get_by_id(tenant.organization_id, sample_id)
        if sample is None:
            return None
        return self._attach_sample_created_by_name(tenant, sample)

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
        if payload.get("is_sample_requested") is False:
            payload["requested_sample_quantity"] = None

        if "status" in payload and payload["status"] == SampleStatus.EVALUATED:
            raise ValueError(
                "Sample status 'evaluated' can only be set by creating a sample evaluation."
            )

        for field, value in payload.items():
            setattr(sample, field, value)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Sample could not be saved due to invalid or duplicate data.") from exc

        self.db.refresh(sample)
        return self._attach_sample_created_by_name(tenant, sample)

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

    def _attach_sample_created_by_name(
        self,
        tenant: TenantContext,
        sample: Sample,
    ) -> Sample:
        foundation = FoundationService(self.db)
        user = foundation.get_user_by_id_in_organization(
            sample.created_by_user_id,
            tenant.organization_id,
        )
        sample.created_by_name = user.full_name if user is not None else None
        return sample
