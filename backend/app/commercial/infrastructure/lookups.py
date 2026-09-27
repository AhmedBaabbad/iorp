from copy import deepcopy
from sqlalchemy import or_, select

from app.core.interfaces.production_demand_lookups import CustomerSummary, QuoteSummary, QuoteItemSummary
from app.commercial.infrastructure.models import Customer, Quote, QuoteItem


class CommercialCustomerLookup:
    @staticmethod
    def _summary(row):
        return CustomerSummary(row.id, row.customer_code, row.name, row.organization_id)

    def get_customer_summary(self, db, customer_id, organization_id):
        row = db.scalar(select(Customer).where(Customer.id == customer_id, Customer.organization_id == organization_id))
        return self._summary(row) if row else None

    def find_customers(self, db, organization_id, search, active_only=True):
        query = select(Customer).where(Customer.organization_id == organization_id)
        if active_only:
            query = query.where(Customer.status == "active")
        if search:
            query = query.where(or_(Customer.name.icontains(search, autoescape=True), Customer.customer_code.icontains(search, autoescape=True)))
        return [self._summary(row) for row in db.scalars(query.order_by(Customer.name, Customer.id))]


class CommercialQuoteLookup:
    @staticmethod
    def _summary(row):
        return QuoteSummary(row.id, row.quote_number, row.customer_id, row.issue_date.date() if row.issue_date else None, row.status.value, row.organization_id)

    def get_quote_summary(self, db, quote_id, organization_id):
        row = db.scalar(select(Quote).where(Quote.id == quote_id, Quote.organization_id == organization_id))
        return self._summary(row) if row else None

    def find_quotes(self, db, customer_id, organization_id):
        return [self._summary(row) for row in db.scalars(select(Quote).where(Quote.customer_id == customer_id, Quote.organization_id == organization_id).order_by(Quote.issue_date.desc(), Quote.id))]

    def get_quote_items(self, db, quote_id, organization_id):
        query = select(QuoteItem).join(Quote).where(Quote.id == quote_id, Quote.organization_id == organization_id).order_by(QuoteItem.line_no, QuoteItem.id)
        return [QuoteItemSummary(row.id, row.line_no, row.product_type, deepcopy(row.requested_spec_json), row.quantity, row.unit, None) for row in db.scalars(query)]
