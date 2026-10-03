"""Public, read-only commercial query API. Callers supply already authorized customer IDs."""
from sqlalchemy import select
from app.commercial.infrastructure.models import Quote
from app.core.interfaces.customer_reporting import QuoteRead
from app.core.reporting.contracts import ReportLimitError


class CommercialReportQueries:
    def __init__(self, db, tenant):
        self.db, self.tenant = db, tenant

    def quotations(self, customer_ids):
        rows = list(self.db.scalars(select(Quote).where(Quote.organization_id == self.tenant.organization_id,
                    Quote.customer_id.in_(customer_ids)).order_by(Quote.issue_date, Quote.id).limit(5001)))
        if len(rows) > 5000:
            raise ReportLimitError()
        return [QuoteRead(customer_id=r.customer_id, number=r.quote_number, issued=r.issue_date,
                         status=getattr(r.status, 'value', r.status), currency=r.currency, total=r.total_amount) for r in rows]
