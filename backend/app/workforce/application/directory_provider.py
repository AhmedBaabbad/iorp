from sqlalchemy import case, select
from app.workforce.infrastructure.models import WorkforceMember


def personal(member):
    return dict(id=member.id, name=member.full_name, phone=member.phone, email=member.email,
                identity_no=member.national_id, worker_type=member.worker_type.value)


class WorkforceDirectoryProvider:
    def member(self, db, org, member_id, *, active_only=False, lock=False):
        query = select(WorkforceMember).where(WorkforceMember.organization_id == org, WorkforceMember.id == member_id)
        if active_only:
            query = query.where(WorkforceMember.status == 'active')
        if lock:
            query = query.with_for_update()
        row = db.scalar(query.execution_options(populate_existing=True))
        return personal(row) if row else None

    def members(self, db, org, search=""):
        query = select(WorkforceMember).where(WorkforceMember.organization_id == org,
            WorkforceMember.status == 'active', WorkforceMember.full_name.icontains(search, autoescape=True))
        query = query.order_by(case((WorkforceMember.worker_type == 'driver', 0), else_=1),
                               WorkforceMember.full_name, WorkforceMember.id).limit(50)
        return [personal(row) for row in db.scalars(query)]
