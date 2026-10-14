"""Customer complaints (COMPLAINTS-001): intake, assignment, investigation, resolution and closure, inside Commercial.

Commercial is the only writer of the complaint tables. Other modules are read through shared tables (Base.metadata) to
check and show references, and Quality opens its own non-conformance report through core/interfaces/complaint_quality.

Every decision is a history entry whose facts are stored by name (`details`: department, owner, dates, statuses,
references) apart from what the person wrote (`notes`), so screens and reports word them in the reader's language.
"""
from pathlib import Path
from uuid import UUID
from sqlalchemy import case, func, or_, select
from fastapi import HTTPException
from app.core.interfaces.reference_lists import unknown_list_values
from app.core.interfaces import approvals
from app.core.authorization.scope_resolver import resolve_effective_scope
from app.core.interfaces.authorization_policy import AccessScope
from app.core.interfaces.product_catalog import products
from app.core.pagination import page_of, paginate
from app.core.units import UNITS
from app.core.utils import utc_now
from app.core import files
from app.core.storage import InvalidAttachmentError, LocalFileStorage, compensate_new_file
from app.core import numbering
from app.commercial.application import notices
from app.commercial.application.visibility import SAMPLES_READ
from app.commercial.domain.complaints import ACTIONS, PREFIX, allowed
from app.commercial.infrastructure.models import CommercialOrder, CommercialOrderItem, Customer, Sample
from app.commercial.infrastructure.complaint_models import (
    Complaint, ComplaintAttachment, ComplaintCodeCounter, ComplaintEvent, ComplaintItem, ComplaintItemProperty, ComplaintLink,
)
from app.commercial.infrastructure.complaint_queries import LINKS, eligible_users, organization_today, reference_query, table, user_names

LOCKED = ('closed', 'cancelled', 'pending_closure')
ACTIVE_FILTER_EXCLUDED = ('closed', 'cancelled')


def fail(code, status=409):
    raise HTTPException(status, detail=code)


def _text(value):
    return '' if value is None else str(value)


class ComplaintService:
    def __init__(self, db, tenant):
        self.db, self.tenant, self.org = db, tenant, tenant.organization_id

    # ── scope ─────────────────────────────────────────────────────────────────────────────────────
    def customers(self):
        """The customers whose complaints this user may see: all, or their own when their read scope is "own"."""
        q = select(Customer).where(Customer.organization_id == self.org)
        scope = resolve_effective_scope(self.db, self.tenant.user_id, self.org, PREFIX + 'read', self.tenant.is_organization_root)
        if scope != AccessScope.ORGANIZATION:
            q = q.where(Customer.sales_owner_user_id == self.tenant.user_id)
        return q

    def customer(self, cid):
        row = self.db.scalar(self.customers().where(Customer.id == cid))
        if row is None:
            fail('CUSTOMER_NOT_FOUND', 404)
        return row

    def query(self):
        return select(Complaint).where(Complaint.organization_id == self.org, Complaint.customer_id.in_(self.customers().with_only_columns(Customer.id)))

    def get(self, cid, version=None):
        q = self.query().where(Complaint.id == cid)
        if version is not None:
            q = q.with_for_update().execution_options(populate_existing=True)
        row = self.db.scalar(q)
        if not row:
            fail('COMPLAINT_NOT_FOUND', 404)
        if version is not None and row.version != version:
            fail('COMPLAINT_CHANGED')
        return row

    def writable(self, row):
        if row.status in LOCKED:
            fail('COMPLAINT_LOCKED')

    def event(self, row, action, notes='', **details):
        self.db.add(ComplaintEvent(organization_id=self.org, complaint_id=row.id, actor_id=self.tenant.user_id, action=action,
                                   notes=notes or '', details={k: v for k, v in details.items() if v not in (None, '', [], {})}))
        row.version += 1
        row.updated_at = utc_now()

    # ── numbering ─────────────────────────────────────────────────────────────────────────────────
    def next_number(self):
        """CC-<year>-0001, one sequence per organization and year, taken under a row lock (no count()+1 race)."""
        year = numbering.organization_year(self.db, self.org)
        return numbering.reference('CC', year, numbering.take(self.db, ComplaintCodeCounter, value_field='last_value', organization_id=self.org, year=year))

    # ── product lines ─────────────────────────────────────────────────────────────────────────────
    def source_spec(self, customer_id, kind, source_id, product_key, can):
        """The agreed specification of a sales order line or a sample of this customer, and how it is named."""
        if not self.reference_allowed(customer_id, kind, can):
            fail('REFERENCE_PERMISSION_REQUIRED', 403)
        if kind == 'order':
            row = self.db.execute(select(CommercialOrderItem, CommercialOrder.order_number).join(CommercialOrder, CommercialOrder.id == CommercialOrderItem.commercial_order_id)
                                  .where(CommercialOrder.organization_id == self.org, CommercialOrder.customer_id == customer_id,
                                         CommercialOrderItem.id == source_id)).first()
            if row is None:
                fail('SOURCE_NOT_FOUND', 404)
            line, number = row
            label = f'{number} / {line.line_no}'
        else:
            line = self.db.scalar(self.samples(customer_id).where(Sample.id == source_id))
            if line is None:
                fail('SOURCE_NOT_FOUND', 404)
            label = line.sample_code
        if line.product_type != product_key:
            fail('SOURCE_PRODUCT_MISMATCH', 422)
        return {str(k): _text(v) for k, v in (line.requested_spec_json or {}).items()}, label

    def samples(self, customer_id):
        # A sample belongs to the organization through its customer (the table has no tenant column).
        return select(Sample).join(Customer, Customer.id == Sample.customer_id).where(Customer.organization_id == self.org, Sample.customer_id == customer_id)

    def build_items(self, row, inputs, can):
        """Validate the lines and write them on the complaint; an edited line keeps its measurements and confirmed quantity."""
        existing = {item.id: item for item in row.items}
        catalogue = products(self.db, self.org, [i.product_key for i in inputs])
        kept = []
        for number, data in enumerate(inputs, 1):
            old = existing.get(data.id) if data.id else None
            if data.id and old is None:
                fail('ITEM_NOT_FOUND', 404)
            product = catalogue.get(data.product_key)
            if not product or (not product.active and not (old and old.product_key == data.product_key)):
                fail('PRODUCT_NOT_AVAILABLE', 422)
            if data.unit not in UNITS:
                fail('UNIT_INVALID', 422)
            definitions = {p.key: p for p in product.properties}
            keys = [p.key for p in data.properties]
            if len(set(keys)) != len(keys) or any(k not in definitions for k in keys):
                fail('PROPERTY_INVALID', 422)
            agreed, label = ({}, None) if data.source_kind == 'manual' else self.source_spec(row.customer_id, data.source_kind, data.source_id, data.product_key, can)
            reported = {p.key: p for p in data.properties}
            wanted = [k for k in definitions if k in reported or k in agreed]  # in the product's own order
            measured = {p.key: p.measured for p in old.properties} if old else {}
            item = old or ComplaintItem(organization_id=self.org)
            item.line_no, item.product_key, item.product_name = number, data.product_key, product.name_ar
            item.batch_reference, item.unit = data.batch_reference, data.unit
            item.delivered_quantity, item.reported_quantity = data.delivered_quantity, data.reported_quantity
            if item.confirmed_quantity is not None and item.confirmed_quantity > data.delivered_quantity:
                fail('CONFIRMED_EXCEEDS_DELIVERED', 422)
            item.source_kind, item.source_id, item.source_label = data.source_kind, data.source_id, label
            item.properties.clear()
            self.db.flush()
            for n, key in enumerate(wanted, 1):
                d = definitions[key]
                expected = agreed.get(key, '') if data.source_kind != 'manual' else reported[key].expected
                item.properties.append(ComplaintItemProperty(organization_id=self.org, line_no=n, key=key, name_ar=d.name_ar, name_en=d.name_en,
                    unit=d.unit, expected=expected, reported=reported[key].reported if key in reported else '', measured=measured.get(key, '')))
            if old is None:
                row.items.append(item)
            kept.append(item)
        for item in list(row.items):
            if item not in kept:
                row.items.remove(item)
        return len(kept)

    def sources(self, customer_id, can, search=''):
        """The customer's sales order lines and samples a complaint line can take its agreed specification from."""
        self.customer(customer_id)
        found = []
        if self.reference_allowed(customer_id, 'order', can):
            q = (select(CommercialOrderItem, CommercialOrder.order_number).join(CommercialOrder, CommercialOrder.id == CommercialOrderItem.commercial_order_id)
                 .where(CommercialOrder.organization_id == self.org, CommercialOrder.customer_id == customer_id))
            if search:
                q = q.where(CommercialOrder.order_number.icontains(search, autoescape=True))
            for line, number in self.db.execute(q.order_by(CommercialOrder.order_date.desc(), CommercialOrderItem.line_no).limit(30)):
                found.append(dict(kind='order', id=line.id, label=f'{number} / {line.line_no}', product_key=line.product_type, unit=line.unit,
                                  quantity=line.quantity, spec={str(k): _text(v) for k, v in (line.requested_spec_json or {}).items()}))
        if self.reference_allowed(customer_id, 'sample', can):
            q = self.samples(customer_id)
            if search:
                q = q.where(Sample.sample_code.icontains(search, autoescape=True))
            for sample in self.db.scalars(q.order_by(Sample.request_date.desc(), Sample.id).limit(30)):
                found.append(dict(kind='sample', id=sample.id, label=sample.sample_code, product_key=sample.product_type, unit=sample.unit,
                                  quantity=sample.requested_sample_quantity, spec={str(k): _text(v) for k, v in (sample.requested_spec_json or {}).items()}))
        return found

    # ── writes ────────────────────────────────────────────────────────────────────────────────────
    def create(self, data, can):
        self.customer(data.customer_id)
        if unknown_list_values(self.db, self.org, 'complaint_category', [data.category]):
            fail('LIST_VALUE_UNKNOWN', 422)  # MD-003: from the organization's complaint categories
        row = Complaint(**data.model_dump(exclude={'items'}), organization_id=self.org, number=self.next_number(),
                        created_by=self.tenant.user_id, version=0)
        self.db.add(row)
        self.db.flush()
        self.build_items(row, data.items, can)
        self.db.flush()
        self.event(row, 'created', channel=row.channel, category=row.category, priority=row.priority, lines=len(row.items))
        self.db.commit()
        return row

    def update_items(self, cid, data, can):
        row = self.get(cid, data.version)
        self.writable(row)
        before = len(row.items)
        count = self.build_items(row, data.items, can)
        self.event(row, 'items_updated', lines=count, previous_lines=before)
        self.db.commit()
        return row

    def change(self, cid, data, operation, can):
        row = self.get(cid, data.version)
        if operation != 'transition':
            self.writable(row)
        if operation == 'assign':
            if not eligible_users(self.db, self.tenant, self.customer(row.customer_id), user_id=data.owner_user_id):
                fail('ASSIGNEE_NOT_ELIGIBLE', 422)
            if data.due_date < row.received_date:
                fail('DUE_BEFORE_RECEIPT', 422)
            previous = dict(previous_owner_user_id=str(row.owner_user_id) if row.owner_user_id else None, previous_department=row.department,
                            previous_due_date=row.due_date.isoformat() if row.due_date else None)
            row.owner_user_id, row.department, row.due_date = data.owner_user_id, data.department, data.due_date
            # The first assignment is the initial assessment: it starts the processing.
            started = dict(from_status='new', to_status='processing') if row.status == 'new' else {}
            if started:
                row.status = 'processing'
            self.event(row, 'assign', data.reason, owner_user_id=str(data.owner_user_id), department=data.department,
                       due_date=data.due_date.isoformat(), **previous, **started)
            if previous['previous_owner_user_id'] != str(data.owner_user_id):
                notices.complaint_assigned(self.db, self.tenant, row)
        elif operation == 'investigate':
            previous = {k: getattr(row, k) for k in ('finding', 'investigation', 'containment')}
            for key in previous:
                setattr(row, key, getattr(data, key))
            measured = self.record_findings(row, data.items)
            self.event(row, 'investigate', finding=data.finding, previous_finding=previous['finding'],
                       fields={k: getattr(data, k) for k in ('investigation', 'containment')},
                       previous={k: v for k, v in previous.items() if k != 'finding' and v and v != getattr(data, k)}, items=measured)
        elif operation == 'resolve':
            keys = ('resolution', 'implementation_evidence', 'customer_response')
            previous = {k: getattr(row, k) for k in keys}
            for key in keys:
                setattr(row, key, getattr(data, key))
            self.event(row, 'resolve', fields={k: getattr(data, k) for k in keys},
                       previous={k: v for k, v in previous.items() if v and v != getattr(data, k)})
        elif operation in ('note', 'response'):
            self.event(row, operation, data.notes)
        else:
            sources, target, permission = ACTIONS[data.action]
            if not can(PREFIX + permission):
                fail('ACTION_FORBIDDEN', 403)
            if row.status not in sources:
                fail('TRANSITION_NOT_ALLOWED')
            if data.action in ('request_close', 'approve_close'):
                if row.finding == 'pending' or not all((row.investigation, row.resolution, row.implementation_evidence, row.customer_response)):
                    fail('CLOSURE_EVIDENCE_REQUIRED', 422)
                self.close_guard(row)
            if data.action == 'request_close':
                row.closure_requested_by = self.tenant.user_id
            if data.action == 'approve_close':
                if row.priority == 'critical' and row.closure_requested_by == self.tenant.user_id:
                    fail('INDEPENDENT_APPROVAL_REQUIRED', 422)
                row.closed_at, row.closed_by = utc_now(), self.tenant.user_id
                approvals.sign(self.db, self.tenant, 'complaint', row.id, 'close', PREFIX + 'close', data.reason)
            if data.action == 'reopen':
                row.closed_at = row.closed_by = row.closure_requested_by = None
            from_status, row.status = row.status, target
            self.event(row, data.action, data.reason, from_status=from_status, to_status=target)
            {'request_close': notices.complaint_close_requested, 'approve_close': notices.complaint_closed,
             'reopen': notices.complaint_reopened, 'return': notices.complaint_returned,
             'cancel': notices.complaint_cancelled}.get(data.action, lambda *a: None)(self.db, self.tenant, row)
        self.db.commit()
        return row

    def record_findings(self, row, findings):
        """Measured values and the confirmed affected quantity per line; only properties already on the line."""
        lines = {item.id: item for item in row.items}
        summary = []
        for finding in findings:
            item = lines.get(finding.item_id)
            if item is None:
                fail('ITEM_NOT_FOUND', 404)
            if finding.confirmed_quantity is not None and finding.confirmed_quantity > item.delivered_quantity:
                fail('CONFIRMED_EXCEEDS_DELIVERED', 422)
            props = {p.key: p for p in item.properties}
            if any(m.key not in props for m in finding.measurements):
                fail('PROPERTY_INVALID', 422)
            item.confirmed_quantity = finding.confirmed_quantity
            for m in finding.measurements:
                props[m.key].measured = m.measured
            summary.append(dict(product=item.product_name, confirmed_quantity=_text(item.confirmed_quantity) or None, unit=item.unit,
                                measured={props[m.key].name_ar: m.measured for m in finding.measurements if m.measured},
                                measured_en={props[m.key].name_en: m.measured for m in finding.measurements if m.measured}))
        return summary

    def close_guard(self, row):
        links = self.db.scalars(select(ComplaintLink).where(ComplaintLink.organization_id == self.org, ComplaintLink.complaint_id == row.id,
                                                            ComplaintLink.kind == 'ncr')).all()
        if row.category == 'quality' and row.finding == 'verified' and not links:
            fail('QUALITY_NCR_REQUIRED', 422)
        for link in links:
            t = table('non_conformance_reports')
            ncr = self.db.execute(select(t).where(t.c.organization_id == self.org, t.c.id == link.record_id)).mappings().first()
            if not ncr or ncr['status'] != 'closed' or (ncr['effectiveness_due_date'] and ncr['effectiveness_result'] != 'effective'):
                fail('QUALITY_REVIEW_PENDING', 422)

    def refer_quality(self, cid, data):
        from app.core.interfaces.complaint_quality import refer_complaint
        row = self.get(cid, data.version)
        self.writable(row)
        if self.db.scalar(select(ComplaintLink.id).where(ComplaintLink.organization_id == self.org,
                                                         ComplaintLink.complaint_id == cid, ComplaintLink.kind == 'ncr')):
            fail('REFERENCE_ALREADY_LINKED')
        customer = self.customer(row.customer_id)
        record_id, number = refer_complaint(self.db, self.tenant, number=row.number, title=row.title,
                                            statement=row.statement, customer_id=customer.id, customer_name=customer.name)
        self.db.add(ComplaintLink(organization_id=self.org, complaint_id=cid, kind='ncr', record_id=record_id, created_by=self.tenant.user_id))
        self.event(row, 'refer_quality', data.notes, ncr_number=number)
        self.db.commit()
        return row

    def reference_allowed(self, customer_id, kind, can):
        permission = SAMPLES_READ if kind == 'sample' else LINKS[kind][2]  # a sample is a line's specification source
        if not can(permission):
            return False
        if kind not in ('order', 'sample'):
            return True  # These source resources have no ownership scope; the customer filter applies to them.
        scope = resolve_effective_scope(self.db, self.tenant.user_id, self.org, permission, self.tenant.is_organization_root)
        return scope == AccessScope.ORGANIZATION or self.customer(customer_id).sales_owner_user_id == self.tenant.user_id

    def link(self, cid, data, can):
        row = self.get(cid, data.version)
        self.writable(row)
        if not self.reference_allowed(row.customer_id, data.kind, can):
            fail('REFERENCE_PERMISSION_REQUIRED', 403)
        t = table(LINKS[data.kind][0])
        ref = self.db.execute(reference_query(self.org, row.customer_id, data.kind).where(t.c.id == data.record_id)).mappings().first()
        if not ref:
            fail('REFERENCE_NOT_FOUND', 404)
        if self.db.scalar(select(ComplaintLink.id).where(ComplaintLink.organization_id == self.org, ComplaintLink.complaint_id == cid,
                                                         ComplaintLink.kind == data.kind, ComplaintLink.record_id == data.record_id)):
            fail('REFERENCE_ALREADY_LINKED', 409)
        self.db.add(ComplaintLink(organization_id=self.org, complaint_id=cid, kind=data.kind, record_id=data.record_id, created_by=self.tenant.user_id))
        self.event(row, 'linked', kind=data.kind, label=str(ref[LINKS[data.kind][1]]))
        self.db.commit()
        return row

    def attach(self, cid, version, filename, content):
        row = self.get(cid, version)
        self.writable(row)
        storage = LocalFileStorage()
        try:
            path, prepared = files.store(self.db, storage, self.org, 'commercial', content, 'attachment')
        except InvalidAttachmentError as exc:
            self.db.rollback()
            fail(f'FILE_{exc.code}', 422)
        name = Path(filename or 'attachment').name[:255]
        with compensate_new_file(self.db, storage, path, lambda: self.db.scalar(select(ComplaintAttachment.id).where(
                ComplaintAttachment.organization_id == self.org, ComplaintAttachment.storage_path == path)) is not None):
            self.db.add(ComplaintAttachment(organization_id=self.org, complaint_id=cid, filename=name, storage_path=path,
                                            content_type=prepared.media_type, size_bytes=prepared.size, checksum=prepared.checksum,
                                            created_by=self.tenant.user_id))
            self.event(row, 'attachment', filename=name)
            self.db.commit()
        return row

    # ── reads ─────────────────────────────────────────────────────────────────────────────────────
    def filtered(self, search='', status=None, customer_id=None, department=None, overdue=False):
        q = self.query()
        if search:
            q = q.where(or_(Complaint.number.icontains(search, autoescape=True), Complaint.title.icontains(search, autoescape=True)))
        for col, value in ((Complaint.status, status), (Complaint.customer_id, customer_id), (Complaint.department, department)):
            if value:
                q = q.where(col == value)
        if overdue:
            q = q.where(Complaint.due_date < organization_today(self.db, self.org), Complaint.status.not_in(ACTIVE_FILTER_EXCLUDED))
        return q.order_by(Complaint.created_at.desc(), Complaint.id.desc())

    def list(self, params, can, **filters):
        rows, total = paginate(self.db, self.filtered(**filters), params)
        return page_of(self.views(rows, can, detail=False), total, params)

    def summary(self, customer_id=None, department=None):
        today = organization_today(self.db, self.org)
        scoped = self.filtered(customer_id=customer_id, department=department).order_by(None).subquery()
        active = scoped.c.status.not_in(ACTIVE_FILTER_EXCLUDED)
        responded = select(ComplaintEvent.id).where(ComplaintEvent.organization_id == self.org,
                                                    ComplaintEvent.complaint_id == scoped.c.id, ComplaintEvent.action == 'response').exists()
        query = select(func.count().label('total'),
                       func.count(case((active, 1))).label('active'),
                       func.count(case((active & (scoped.c.due_date < today), 1))).label('overdue'),
                       func.count(case((active & (scoped.c.response_due_date < today) & ~responded, 1))).label('response_overdue'),
                       func.count(case((scoped.c.status == 'pending_closure', 1))).label('pending_closure'),
                       func.count(case((scoped.c.status == 'closed', 1))).label('closed')).select_from(scoped)
        return dict(self.db.execute(query).mappings().one())

    def views(self, rows, can, detail=True):
        """Rows as the screens show them; customers and people are read once for all the rows (no query per row)."""
        if not rows:
            return []
        customers = dict(self.db.execute(select(Customer.id, Customer.name).where(Customer.organization_id == self.org,
                                                                                  Customer.id.in_({r.customer_id for r in rows}))).all())
        names = user_names(self.db, self.org, list({x for r in rows for x in (r.owner_user_id, r.created_by, r.closed_by) if x}))
        today = organization_today(self.db, self.org)
        return [self._view(r, can, detail, customers, names, today) for r in rows]

    def view(self, row, can, detail=True):
        return self.views([row], can, detail)[0]

    def _view(self, row, can, detail, customers, names, today):
        result = {c.name: getattr(row, c.name) for c in Complaint.__table__.columns}
        result.update(customer_name=customers.get(row.customer_id), owner_name=names.get(row.owner_user_id), created_by_name=names.get(row.created_by),
                      closed_by_name=names.get(row.closed_by), actions=allowed(row.status, can))
        if row.status not in LOCKED:
            operations = (('assign', 'assign'), ('investigate', 'investigate'), ('resolve', 'resolve'), ('items', 'update'), ('communicate', 'update'),
                          ('link', 'update'), ('attach', 'update'))
            result['actions'] += [op for op, perm in operations if can(PREFIX + perm)]
            if can(PREFIX + 'investigate') and can('quality:ncr_reports:create'):
                result['actions'].append('refer_quality')
        result['overdue'] = bool(row.due_date and row.due_date < today and row.status not in ACTIVE_FILTER_EXCLUDED)
        if not detail:
            return result
        result['items'] = [dict({c.name: getattr(i, c.name) for c in ComplaintItem.__table__.columns},
                                properties=[{c.name: getattr(p, c.name) for c in ComplaintItemProperty.__table__.columns} for p in i.properties])
                           for i in row.items]
        result['events'] = self.history(row)
        result['links'] = []
        for link in self.db.scalars(select(ComplaintLink).where(ComplaintLink.organization_id == self.org, ComplaintLink.complaint_id == row.id)):
            if self.reference_allowed(row.customer_id, link.kind, can):
                t = table(LINKS[link.kind][0])
                ref = self.db.execute(reference_query(self.org, row.customer_id, link.kind).where(t.c.id == link.record_id)).mappings().first()
                if ref:
                    result['links'].append(dict(kind=link.kind, record_id=link.record_id, label=ref[LINKS[link.kind][1]], href=LINKS[link.kind][3] + str(link.record_id)))
        result['attachments'] = [dict(id=a.id, filename=a.filename) for a in self.db.scalars(select(ComplaintAttachment).where(
            ComplaintAttachment.organization_id == self.org, ComplaintAttachment.complaint_id == row.id))]
        return result

    def history(self, row):
        """The decision history with people named: the actor, and any owner a decision names (never an id)."""
        events = self.db.scalars(select(ComplaintEvent).where(ComplaintEvent.organization_id == self.org, ComplaintEvent.complaint_id == row.id)
                                 .order_by(ComplaintEvent.created_at, ComplaintEvent.id)).all()
        people = {e.actor_id for e in events}
        for e in events:
            people |= {UUID(str(v)) for k, v in (e.details or {}).items() if k.endswith('owner_user_id') and v}
        names = {str(k): v for k, v in user_names(self.db, self.org, [p for p in people if p]).items()}
        out = []
        for e in events:
            details = dict(e.details or {})
            for key in ('owner_user_id', 'previous_owner_user_id'):
                if details.get(key):
                    details[key.replace('_user_id', '_name')] = names.get(str(details.pop(key)), '')
                else:
                    details.pop(key, None)
            out.append(dict(id=e.id, action=e.action, notes=e.notes, details=details, actor_name=names.get(str(e.actor_id)), created_at=e.created_at))
        return out
