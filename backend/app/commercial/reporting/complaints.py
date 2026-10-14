"""Branded complaint register and investigation record through the existing reporting engine.

Every value is worded in the report's language (complaint_wording), people are named, and times are the organization's.
"""
from datetime import date, timezone
from uuid import UUID
from pydantic import Field, model_validator
from sqlalchemy import select
from app.core.reporting.contracts import CommonParams, ReportDefinition, ReportData, TableSection, SectionDefinition, ReportLimitError
from app.core.reporting.registry import registry
from app.commercial.application.complaint_service import ComplaintService
from app.commercial.domain.complaint_wording import action_title, describe, word
from app.commercial.infrastructure.complaint_models import Complaint
from app.commercial.infrastructure.complaint_queries import organization_zone
from app.commercial.infrastructure.models import Customer


class Params(CommonParams):
    complaint_id: UUID | None = Field(None, json_schema_extra={'lookup': 'complaints', 'title_ar': 'الشكوى', 'title_en': 'Complaint'})
    customer_id: UUID | None = Field(None, json_schema_extra={'lookup': 'complaint_customers', 'title_ar': 'العميل', 'title_en': 'Customer'})
    date_from: date | None = None
    date_to: date | None = None

    @model_validator(mode='after')
    def dates(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError('INVALID_DATE_RANGE')
        return self


def _day(value):
    return value.strftime('%d/%m/%Y') if value else '—'


def _qty(value):
    return '—' if value is None else f'{value.normalize():f}'


def build(db, tenant, params, selected):
    service = ComplaintService(db, tenant)
    q = service.filtered(customer_id=params.customer_id)
    if params.complaint_id:
        service.get(params.complaint_id)
        q = q.where(Complaint.id == params.complaint_id)
    if params.date_from:
        q = q.where(Complaint.received_date >= params.date_from)
    if params.date_to:
        q = q.where(Complaint.received_date <= params.date_to)
    rows = list(db.scalars(q.limit(2001)))
    if len(rows) > 2000:
        raise ReportLimitError()
    lang = params.lang
    ar = lang == 'ar'
    sections = []
    if 'register' in selected:
        names = dict(db.execute(select(Customer.id, Customer.name).where(Customer.organization_id == tenant.organization_id,
                                                                       Customer.id.in_({r.customer_id for r in rows}))).all()) if rows else {}
        sections.append(TableSection(key='register', title='سجل الشكاوى' if ar else 'Complaint register',
            columns=['الرقم', 'العميل', 'الموضوع', 'الحالة', 'موعد الحل'] if ar else ['Number', 'Customer', 'Subject', 'Status', 'Resolution due'],
            rows=[[r.number, names.get(r.customer_id, ''), r.title, word(r.status, lang), _day(r.due_date)] for r in rows]))
    if 'investigation' in selected and params.complaint_id and rows:
        r = rows[0]
        fields = [('بلاغ العميل' if ar else 'Customer statement', r.statement), ('نتيجة التحقق' if ar else 'Finding', word(r.finding, lang)),
                  (word('investigation', lang), r.investigation), (word('containment', lang), r.containment), (word('resolution', lang), r.resolution),
                  (word('implementation_evidence', lang), r.implementation_evidence), (word('customer_response', lang), r.customer_response)]
        sections.append(TableSection(key='investigation', title='التحقيق والمعالجة' if ar else 'Investigation and resolution', layout='fields',
                                     columns=[], rows=[[k, v or '—'] for k, v in fields]))
        for item in r.items:
            source = word(item.source_kind, lang) + (f' {item.source_label}' if item.source_label else '')
            quantities = (f'المسلّم {_qty(item.delivered_quantity)}، المبلّغ عنه {_qty(item.reported_quantity)}، المثبت تأثره {_qty(item.confirmed_quantity)} {item.unit}'
                          f' — مصدر المواصفة: {source}' if ar else
                          f'Delivered {_qty(item.delivered_quantity)}, reported {_qty(item.reported_quantity)}, confirmed affected '
                          f'{_qty(item.confirmed_quantity)} {item.unit} — specification from: {source}')
            sections.append(TableSection(key=f'item_{item.line_no}', title=item.product_name, note=quantities,
                columns=['الخاصية', 'المتفق عليه', 'بلاغ العميل', 'القياس الفعلي'] if ar else ['Property', 'Agreed', 'Reported', 'Measured'],
                rows=[[(p.name_ar if ar else p.name_en) + (f' ({p.unit})' if p.unit else ''), p.expected or '—', p.reported or '—', p.measured or '—']
                      for p in item.properties]))
        zone = organization_zone(db, tenant.organization_id)
        sections.append(TableSection(key='history', title='سجل المتابعة والقرارات' if ar else 'Follow-up and decisions',
            columns=['التاريخ', 'الإجراء', 'بواسطة', 'التفاصيل'] if ar else ['Date', 'Action', 'By', 'Details'],
            rows=[[_when(e['created_at'], zone), action_title(e['action'], lang), e['actor_name'] or '',
                   describe(e['action'], e['details'], e['notes'], lang) or '—'] for e in service.history(r)]))
    return ReportData(sections=sections, subject=rows[0].number if params.complaint_id and rows else '',
                      provisional=bool(params.complaint_id and rows and rows[0].status != 'closed'))


def _when(moment, zone):
    """A stored moment (UTC, naive on SQLite) at the organization's clock."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(zone).strftime('%d/%m/%Y %H:%M')


def register():
    if registry.get('customers.complaints'):
        return
    registry.register(ReportDefinition(key='customers.complaints', module='customers', title_ar='سجل شكاوى العملاء', title_en='Customer complaints',
        params_schema=Params, sections=(SectionDefinition('register', 'سجل الشكاوى', 'Complaint register'),
                                        SectionDefinition('investigation', 'التحقيق والمعالجة', 'Investigation',
                                                          available=lambda db, t, p: bool(p and getattr(p, 'complaint_id', None)))),
        permission='commercial:complaints:report', required_permissions=('commercial:complaints:read',), builder=build,
        body_template='customers_body.html', classification='internal', context_fields=('complaint_id',)))
