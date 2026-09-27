from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from app.core.interfaces.authorization_policy import AuthorizationContext, AuthorizationPolicy

from app.commercial.api.schemas import (
    CreatedBySummary,
    CustomerCreate,
    CustomerDeletionImpact,
    CustomerInteractionCreate,
    CustomerUpdate,
    EligibleSalesOwnerResponse,
    FollowUpComplete,
    FollowUpCreate,
    FollowUpCustomerSummary,
    FollowUpAssignedUser,
    FollowUpUpdate,
    RoleSummary,
    SalesOwnerSummary,
    WorkforceSummary,
)
from app.commercial.application.follow_up_eligibility import FollowUpAssigneeEligibilityService
from app.commercial.application.sales_owner_eligibility import SalesOwnerEligibilityService
from app.commercial.application.workforce_enrichment import get_workforce_summary_row
from app.commercial.domain.enums import FollowUpStatus
from app.commercial.infrastructure.models import Customer, CustomerInteraction, FollowUp
from app.commercial.infrastructure.repositories import (
    CommercialOrderRepository,
    CustomerInteractionRepository,
    CustomerRepository,
    FollowUpListFilters,
    FollowUpRepository,
    QuoteRepository,
    SampleRepository,
)
from app.core.tenancy import TenantContext
from app.core.interfaces.activity_log import get_registered_activity_logger
from app.core.utils import utc_now
from app.foundation.application.services import FoundationService


class CustomerService:
    def __init__(self, db: Session, demand_count=None) -> None:
        self.db = db
        self.demand_count = demand_count
        self.customers = CustomerRepository(db)
        self.interactions = CustomerInteractionRepository(db)
        self.follow_ups = FollowUpRepository(db)
        self.samples = SampleRepository(db)
        self.quotes = QuoteRepository(db)
        self.orders = CommercialOrderRepository(db)

    def create_customer(self, tenant: TenantContext, data: CustomerCreate) -> Customer:
        eligibility = SalesOwnerEligibilityService(self.db)
        can_assign_owner = "commercial:customers:assign_owner" in tenant.permissions

        if can_assign_owner:
            sales_owner_user_id = data.sales_owner_user_id
            if sales_owner_user_id is None:
                raise ValueError("Sales Owner is required.")
            if not eligibility.is_user_eligible(sales_owner_user_id, tenant.organization_id):
                raise ValueError("User is not eligible as Sales Owner.")
        elif eligibility.is_current_user_eligible(tenant):
            if data.sales_owner_user_id is not None and data.sales_owner_user_id != tenant.user_id:
                raise PermissionError(
                    "You do not have permission to assign a different Sales Owner.",
                )
            sales_owner_user_id = tenant.user_id
        else:
            raise PermissionError("You are not eligible to create customers.")

        customer = Customer(
            organization_id=tenant.organization_id,
            created_by_user_id=tenant.user_id,
            sales_owner_user_id=sales_owner_user_id,
            customer_code=self._generate_customer_code(tenant),
            **data.model_dump(exclude={"sales_owner_user_id"}),
        )
        try:
            self.customers.add(customer)
            get_registered_activity_logger().log_activity(self.db, tenant.organization_id, "customer.created", "customer", customer.id, customer.name, tenant.user_id)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Customer could not be saved due to invalid or duplicate data.") from exc

        self.db.refresh(customer)
        return self._attach_customer_associations(tenant, customer)

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
            get_registered_activity_logger().log_activity(self.db, tenant.organization_id, "interaction.created", "interaction", interaction.id, actor_id=tenant.user_id, details={"customer_id": str(customer.id)})
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
        policy: "AuthorizationPolicy | None" = None,
        auth_context: "AuthorizationContext | None" = None,
    ) -> list[CustomerInteraction] | None:
        customer = self.customers.get_by_id(tenant.organization_id, customer_id)
        if customer is None:
            return None

        return self.interactions.list_for_customer(
            tenant.organization_id, customer_id, policy=policy, auth_context=auth_context,
        )

    def create_follow_up(
        self,
        tenant: TenantContext,
        customer_id: UUID,
        data: FollowUpCreate,
    ) -> FollowUp | None:
        customer = self.customers.get_by_id(tenant.organization_id, customer_id)
        if customer is None:
            return None

        if data.interaction_id is not None:
            interaction = self.interactions.get_for_customer(
                tenant.organization_id,
                customer_id,
                data.interaction_id,
            )
            if interaction is None:
                raise ValueError("The selected interaction does not belong to this customer.")

        eligibility = FollowUpAssigneeEligibilityService(self.db)
        can_assign = "commercial:follow_ups:assign" in tenant.permissions

        if can_assign:
            assigned_user_id = data.assigned_user_id or customer.sales_owner_user_id
            if assigned_user_id is None:
                raise ValueError("An assignee is required for this follow-up.")
            if not eligibility.is_user_eligible(assigned_user_id, tenant.organization_id):
                raise ValueError("User is not eligible as a follow-up assignee.")
        elif eligibility.is_current_user_eligible(tenant):
            if data.assigned_user_id is not None and data.assigned_user_id != tenant.user_id:
                raise PermissionError(
                    "You do not have permission to assign this follow-up to another user.",
                )
            assigned_user_id = tenant.user_id
        else:
            raise PermissionError("You are not eligible to create follow-ups.")

        follow_up = FollowUp(
            customer_id=customer.id,
            created_by_user_id=tenant.user_id,
            assigned_user_id=assigned_user_id,
            status=FollowUpStatus.PENDING,
            **data.model_dump(exclude={"assigned_user_id"}),
        )

        try:
            self.follow_ups.add(follow_up)
            get_registered_activity_logger().log_activity(self.db, tenant.organization_id, "followup.created", "followup", follow_up.id, actor_id=tenant.user_id, details={"customer_id": str(customer.id)})
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Follow-up could not be saved due to invalid data.") from exc

        self.db.refresh(follow_up)
        return self._attach_follow_up_associations(tenant, follow_up)

    def get_follow_up_by_id(
        self, tenant: TenantContext, follow_up_id: UUID,
        policy: "AuthorizationPolicy | None" = None, auth_context: "AuthorizationContext | None" = None,
    ) -> FollowUp | None:
        follow_up = self.follow_ups.get_by_id(
            tenant.organization_id, follow_up_id, policy=policy, auth_context=auth_context,
        )
        if follow_up is None:
            return None
        return self._attach_follow_up_associations(tenant, follow_up)

    def list_follow_ups(
        self,
        tenant: TenantContext,
        filters: FollowUpListFilters,
        policy: "AuthorizationPolicy | None" = None,
        auth_context: "AuthorizationContext | None" = None,
    ) -> tuple[list[FollowUp], int]:
        items, total = self.follow_ups.list_filtered(
            tenant.organization_id, filters, policy=policy, auth_context=auth_context,
        )
        return [self._attach_follow_up_associations(tenant, item) for item in items], total

    def list_follow_ups_for_customer(
        self,
        tenant: TenantContext,
        customer_id: UUID,
        policy: "AuthorizationPolicy | None" = None,
        auth_context: "AuthorizationContext | None" = None,
    ) -> list[FollowUp] | None:
        customer = self.customers.get_by_id(tenant.organization_id, customer_id)
        if customer is None:
            return None

        items = self.follow_ups.list_by_customer(
            tenant.organization_id, customer_id, policy=policy, auth_context=auth_context,
        )
        return [self._attach_follow_up_associations(tenant, item) for item in items]

    def update_follow_up(
        self,
        tenant: TenantContext,
        follow_up_id: UUID,
        data: FollowUpUpdate,
    ) -> FollowUp | None:
        follow_up = self.follow_ups.get_by_id(tenant.organization_id, follow_up_id)
        if follow_up is None:
            return None

        payload = data.model_dump(exclude_unset=True)

        if "assigned_user_id" in payload:
            new_assignee = payload["assigned_user_id"]
            if new_assignee != follow_up.assigned_user_id:
                if "commercial:follow_ups:assign" not in tenant.permissions:
                    raise PermissionError(
                        "You do not have permission to reassign this follow-up.",
                    )
                if new_assignee is not None:
                    eligibility = FollowUpAssigneeEligibilityService(self.db)
                    if not eligibility.is_user_eligible(new_assignee, tenant.organization_id):
                        raise ValueError("User is not eligible as a follow-up assignee.")

        for field, value in payload.items():
            setattr(follow_up, field, value)

        try:
            get_registered_activity_logger().log_activity(self.db, tenant.organization_id, "followup.updated", "followup", follow_up.id, actor_id=tenant.user_id, details=payload)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Follow-up could not be saved due to invalid data.") from exc

        self.db.refresh(follow_up)
        return self._attach_follow_up_associations(tenant, follow_up)

    def delete_follow_up(self, tenant: TenantContext, follow_up_id: UUID) -> bool:
        follow_up = self.follow_ups.get_by_id(tenant.organization_id, follow_up_id)
        if follow_up is None:
            return False
        self.follow_ups.delete(follow_up)
        get_registered_activity_logger().log_activity(self.db, tenant.organization_id, "followup.deleted", "followup", follow_up.id, actor_id=tenant.user_id)
        self.db.commit()
        return True

    def complete_follow_up(
        self,
        tenant: TenantContext,
        follow_up_id: UUID,
        data: FollowUpComplete,
    ) -> FollowUp | None:
        follow_up = self.follow_ups.get_by_id(tenant.organization_id, follow_up_id)
        if follow_up is None:
            return None
        if follow_up.status not in (FollowUpStatus.PENDING, FollowUpStatus.IN_PROGRESS):
            raise ValueError("This action cannot be performed on the current status.")

        follow_up.status = FollowUpStatus.COMPLETED
        follow_up.completed_at = data.completed_at or utc_now()
        if data.notes is not None:
            follow_up.notes = data.notes

        get_registered_activity_logger().log_activity(self.db, tenant.organization_id, "followup.completed", "followup", follow_up.id, actor_id=tenant.user_id)
        self.db.commit()
        self.db.refresh(follow_up)
        return self._attach_follow_up_associations(tenant, follow_up)

    def reopen_follow_up(self, tenant: TenantContext, follow_up_id: UUID) -> FollowUp | None:
        follow_up = self.follow_ups.get_by_id(tenant.organization_id, follow_up_id)
        if follow_up is None:
            return None
        if follow_up.status not in (FollowUpStatus.COMPLETED, FollowUpStatus.CANCELLED):
            raise ValueError("This action cannot be performed on the current status.")

        follow_up.status = FollowUpStatus.PENDING
        follow_up.completed_at = None

        get_registered_activity_logger().log_activity(self.db, tenant.organization_id, "followup.reopened", "followup", follow_up.id, actor_id=tenant.user_id)
        self.db.commit()
        self.db.refresh(follow_up)
        return self._attach_follow_up_associations(tenant, follow_up)

    def cancel_follow_up(self, tenant: TenantContext, follow_up_id: UUID) -> FollowUp | None:
        follow_up = self.follow_ups.get_by_id(tenant.organization_id, follow_up_id)
        if follow_up is None:
            return None
        if follow_up.status not in (FollowUpStatus.PENDING, FollowUpStatus.IN_PROGRESS):
            raise ValueError("This action cannot be performed on the current status.")

        follow_up.status = FollowUpStatus.CANCELLED
        follow_up.completed_at = None

        get_registered_activity_logger().log_activity(self.db, tenant.organization_id, "followup.cancelled", "followup", follow_up.id, actor_id=tenant.user_id)
        self.db.commit()
        self.db.refresh(follow_up)
        return self._attach_follow_up_associations(tenant, follow_up)

    def get_eligible_follow_up_assignees(
        self,
        tenant: TenantContext,
    ) -> list[EligibleSalesOwnerResponse]:
        eligibility = FollowUpAssigneeEligibilityService(self.db)
        users = eligibility.list_eligible_users(tenant.organization_id)
        return [
            EligibleSalesOwnerResponse(
                id=user.id,
                full_name=user.full_name,
                email=user.email,
                status=user.status.value,
                roles=self._get_role_summaries(user.id, tenant.organization_id),
                workforce=self._get_workforce_summary(user.id, tenant.organization_id),
            )
            for user in users
        ]

    def reassign_open_follow_ups_by_user(
        self,
        tenant: TenantContext,
        from_user_id: UUID,
        to_user_id: UUID,
    ) -> int:
        if from_user_id == to_user_id:
            raise ValueError("Source and replacement users must be different.")

        foundation = FoundationService(self.db)
        from_user = foundation.get_user_by_id_in_organization(
            from_user_id,
            tenant.organization_id,
        )
        to_user = foundation.get_user_by_id_in_organization(
            to_user_id,
            tenant.organization_id,
        )
        if from_user is None or to_user is None:
            raise ValueError("Both users must belong to the current organization.")

        eligibility = FollowUpAssigneeEligibilityService(self.db)
        if not eligibility.is_user_eligible(to_user_id, tenant.organization_id):
            raise ValueError("Replacement user is not eligible as a follow-up assignee.")

        try:
            count = self.follow_ups.reassign_open_by_user(
                tenant.organization_id,
                from_user_id,
                to_user_id,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return count

    def _attach_follow_up_associations(
        self,
        tenant: TenantContext,
        follow_up: FollowUp,
    ) -> FollowUp:
        follow_up.customer = FollowUpCustomerSummary(
            id=follow_up.customer_id,
            customer_code="",
            customer_name="",
        )
        customer = self.customers.get_by_id(tenant.organization_id, follow_up.customer_id)
        if customer is not None:
            follow_up.customer = FollowUpCustomerSummary(
                id=customer.id,
                customer_code=customer.customer_code,
                customer_name=customer.name,
            )

        follow_up.is_overdue = (
            follow_up.due_date < utc_now()
            and follow_up.status not in (FollowUpStatus.COMPLETED, FollowUpStatus.CANCELLED)
        )

        foundation = FoundationService(self.db)

        if follow_up.created_by_user_id is None:
            follow_up.created_by = None
        else:
            creator = foundation.get_user_by_id_in_organization(
                follow_up.created_by_user_id,
                tenant.organization_id,
            )
            follow_up.created_by = (
                CreatedBySummary(id=creator.id, full_name=creator.full_name)
                if creator is not None
                else None
            )

        if follow_up.assigned_user_id is None:
            follow_up.assigned_user = None
        else:
            assignee = foundation.get_user_by_id_in_organization(
                follow_up.assigned_user_id,
                tenant.organization_id,
            )
            follow_up.assigned_user = (
                FollowUpAssignedUser(
                    id=assignee.id,
                    full_name=assignee.full_name,
                    email=assignee.email,
                    workforce=self._get_workforce_summary(assignee.id, tenant.organization_id),
                )
                if assignee is not None
                else None
            )

        return follow_up

    def list_customers(
        self, tenant: TenantContext,
        policy: "AuthorizationPolicy | None" = None, auth_context: "AuthorizationContext | None" = None,
    ) -> list[Customer]:
        customers = self.customers.list_by_organization(
            tenant.organization_id, policy=policy, auth_context=auth_context,
        )
        return [self._attach_customer_associations(tenant, customer) for customer in customers]

    def get_customer(
        self, tenant: TenantContext, customer_id: UUID,
        policy: "AuthorizationPolicy | None" = None, auth_context: "AuthorizationContext | None" = None,
    ) -> Customer | None:
        customer = self.customers.get_by_id(
            tenant.organization_id, customer_id, policy=policy, auth_context=auth_context,
        )
        if customer is None:
            return None
        return self._attach_customer_associations(tenant, customer)

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

        if payload.get("status") is not None and payload["status"] != "active" and self.demand_count and self.demand_count.count_demands_for_customer(self.db, customer_id, tenant.organization_id, active_only=True):
            raise ValueError("Customer has active production demands. Cancel or complete them before deactivation.")

        if "sales_owner_user_id" in payload:
            new_owner_id = payload["sales_owner_user_id"]
            if new_owner_id != customer.sales_owner_user_id:
                if "commercial:customers:assign_owner" not in tenant.permissions:
                    raise PermissionError(
                        "You do not have permission to reassign Sales Owner.",
                    )
                if new_owner_id is not None:
                    eligibility = SalesOwnerEligibilityService(self.db)
                    if not eligibility.is_user_eligible(new_owner_id, tenant.organization_id):
                        raise ValueError("User is not eligible as Sales Owner.")

        for field, value in payload.items():
            setattr(customer, field, value)

        try:
            get_registered_activity_logger().log_activity(self.db, tenant.organization_id, "customer.updated", "customer", customer.id, customer.name, tenant.user_id, details=payload)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Customer could not be saved due to invalid or duplicate data.") from exc

        self.db.refresh(customer)
        return self._attach_customer_associations(tenant, customer)

    def get_eligible_sales_owners(self, tenant: TenantContext) -> list[EligibleSalesOwnerResponse]:
        eligibility = SalesOwnerEligibilityService(self.db)
        users = eligibility.list_eligible_users(tenant.organization_id)
        return [
            EligibleSalesOwnerResponse(
                id=user.id,
                full_name=user.full_name,
                email=user.email,
                status=user.status.value,
                roles=self._get_role_summaries(user.id, tenant.organization_id),
                workforce=self._get_workforce_summary(user.id, tenant.organization_id),
            )
            for user in users
        ]

    def reassign_customers_by_owner(self, tenant: TenantContext, from_user_id: UUID, to_user_id: UUID) -> int:
        eligibility = SalesOwnerEligibilityService(self.db)
        if from_user_id == to_user_id:
            raise ValueError("Replacement user must be different from the current owner.")
        foundation = FoundationService(self.db)
        if foundation.get_user_by_id_in_organization(from_user_id, tenant.organization_id) is None:
            raise ValueError("Both users must belong to the current organization.")
        if not eligibility.is_user_eligible(to_user_id, tenant.organization_id):
            raise ValueError("Replacement user is not eligible as Sales Owner.")
        count = self.customers.reassign_active_by_sales_owner(tenant.organization_id, from_user_id, to_user_id)
        get_registered_activity_logger().log_activity(self.db, tenant.organization_id, "customer.bulk_reassigned", "customer", actor_id=tenant.user_id, details={"count": count, "from_user_id": str(from_user_id), "to_user_id": str(to_user_id)})
        self.db.commit()
        return count

    def get_deletion_impact(
        self,
        tenant: TenantContext,
        customer_id: UUID,
    ) -> CustomerDeletionImpact | None:
        customer = self.customers.get_by_id(tenant.organization_id, customer_id)
        if customer is None:
            return None

        quotes = self.quotes.count_by_customer(customer.id)
        orders = self.orders.count_by_customer(customer.id)
        demands = self.demand_count.count_demands_for_customer(self.db, customer.id, tenant.organization_id) if self.demand_count else 0

        return CustomerDeletionImpact(
            interactions=self.interactions.count_by_customer(customer.id),
            follow_ups=self.follow_ups.count_by_customer(customer.id),
            samples=self.samples.count_by_customer(customer.id),
            quotes=quotes,
            orders=orders,
            production_demands=demands,
            is_blocked=quotes > 0 or orders > 0 or demands > 0,
        )

    def delete_customer(self, tenant: TenantContext, customer_id: UUID) -> bool:
        customer = self.customers.get_by_id(tenant.organization_id, customer_id)
        if customer is None:
            return False

        if self.demand_count and self.demand_count.count_demands_for_customer(self.db, customer.id, tenant.organization_id):
            raise ValueError("Customer has production demands and cannot be deleted.")

        if self.quotes.count_by_customer(customer.id) > 0:
            raise ValueError(
                "Cannot delete a customer that has quotes. Remove the quotes first or archive the customer.",
            )
        if self.orders.count_by_customer(customer.id) > 0:
            raise ValueError(
                "Cannot delete a customer that has orders. Remove the orders first or archive the customer.",
            )

        try:
            self.follow_ups.delete_for_customer(customer.id)
            self.interactions.delete_for_customer(customer.id)
            self.samples.delete_for_customer(customer.id)
            self.customers.delete(customer)
            get_registered_activity_logger().log_activity(self.db, tenant.organization_id, "customer.deleted", "customer", customer.id, customer.name, tenant.user_id)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError(
                "Customer could not be deleted because other records still reference it.",
            ) from exc

        return True

    def _generate_customer_code(self, tenant: TenantContext) -> str:
        highest_sequence = self.customers.get_highest_customer_code_sequence(tenant.organization_id)
        self.customers.ensure_code_counter(tenant.organization_id, highest_sequence)
        counter = self.customers.get_code_counter_for_update(tenant.organization_id)
        if counter is None:
            raise ValueError("Customer code counter could not be initialized.")

        counter.last_value += 1
        return f"CUST-{counter.last_value:05d}"

    def _attach_customer_associations(
        self,
        tenant: TenantContext,
        customer: Customer,
    ) -> Customer:
        foundation = FoundationService(self.db)

        if customer.created_by_user_id is None:
            customer.created_by = None
        else:
            creator = foundation.get_user_by_id_in_organization(
                customer.created_by_user_id,
                tenant.organization_id,
            )
            customer.created_by = (
                CreatedBySummary(id=creator.id, full_name=creator.full_name)
                if creator is not None
                else None
            )

        if customer.sales_owner_user_id is None:
            customer.sales_owner = None
        else:
            owner = foundation.get_user_by_id_in_organization(
                customer.sales_owner_user_id,
                tenant.organization_id,
            )
            customer.sales_owner = (
                SalesOwnerSummary(
                    id=owner.id,
                    full_name=owner.full_name,
                    email=owner.email,
                    roles=self._get_role_summaries(owner.id, tenant.organization_id),
                    workforce=self._get_workforce_summary(owner.id, tenant.organization_id),
                )
                if owner is not None
                else None
            )

        return customer

    def _get_role_summaries(self, user_id: UUID, organization_id: UUID) -> list[RoleSummary]:
        foundation = FoundationService(self.db)
        roles = foundation.user_roles.list_roles_for_user(user_id, organization_id)
        return [RoleSummary(id=role.id, code=role.code, name=role.name) for role in roles]

    def _get_workforce_summary(self, user_id: UUID, organization_id: UUID) -> WorkforceSummary | None:
        row = get_workforce_summary_row(self.db, user_id, organization_id)
        if row is None:
            return None
        return WorkforceSummary(
            id=row["id"],
            employee_code=row["employee_code"],
            worker_type=row["worker_type"],
            display_name=row["display_name"],
        )
