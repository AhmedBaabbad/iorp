from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from time import monotonic
from zoneinfo import ZoneInfo
import logging
import re

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError
from app.core.db import Base
from app.core.reporting import providers
from app.core.reporting.contracts import ReportLimitError
from app.core.reporting.registry import registry
from app.core.reporting.layout import render_layout
from app.core.reporting.renderers import GotenbergRenderer, RenderError


logger = logging.getLogger(__name__)

# Composition root supplies template search paths; the core never imports a module.
template_roots: list[Path] = []
# Longest a report's data queries may run (PostgreSQL); beyond it the user is asked to narrow filters.
BUILD_TIMEOUT_MS = 30_000


def _available(check, db, tenant, params):
    """A data-availability check never fails the listing: too much data still means data (the report itself says narrow filters)."""
    try:
        return not check or check(db, tenant, params)
    except ReportLimitError:
        return True


def classification_for(definition, audience) -> str:
    """Which corporate header/footer a document carries: fixed by its definition, otherwise by its audience."""
    return definition.classification or ('external' if audience == 'customer' else 'internal')


def default_margins(classification, branding) -> tuple[float, float]:
    """Room for the repeated header and footer, so content never overlaps them (inches: top, bottom).

    The external header adds up to three legal lines (CR, Unified No., VAT) under the names; the external footer
    is the contact line, one line per active bank account and the closing strip.
    """
    if classification == 'external':
        legal = sum(1 for key in ('commercial_registration_no', 'unified_number', 'vat_number') if branding.get(key))
        banks = sum(1 for account in branding.get('bank_accounts') or [] if account.get('is_active'))
        return 1.1 + 0.15 * legal, 0.75 + 0.2 * banks
    return 1.1, 0.7


def visible_sections(definition, db, tenant, can, params=None):
    return [s for s in definition.sections if (not s.requires_permission or can(s.requires_permission))
            and all(can(p) for p in s.permissions)
            and not (s.internal_only and getattr(params, 'audience', 'internal') == 'customer')
            and _available(s.available, db, tenant, params)]


def definitions(db, tenant, can, module=None, params=None):
    values = []
    for d in registry.definitions.values():
        audiences = [a for a in d.audiences if a != 'internal' or not d.internal_permission or can(d.internal_permission)]
        if not d.listed or (module and module != d.module) or not can(d.permission) or not all(can(p) for p in d.required_permissions) or (d.audiences and not audiences) or not _available(d.available, db, tenant, params):
            continue
        effective_params = params
        if d.audiences and getattr(params, 'audience', 'internal') not in audiences:
            effective_params = SimpleNamespace(**{**vars(params or SimpleNamespace()), 'audience': audiences[0]})
        values.append(dict(key=d.key, module=d.module, title_ar=d.title_ar, title_en=d.title_en,
                           audiences=audiences, context_fields=d.context_fields,
                           params_schema=d.params_schema.model_json_schema(), default_orientation=d.default_orientation,
                           orientations=['portrait', 'landscape'], sections=[dict(key=s.key, title_ar=s.title_ar, title_en=s.title_en,
                               default_enabled=s.default_enabled, requires_permission=s.requires_permission)
                               for s in visible_sections(d, db, tenant, can, effective_params)]))
    return values


class ReportingService:
    def __init__(self, db, tenant, can, actor_name, renderer=None):
        self.db, self.tenant, self.can, self.actor_name = db, tenant, can, actor_name
        self.renderer = renderer or GotenbergRenderer()

    def _now(self):
        """Now, in the organization's time zone (shared-table read, no foundation model import)."""
        organizations = Base.metadata.tables['foundation_organizations']
        zone = self.db.scalar(select(organizations.c.timezone).where(organizations.c.id == self.tenant.organization_id))
        return datetime.now(ZoneInfo(zone or 'UTC'))

    def generate(self, key, payload, fmt):
        """Builds the report from current data and returns it; nothing is stored. Failures go to the server log."""
        start, now = monotonic(), self._now()
        try:
            definition = registry.get(key)
            if not definition:
                raise HTTPException(404, 'REPORT_NOT_FOUND')
            if not self.can(definition.permission) or not all(self.can(p) for p in definition.required_permissions):
                raise HTTPException(403, 'REPORT_PERMISSION_DENIED')
            try:
                params = definition.params_schema.model_validate(payload)
            except ValidationError as exc:
                raise HTTPException(422, 'INVALID_REPORT_PARAMS') from exc
            audience = getattr(params, 'audience', 'internal')
            if definition.parameter_permissions and not all(self.can(p) for p in definition.parameter_permissions(params)):
                raise HTTPException(403, 'SECTION_PERMISSION_DENIED')
            if definition.audiences:
                if audience not in definition.audiences:
                    raise HTTPException(422, 'INVALID_REPORT_AUDIENCE')
                if audience == 'internal' and definition.internal_permission and not self.can(definition.internal_permission):
                    raise HTTPException(403, 'INTERNAL_AUDIENCE_DENIED')
            if not _available(definition.available, self.db, self.tenant, params):
                raise HTTPException(409, 'REPORT_DATA_UNAVAILABLE')
            candidates = visible_sections(definition, self.db, self.tenant, self.can, params)
            known = {s.key: s for s in definition.sections}
            requested = params.sections if params.sections is not None else [s.key for s in candidates if s.default_enabled]
            if len(set(requested)) != len(requested) or any(k not in known for k in requested):
                raise HTTPException(422, 'INVALID_REPORT_SECTIONS')
            for k in requested:
                if audience == 'customer' and known[k].internal_only:
                    continue
                if known[k].requires_permission and not self.can(known[k].requires_permission):
                    raise HTTPException(403, 'SECTION_PERMISSION_DENIED')
                if not all(self.can(p) for p in known[k].permissions):
                    raise HTTPException(403, 'SECTION_PERMISSION_DENIED')
            selected = {s.key for s in candidates} & set(requested)
            data = self._build(definition, params, selected)
            branding = providers.branding(self.db, self.tenant.organization_id)
            title = definition.title_ar if params.lang == 'ar' else definition.title_en
            classification = classification_for(definition, audience)
            department = definition.department[0 if params.lang == 'ar' else 1] if definition.department else ''
            context = dict(data=data, branding=branding, lang=params.lang, title=title, classification=classification, department=department,
                           audience=audience, watermark=definition.watermark(data, params.lang) if definition.watermark else '',
                           generated_at=now.strftime('%Y-%m-%d %H:%M %Z'), generated_by=self.actor_name,
                           filters=data.applied_filters, body_template=definition.body_template)
            html, header, footer = render_layout(context, template_roots, definition.layout_templates)
            if len(html.encode()) > 20_000_000:
                raise HTTPException(422, 'REPORT_TOO_LARGE_NARROW_FILTERS')
            self.db.rollback()  # release the read transaction before waiting for Chromium
            margins = definition.page_margins(data) if definition.page_margins else default_margins(classification, branding)
            content, _pages = (self.renderer.render(html, header, footer, params.orientation == 'landscape', margins=margins)
                               if fmt == 'pdf' else (html, None))
            # The download name is in the report's language: "تقرير أمر الإنتاج_PO-2026-000001_20261001-1434.pdf".
            safe = lambda value: re.sub(r'[^\w.-]+', '_', value).strip('_')[:80]  # noqa: E731
            parts = [safe(definition.filename_prefix or title), safe(data.subject) if data.subject else None, f'{now:%Y%m%d-%H%M}']
            return content, '_'.join(p for p in parts if p) + f'.{fmt}'
        except Exception as exc:
            self.db.rollback()
            limit = isinstance(exc, ReportLimitError)
            if limit:
                exc = HTTPException(422, exc.code)
            code = str(exc.detail) if isinstance(exc, HTTPException) and isinstance(exc.detail, str) else 'REPORT_GENERATION_FAILED'
            log = logger.exception if not isinstance(exc, HTTPException) else logger.info
            log('Report %s failed for organization %s: %s (%d ms)', key, self.tenant.organization_id, code, int((monotonic() - start) * 1000))
            if limit:
                raise exc from None
            if isinstance(exc, HTTPException):
                raise
            if isinstance(exc, RenderError):
                raise HTTPException(503, 'PDF_RENDER_FAILED_RETRY') from exc
            raise HTTPException(500, 'REPORT_GENERATION_FAILED') from exc

    def _build(self, definition, params, selected):
        """Run the read-only data builder under a statement timeout (PostgreSQL), so a huge report fails clearly."""
        if self.db.get_bind().dialect.name == 'postgresql':
            self.db.execute(text(f'SET LOCAL statement_timeout = {int(BUILD_TIMEOUT_MS)}'))
        try:
            return definition.builder(self.db, self.tenant, params, selected)
        except OperationalError as exc:
            if 'statement timeout' in str(exc).lower() or 'canceling statement' in str(exc).lower():
                raise HTTPException(504, 'REPORT_TIMEOUT_NARROW_FILTERS') from exc
            raise
