from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.commercial.api.schemas import (
    CustomerCreate,
    CustomerInteractionCreate,
    CustomerUpdate,
    FollowUpComplete,
    FollowUpCreate,
)
from app.commercial.domain.enums import FollowUpStatus
from app.commercial.infrastructure.models import Customer, CustomerInteraction, FollowUp
from app.commercial.infrastructure.repositories import (
    CustomerInteractionRepository,
    CustomerRepository,
    FollowUpRepository,
)
from app.core.tenancy import TenantContext
from app.core.utils import utc_now
from app.foundation.application.services import FoundationService


class CustomerService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.customers = CustomerRepository(db)
        self.interactions = CustomerInteractionRepository(db)
        self.follow_ups = FollowUpRepository(db)

    def create_customer(self, tenant: TenantContext, data: CustomerCreate) -> Customer:
        existing = self.customers.get_by_code(tenant.organization_id, data.customer_code)
        if existing is not None:
            raise ValueError(f"Customer code '{data.customer_code}' already exists.")

        if data.assigned_sales_user_id is not None:
            foundation = FoundationService(self.db)
            if foundation.get_user_by_id_in_organization(
                data.assigned_sales_user_id,
                tenant.organization_id,
            ) is None:
                raise ValueError("Assigned sales user does not belong to the current organization.")

        customer = Customer(
            organization_id=tenant.organization_id,
            **data.model_dump(),
        )
        try:
            self.customers.add(customer)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Customer could not be saved due to invalid or duplicate data.") from exc

        self.db.refresh(customer)
        return customer

    def create_interaction(
        self,
        tenant: TenantContext,
        customer_id: UUID,
        data: CustomerInteractionCreate,
    ) -> CustomerInteraction | None:
        customer = self.customers.get_by_id(tenant.organization_id, customer_id)
        if customer is None:
            return None

        interaction = CustomerInteraction(
            customer_id=customer.id,
            created_by_user_id=tenant.user_id,
            **data.model_dump(),
        )

        try:
            self.interactions.add(interaction)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Interaction could not be saved due to invalid data.") from exc

        self.db.refresh(interaction)
        return interaction

    def list_interactions(
        self,
        tenant: TenantContext,
        customer_id: UUID,
    ) -> list[CustomerInteraction] | None:
        customer = self.customers.get_by_id(tenant.organization_id, customer_id)
        if customer is None:
            return None

        return self.interactions.list_for_customer(tenant.organization_id, customer_id)

    def create_follow_up(
        self,
        tenant: TenantContext,
        customer_id: UUID,
        data: FollowUpCreate,
    ) -> FollowUp | None:
        customer = self.customers.get_by_id(tenant.organization_id, customer_id)
        if customer is None:
            return None

        foundation = FoundationService(self.db)
        if foundation.get_user_by_id_in_organization(
            data.assigned_user_id,
            tenant.organization_id,
        ) is None:
            raise ValueError("Assigned user does not belong to the current organization.")

        if data.interaction_id is not None:
            interaction = self.interactions.get_for_customer(
                tenant.organization_id,
                customer_id,
                data.interaction_id,
            )
            if interaction is None:
                raise ValueError("Interaction must belong to the target customer.")

        follow_up = FollowUp(
            customer_id=customer.id,
            status=FollowUpStatus.PENDING,
            **data.model_dump(),
        )

        try:
            self.follow_ups.add(follow_up)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Follow-up could not be saved due to invalid data.") from exc

        self.db.refresh(follow_up)
        return follow_up

    def list_follow_ups(self, tenant: TenantContext) -> list[FollowUp]:
        return self.follow_ups.list_by_organization(tenant.organization_id)

    def list_follow_ups_for_customer(
        self,
        tenant: TenantContext,
        customer_id: UUID,
    ) -> list[FollowUp] | None:
        customer = self.customers.get_by_id(tenant.organization_id, customer_id)
        if customer is None:
            return None

        return self.follow_ups.list_by_customer(tenant.organization_id, customer_id)

    def complete_follow_up(
        self,
        tenant: TenantContext,
        follow_up_id: UUID,
        data: FollowUpComplete,
    ) -> FollowUp | None:
        follow_up = self.follow_ups.get_by_id(tenant.organization_id, follow_up_id)
        if follow_up is None:
            return None

        follow_up.status = FollowUpStatus.COMPLETED
        follow_up.completed_at = data.completed_at or utc_now()
        if data.notes is not None:
            follow_up.notes = data.notes

        self.db.commit()
        self.db.refresh(follow_up)
        return follow_up

    def list_customers(self, tenant: TenantContext) -> list[Customer]:
        return self.customers.list_by_organization(tenant.organization_id)

    def get_customer(self, tenant: TenantContext, customer_id: UUID) -> Customer | None:
        return self.customers.get_by_id(tenant.organization_id, customer_id)

    def update_customer(
        self,
        tenant: TenantContext,
        customer_id: UUID,
        data: CustomerUpdate,
    ) -> Customer | None:
        customer = self.customers.get_by_id(tenant.organization_id, customer_id)
        if customer is None:
            return None

        payload = data.model_dump(exclude_unset=True)
        new_customer_code = payload.get("customer_code")
        if new_customer_code is not None and new_customer_code != customer.customer_code:
            existing = self.customers.get_by_code(tenant.organization_id, new_customer_code)
            if existing is not None and existing.id != customer.id:
                raise ValueError(f"Customer code '{new_customer_code}' already exists.")

        if "assigned_sales_user_id" in payload and payload["assigned_sales_user_id"] is not None:
            foundation = FoundationService(self.db)
            if foundation.get_user_by_id_in_organization(
                payload["assigned_sales_user_id"],
                tenant.organization_id,
            ) is None:
                raise ValueError("Assigned sales user does not belong to the current organization.")

        for field, value in payload.items():
            setattr(customer, field, value)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Customer could not be saved due to invalid or duplicate data.") from exc

        self.db.refresh(customer)
        return customer
