from sqlalchemy import case, select, or_
from app.workforce.infrastructure.models import WorkforceMember


def personal(member):
    return dict(id=member.id, name=member.full_name, phone=member.phone, email=member.email,
                identity_no=member.national_id, worker_type=member.worker_type.value, active=member.status == 'active')


class WorkforceDirectoryProvider:
    def batch(self, db, org, member_ids):
        if not member_ids:return {}
        rows=db.scalars(select(WorkforceMember).where(WorkforceMember.organization_id==org, WorkforceMember.id.in_(member_ids)))
        return {row.id:personal(row) for row in rows}

    def member(self, db, org, member_id, *, active_only=False, lock=False):
        query = select(WorkforceMember).where(WorkforceMember.organization_id == org, WorkforceMember.id == member_id)
        if active_only:
            query = query.where(WorkforceMember.status == 'active')
        if lock:
            query = query.with_for_update()
        row = db.scalar(query.execution_options(populate_existing=True))
        return personal(row) if row else None

    def members(self, db, org, search=""):
        from app.core.phones import phone_search_terms
        query = select(WorkforceMember).where(WorkforceMember.organization_id == org,
            WorkforceMember.status == 'active', or_(WorkforceMember.full_name.icontains(search, autoescape=True),
                *[WorkforceMember.phone.icontains(term, autoescape=True) for term in phone_search_terms(search)], WorkforceMember.national_id.icontains(search, autoescape=True)))
        query = query.order_by(case((WorkforceMember.worker_type == 'driver', 0), else_=1),
                               WorkforceMember.full_name, WorkforceMember.id).limit(50)
        return [personal(row) for row in db.scalars(query)]
