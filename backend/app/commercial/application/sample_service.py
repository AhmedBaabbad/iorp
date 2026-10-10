from datetime import datetime, timezone
from json import dumps
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.interfaces import product_catalog
from app.commercial.api.schemas import SampleCreate, SampleDeletionImpact, SampleEvaluationCreate, SampleUpdate
from app.commercial.domain.enums import SampleStatus
from app.commercial.infrastructure.models import Sample, SampleEvaluation
from app.commercial.infrastructure.repositories import customer_labels
from app.commercial.infrastructure.repositories import (
    CustomerRepository,
    QuoteRepository,
    SampleEvaluationRepository,
    SampleRepository,
)
from app.core.tenancy import TenantContext
from app.foundation.application.services import FoundationService


class SampleService:
    def __init__(self, db: Session, owner_user_id: UUID | None = None) -> None:
        """owner_user_id: see only the records of this sales owner's customers (RBAC-002, visibility.py)."""
        self.db = db
        self.customers = CustomerRepository(db)
        self.samples = SampleRepository(db)
        self.sample_evaluations = SampleEvaluationRepository(db)
        self.quotes = QuoteRepository(db)
        self.samples.owner_user_id = owner_user_id
        self.quotes.owner_user_id = owner_user_id
        self.customers.owner_user_id = owner_user_id
        self.sample_evaluations.owner_user_id = owner_user_id

    def create_sample(
        self,
        tenant: TenantContext,
        customer_id: UUID,
        data: SampleCreate,
    ) -> Sample | None:
        customer = self.customers.get_by_id(tenant.organization_id, customer_id)
        if customer is None:
            return None
        product_catalog.validate_sample_properties(self.db,tenant.organization_id,data.product_type,data.requested_spec_json or {})

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

    def page_samples(self, tenant: TenantContext, filters, params):
        """One page of samples, with the customer, the author and the product read once for the whole page."""
        samples, total = self.samples.page(tenant.organization_id, filters, params)
        labels = customer_labels(self.db, tenant.organization_id, [s.customer_id for s in samples])
        foundation = FoundationService(self.db)
        people = {}
        for user_id in {s.created_by_user_id for s in samples}:
            user = foundation.get_user_by_id_in_organization(user_id, tenant.organization_id)
            people[user_id] = user.full_name if user is not None else None
        definitions = product_catalog.products(self.db, tenant.organization_id, {s.product_type for s in samples})
        for sample in samples:
            sample.customer_name, sample.customer_code = labels.get(sample.customer_id, (None, None))
            sample.created_by_name = people.get(sample.created_by_user_id)
            definition = definitions.get(sample.product_type)
            sample.product_definition = self.product_view(definition) if definition else None
        return samples, total

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
        product_key=payload.get('product_type',sample.product_type)
        if product_key is None:
            raise product_catalog.ProductSpecificationError('SAMPLE_PRODUCT_NOT_FOUND')
        new_values=payload.get('requested_spec_json',sample.requested_spec_json)
        if product_key != sample.product_type or ('requested_spec_json' in payload and dumps(new_values, sort_keys=True) != dumps(sample.requested_spec_json, sort_keys=True)):
            payload['requested_spec_json'] = product_catalog.validate_sample_properties(self.db,tenant.organization_id,product_key,new_values or {},
                existing_key=sample.product_type,existing_values=sample.requested_spec_json)
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
        return self._attach_evaluated_by_name(tenant, evaluation)

    def update_sample_evaluation(self, tenant: TenantContext, evaluation_id: UUID, data) -> SampleEvaluation | None:
        """Corrects an evaluation (commercial:evaluations:update)."""
        evaluation = self.sample_evaluations.get_by_id(tenant.organization_id, evaluation_id)
        if evaluation is None:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            if value is None:
                if field != "comments":
                    raise ValueError(f"{field} cannot be empty.")
            setattr(evaluation, field, value)
        self.db.commit()
        self.db.refresh(evaluation)
        return self._attach_evaluated_by_name(tenant, evaluation)

    def delete_sample_evaluation(self, tenant: TenantContext, evaluation_id: UUID) -> bool:
        """Removes an evaluation recorded by mistake (commercial:evaluations:delete). A sample left without any evaluation
        goes back to delivered, waiting for one."""
        evaluation = self.sample_evaluations.get_by_id(tenant.organization_id, evaluation_id)
        if evaluation is None:
            return False
        sample = self.samples.get_by_id(tenant.organization_id, evaluation.sample_id)
        self.db.delete(evaluation)
        self.db.flush()
        remaining = self.db.scalar(select(SampleEvaluation.id).where(SampleEvaluation.sample_id == evaluation.sample_id).limit(1))
        if sample is not None and remaining is None and sample.status == SampleStatus.EVALUATED:
            sample.status = SampleStatus.DELIVERED
        self.db.commit()
        return True

    def list_sample_evaluations(
        self,
        tenant: TenantContext,
        sample_id: UUID,
    ) -> list[SampleEvaluation] | None:
        sample = self.samples.get_by_id(tenant.organization_id, sample_id)
        if sample is None:
            return None

        return [self._attach_evaluated_by_name(tenant, row)
                for row in self.sample_evaluations.list_by_sample(tenant.organization_id, sample_id)]

    def get_sample_evaluation(
        self,
        tenant: TenantContext,
        evaluation_id: UUID,
    ) -> SampleEvaluation | None:
        evaluation = self.sample_evaluations.get_by_id(tenant.organization_id, evaluation_id)
        return self._attach_evaluated_by_name(tenant, evaluation) if evaluation else None

    def _attach_evaluated_by_name(self, tenant: TenantContext, evaluation: SampleEvaluation) -> SampleEvaluation:
        user = FoundationService(self.db).get_user_by_id_in_organization(
            evaluation.evaluated_by_user_id, tenant.organization_id,
        )
        evaluation.evaluated_by_name = user.full_name if user is not None else None
        return evaluation

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
        definition=product_catalog.products(self.db,tenant.organization_id,[sample.product_type]).get(sample.product_type)
        sample.product_definition=self.product_view(definition) if definition else None
        return sample

    @staticmethod
    def product_view(product):
        return dict(key=product.key,name_ar=product.name_ar,name_en=product.name_en,active=product.active,
            default_unit=product.default_unit,properties=[dict(key=p.key,name_ar=p.name_ar,name_en=p.name_en,
                kind=p.kind,unit=p.unit,required=p.required,options=[dict(value=v,label_ar=ar,label_en=en) for v,ar,en in p.options])
                for p in product.properties])

    def product_options(self,tenant):
        return [self.product_view(p) for p in product_catalog.sample_products(self.db,tenant.organization_id)]
