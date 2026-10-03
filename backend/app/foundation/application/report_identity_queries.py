"""Public tenant identity reads for module reporting; no user contact details are exposed."""
from sqlalchemy import select
from app.foundation.infrastructure.models import Organization, User


class ReportIdentityQueries:
    def __init__(self, db, tenant):
        self.db, self.tenant = db, tenant

    def timezone(self):
        return self.db.scalar(select(Organization.timezone).where(Organization.id == self.tenant.organization_id)) or 'UTC'

    def user_names(self, ids, search=None):
        query = select(User.id, User.full_name).where(User.organization_id == self.tenant.organization_id, User.id.in_(ids))
        if search is not None:
            query = query.where(User.full_name.icontains(search, autoescape=True)).limit(50)
        return dict(self.db.execute(query).all())
