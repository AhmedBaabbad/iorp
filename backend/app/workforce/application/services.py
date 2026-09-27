from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.tenancy import TenantContext, validate_same_organization
from app.core.interfaces.activity_log import get_registered_activity_logger
from app.foundation.application.services import FoundationService
from app.workforce.api.schemas import (
    LinkedUser,
    WorkforceMemberCreate,
    WorkforceMemberResponse,
    WorkforceMemberUpdate,
)
from app.workforce.infrastructure.models import WorkforceMember
from app.workforce.infrastructure.repositories import WorkforceRepository


class WorkforceService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.workforce = WorkforceRepository(db)
        self.foundation = FoundationService(db)

    def create_workforce_member(
        self,
        tenant: TenantContext,
        data: WorkforceMemberCreate,
    ) -> WorkforceMemberResponse:
        if self.foundation.get_organization(tenant.organization_id) is None:
            raise ValueError("Current organization does not exist.")

        payload = data.model_dump()

        try:
            member = self.workforce.create_workforce_member(payload, tenant.organization_id)
            get_registered_activity_logger().log_activity(self.db, tenant.organization_id, "workforce_member.created", "workforce_member", member.id, member.full_name, tenant.user_id)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Workforce member could not be saved due to invalid or duplicate data.") from exc

        self.db.refresh(member)
        return self._to_response(member)

    def get_workforce_member_by_id(
        self,
        member_id: UUID,
        organization_id: UUID,
    ) -> WorkforceMemberResponse | None:
        member = self.workforce.get_workforce_member_by_id(member_id, organization_id)
        if member is None:
            return None
        return self._to_response(member)

    def list_workforce_members(
        self,
        organization_id: UUID,
        filters: dict | None = None,
    ) -> list[WorkforceMember]:
        return self.workforce.list_workforce_members(organization_id, filters)

    def update_workforce_member(
        self,
        member_id: UUID,
        organization_id: UUID,
        data: WorkforceMemberUpdate,
    ) -> WorkforceMemberResponse | None:
        payload = data.model_dump(exclude_unset=True)

        try:
            member = self.workforce.update_workforce_member(member_id, organization_id, payload)
            if member is None:
                return None
            get_registered_activity_logger().log_activity(self.db, organization_id, "workforce_member.updated", "workforce_member", member.id, member.full_name, details=payload)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Workforce member could not be saved due to invalid or duplicate data.") from exc

        self.db.refresh(member)
        return self._to_response(member)

    def delete_workforce_member(self, member_id: UUID, organization_id: UUID) -> bool:
        try:
            deleted = self.workforce.delete_workforce_member(member_id, organization_id)
            if not deleted:
                return False
            get_registered_activity_logger().log_activity(self.db, organization_id, "workforce_member.deleted", "workforce_member", member_id)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Workforce member could not be deleted because other records still reference it.") from exc

        return True

    def link_user_to_member(
        self,
        member_id: UUID,
        user_id: UUID,
        organization_id: UUID,
    ) -> WorkforceMemberResponse | None:
        self._validate_user_link(user_id, organization_id, member_id)
        try:
            member = self.workforce.link_user_to_member(member_id, user_id, organization_id)
            if member is None:
                return None
            get_registered_activity_logger().log_activity(self.db, organization_id, "workforce_member.user_linked", "workforce_member", member.id, member.full_name, details={"user_id": str(user_id)})
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("User could not be linked to this workforce member.") from exc

        self.db.refresh(member)
        return self._to_response(member)

    def unlink_user_from_member(
        self,
        member_id: UUID,
        organization_id: UUID,
    ) -> WorkforceMemberResponse | None:
        try:
            member = self.workforce.unlink_user_from_member(member_id, organization_id)
            if member is None:
                return None
            get_registered_activity_logger().log_activity(self.db, organization_id, "workforce_member.user_unlinked", "workforce_member", member.id, member.full_name)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("User could not be unlinked from this workforce member.") from exc

        self.db.refresh(member)
        return self._to_response(member)

    def _validate_user_link(
        self,
        user_id: UUID,
        organization_id: UUID,
        current_member_id: UUID | None = None,
    ) -> None:
        user = self.foundation.get_user_by_id_in_organization(user_id, organization_id)
        if user is None:
            raise ValueError("User must belong to the current organization.")
        if user.status.value != "active":
            raise ValueError("Only active users can be linked to a workforce member.")

        linked_member = self.workforce.get_by_user_id(user_id, organization_id)
        if linked_member is not None and linked_member.id != current_member_id:
            raise ValueError("User is already linked to another workforce member.")

    def _to_response(self, member: WorkforceMember) -> WorkforceMemberResponse:
        response = WorkforceMemberResponse.model_validate(member)
        if member.user_id is not None:
            user = self.foundation.get_user(member.user_id)
            if user is not None:
                validate_same_organization(
                    user.organization_id,
                    member.organization_id,
                    "user",
                )
                roles = self.foundation.get_user_roles(user.id, member.organization_id)
                response.linked_user = LinkedUser(
                    id=user.id,
                    full_name=user.full_name,
                    email=user.email,
                    status=user.status.value,
                    roles=[role.code for role in roles],
                )
        return response
