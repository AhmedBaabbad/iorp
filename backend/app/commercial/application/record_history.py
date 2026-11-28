"""Commercial record history (PR2 of the unified history, docs/architecture/record-history.md).

Commercial declares which of its records have a "السجل" tab and who may read it; every write below records its
field-level old→new changes in the same transaction through core/interfaces/record_history.

- customer: the customer and everything kept under it (contacts, sites, interactions, follow-ups), plus the quotations,
  samples and sales orders deleted from it (a deleted record has no page of its own any more).
- quote, sample, sales_order: their own changes, lines and status steps (with the reason a step requires).
Complaints keep their own decision history (COMPLAINTS-001), which already records every step with its reason.
"""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from app.core.interfaces.record_history import diff_fields, record_event, register_record_history, safe
from app.core.interfaces.user_directory import directory

CUSTOMER, QUOTE, SAMPLE, SALES_ORDER = 'customer', 'quote', 'sample', 'sales_order'
CUSTOMERS_READ = 'commercial:customers:read'

CUSTOMER_FIELDS = ('name', 'name_ar', 'name_en', 'status', 'sector', 'country', 'city', 'city_other', 'phone', 'email',
                   'relationship_stage', 'opportunity_source', 'priority_level', 'sales_owner', 'key_influencer_name', 'notes')
CONTACT_FIELDS = ('name', 'phone', 'email', 'role', 'active', 'is_default')
SITE_FIELDS = ('name', 'address', 'country', 'city', 'city_other', 'location_url', 'contact', 'active', 'is_default')
INTERACTION_FIELDS = ('interaction_type', 'interaction_date', 'subject', 'summary', 'outcome', 'next_step_hint')
FOLLOW_UP_FIELDS = ('reason', 'due_date', 'priority', 'status', 'assigned_user', 'notes', 'completed_at')
QUOTE_FIELDS = ('sample', 'issue_date', 'valid_until', 'currency', 'attention', 'subject', 'notes', 'tax_rate',
                'tax_amount', 'subtotal_amount', 'discount_amount', 'total_amount')
QUOTE_LINE_FIELDS = ('product_type', 'requested_spec_json', 'quantity', 'unit', 'unit_price', 'discount_percent',
                     'description_ar', 'description_en')
ORDER_FIELDS = ('quote', 'order_date', 'customer_reference', 'requested_delivery_date', 'currency', 'notes')
ORDER_LINE_FIELDS = ('product_type', 'requested_spec_json', 'quantity', 'unit', 'agreed_unit_price')
SAMPLE_FIELDS = ('product_type', 'requested_spec_json', 'status', 'sample_decision', 'is_sample_requested',
                 'requested_sample_quantity', 'unit', 'request_date', 'notes')
EVALUATION_FIELDS = ('result_status', 'evaluation_date', 'comments', 'next_action')


def register():
    from app.commercial.application.visibility import ORDERS_READ, QUOTES_READ, SAMPLES_READ, visible_owner
    from app.commercial.infrastructure.repositories import (CommercialOrderRepository, CustomerRepository, QuoteRepository,
                                                            SampleRepository)

    def visible(repository, permission):
        # The same owner filter the record's own page uses (RBAC-002): an "own" reader sees only their customers' records.
        def check(db, tenant, entity_id):
            repo = repository(db)
            repo.owner_user_id = visible_owner(db, tenant, permission)
            return repo.get_by_id(tenant.organization_id, entity_id) is not None
        return check

    register_record_history(CUSTOMER, CUSTOMERS_READ, visible(CustomerRepository, CUSTOMERS_READ))
    register_record_history(QUOTE, QUOTES_READ, visible(QuoteRepository, QUOTES_READ))
    register_record_history(SAMPLE, SAMPLES_READ, visible(SampleRepository, SAMPLES_READ))
    register_record_history(SALES_ORDER, ORDERS_READ, visible(CommercialOrderRepository, ORDERS_READ))


def _plain(value):
    # 1000, 1000.0 and 1000.000 are one quantity: a value read back from the database is not a change.
    if isinstance(value, Decimal):
        return format(value.normalize(), 'f')
    if isinstance(value, float):
        return _plain(Decimal(str(value)))
    if isinstance(value, datetime):
        # One instant, however it was written (stored UTC, or a request's own offset).
        return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat()
    return value


def snapshot(row, fields):
    """The business fields of a record, as plain values (only those the record has)."""
    return {f: _plain(getattr(row, f)) for f in fields if hasattr(row, f)}


def changes(before, after, fields):
    return diff_fields(before, after, [f for f in fields if f in before or f in after])


def lines(rows, fields) -> dict:
    """A document's lines by line number, copied before an edit replaces them."""
    return {row.line_no: snapshot(row, fields) for row in rows}


def line_changes(old: dict, new: dict, fields):
    """Line by line (from lines()): each change carries its line and whether the line was added, removed or changed."""
    result = []
    for no in sorted(set(old) | set(new)):
        kind = 'added' if no not in old else 'removed' if no not in new else 'changed'
        for change in changes(old.get(no, {}), new.get(no, {}), fields):
            if kind != 'changed' and change['old'] in (None, '', {}) and change['new'] in (None, '', {}):
                continue
            result.append(dict(change, line=no, line_change=kind))
    return result


def people(db, organization_id, values: dict, keys: dict) -> dict:
    """Replace user ids by names ({'sales_owner_user_id': 'sales_owner'}): history shows people, never ids."""
    ids = [values.get(k) for k in keys if values.get(k)]
    names = directory().names(db, organization_id, ids) if ids else {}
    out = {k: v for k, v in values.items() if k not in keys}
    for key, name in keys.items():
        if key in values:
            out[name] = names.get(values[key]) if values[key] else None
    return out


def event(db, tenant, entity_type, entity_id, name, action, before=None, after=None, fields=(), extra=None,
          reason=None, related=None):
    """One history entry; nothing is written for an edit that changed nothing."""
    found = changes(before or {}, after or {}, fields) if fields else []
    found += extra or []
    if before is not None and after is not None and not found and not reason:
        return
    record_event(db, tenant.organization_id, entity_type, entity_id, name, action, tenant, found,
                 (reason or '').strip() or None, safe(related or {}))


def created(values: dict, fields):
    """The values a new record starts with, as changes from empty."""
    return changes({}, {k: v for k, v in values.items() if v not in (None, '', [], {})}, fields)


def customer_name(db, tenant, customer_id):
    from sqlalchemy import select
    from app.commercial.infrastructure.models import Customer
    return db.scalar(select(Customer.name).where(Customer.organization_id == tenant.organization_id, Customer.id == customer_id))


def subject(kind: str, record_id: UUID | None, name) -> dict:
    """The child record a customer entry is about (a contact, a site, an interaction, a quotation…)."""
    return dict(subject_kind=kind, subject_id=record_id, subject_name=name)
