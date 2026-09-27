from uuid import UUID

from sqlalchemy import Integer, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.workforce.infrastructure.models import WorkforceCodeCounter, WorkforceMember
from app.workforce.domain.enums import WorkforceMemberStatus


class WorkforceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_workforce_member(
        self,
        data: dict,
        organization_id: UUID,
    ) -> WorkforceMember:
        payload = dict(data)
        payload.pop("employee_code", None)
        payload.pop("organization_id", None)
        payload.pop("status", None)
        member = WorkforceMember(
            organization_id=organization_id,
            employee_code=self._generate_employee_code(organization_id),
            status=WorkforceMemberStatus.ACTIVE,
            **payload,
        )
        self.db.add(member)
        self.db.flush()
        return member

    def get_workforce_member_by_id(
        self,
        member_id: UUID,
        organization_id: UUID,
    ) -> WorkforceMember | None:
        statement = select(WorkforceMember).where(
            WorkforceMember.id == member_id,
            WorkforceMember.organization_id == organization_id,
        )
        return self.db.scalar(statement)

    def list_workforce_members(
        self,
        organization_id: UUID,
        filters: dict | None = None,
    ) -> list[WorkforceMember]:
        filters = filters or {}
        statement = select(WorkforceMember).where(WorkforceMember.organization_id == organization_id)

        if filters.get("worker_type") is not None:
            statement = statement.where(WorkforceMember.worker_type == filters["worker_type"])
        if filters.get("employment_type") is not None:
            statement = statement.where(
                WorkforceMember.employment_type == filters["employment_type"],
            )
        if filters.get("status") is not None:
            statement = statement.where(WorkforceMember.status == filters["status"])
        if filters.get("is_system_user") is not None:
            statement = statement.where(
                WorkforceMember.is_system_user == filters["is_system_user"],
            )

        statement = statement.order_by(WorkforceMember.employee_code.asc())

        limit = filters.get("limit")
        offset = filters.get("offset")
        if offset is not None:
            statement = statement.offset(offset)
        if limit is not None:
            statement = statement.limit(limit)

        return list(self.db.scalars(statement))

    def update_workforce_member(
        self,
        member_id: UUID,
        organization_id: UUID,
        data: dict,
    ) -> WorkforceMember | None:
        member = self.get_workforce_member_by_id(member_id, organization_id)
        if member is None:
            return None

        payload = dict(data)
        payload.pop("employee_code", None)
        payload.pop("organization_id", None)
        payload.pop("is_system_user", None)
        payload.pop("user_id", None)
        for field, value in payload.items():
            setattr(member, field, value)
        self.db.flush()
        return member

    def delete_workforce_member(self, member_id: UUID, organization_id: UUID) -> bool:
        member = self.get_workforce_member_by_id(member_id, organization_id)
        if member is None:
            return False

        self.db.delete(member)
        self.db.flush()
        return True

    def link_user_to_member(
        self,
        member_id: UUID,
        user_id: UUID,
        organization_id: UUID,
    ) -> WorkforceMember | None:
        member = self.get_workforce_member_by_id(member_id, organization_id)
        if member is None:
            return None

        linked_member = self.get_by_user_id(user_id, organization_id)
        if linked_member is not None and linked_member.id != member_id:
            raise ValueError("User is already linked to another workforce member.")

        member.user_id = user_id
        self.db.flush()
        return member

    def unlink_user_from_member(
        self,
        member_id: UUID,
        organization_id: UUID,
    ) -> WorkforceMember | None:
        member = self.get_workforce_member_by_id(member_id, organization_id)
        if member is None:
            return None

        member.user_id = None
        self.db.flush()
        return member

    def get_by_user_id(
        self,
        user_id: UUID,
        organization_id: UUID,
    ) -> WorkforceMember | None:
        statement = select(WorkforceMember).where(
            WorkforceMember.organization_id == organization_id,
            WorkforceMember.user_id == user_id,
        )
        return self.db.scalar(statement)

    def _generate_employee_code(self, organization_id: UUID) -> str:
        highest_sequence = self._get_highest_employee_code_sequence(organization_id)
        self._ensure_code_counter(organization_id, highest_sequence)
        counter = self._get_code_counter_for_update(organization_id)
        if counter is None:
            raise ValueError("Workforce code counter could not be initialized.")
        counter.last_value += 1
        return f"WF-{counter.last_value:05d}"

    def _get_highest_employee_code_sequence(self, organization_id: UUID) -> int:
        if self.db.bind is not None and self.db.bind.dialect.name != "postgresql":
            highest = 0
            statement = select(WorkforceMember.employee_code).where(
                WorkforceMember.organization_id == organization_id,
            )
            for employee_code in self.db.scalars(statement):
                upper = employee_code.upper()
                if not upper.startswith("WF-"):
                    continue
                sequence_text = upper.removeprefix("WF-")
                if sequence_text.isdigit():
                    highest = max(highest, int(sequence_text))
            return highest

        sequence_text = func.substring(func.lower(WorkforceMember.employee_code), r"^wf-([0-9]+)$")
        statement = select(func.coalesce(func.max(sequence_text.cast(Integer)), 0)).where(
            WorkforceMember.organization_id == organization_id,
        )
        return int(self.db.scalar(statement) or 0)

    def _ensure_code_counter(self, organization_id: UUID, last_value: int) -> None:
        if self.db.bind is not None and self.db.bind.dialect.name != "postgresql":
            counter = self.db.get(WorkforceCodeCounter, organization_id)
            if counter is None:
                self.db.add(
                    WorkforceCodeCounter(
                        organization_id=organization_id,
                        last_value=last_value,
                    ),
                )
                self.db.flush()
            return

        statement = (
            insert(WorkforceCodeCounter)
            .values(organization_id=organization_id, last_value=last_value)
            .on_conflict_do_nothing(index_elements=[WorkforceCodeCounter.organization_id])
        )
        self.db.execute(statement)
        self.db.flush()

    def _get_code_counter_for_update(
        self,
        organization_id: UUID,
    ) -> WorkforceCodeCounter | None:
        statement = (
            select(WorkforceCodeCounter)
            .where(WorkforceCodeCounter.organization_id == organization_id)
            .with_for_update()
        )
        return self.db.scalar(statement)
