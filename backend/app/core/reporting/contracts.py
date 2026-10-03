from dataclasses import dataclass
from typing import Any, Callable, Literal
from pydantic import BaseModel, Field, ConfigDict


class ReportLimitError(Exception):
    """A report read would exceed its row limit. Raised by read APIs (no HTTP there); the reporting service answers 422."""
    code = 'REPORT_ROW_LIMIT_NARROW_FILTERS'


class CommonParams(BaseModel):
    model_config = ConfigDict(extra='forbid')
    lang: Literal['ar', 'en'] = 'ar'
    orientation: Literal['portrait', 'landscape'] = 'portrait'
    sections: list[str] | None = Field(None, max_length=30)


class TableSection(BaseModel):
    key: str
    title: str
    columns: list[str] = []
    rows: list[list[str]] = []
    note: str | None = None
    bars: list[tuple[str, float]] = []
    cards: list[tuple[str, str]] = []
    # 'fields': rows are (label, value) pairs shown as a two-column information panel instead of a table.
    layout: Literal['table', 'fields'] = 'table'


class ReportData(BaseModel):
    sections: list[TableSection]
    provisional: bool = False
    subject: str = ''
    applied_filters: str = ''
    # Who an external-audience report is for (shown as "Prepared for"); empty for internal reports.
    prepared_for: str = ''
    # Structured content for a document layout (e.g. a quotation) that is not a list of sections.
    document: dict[str, Any] = {}


@dataclass(frozen=True)
class SectionDefinition:
    key: str
    title_ar: str
    title_en: str
    default_enabled: bool = True
    requires_permission: str | None = None
    available: Callable | None = None
    internal_only: bool = False
    permissions: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReportDefinition:
    key: str
    module: str
    title_ar: str
    title_en: str
    params_schema: type[CommonParams]
    sections: tuple[SectionDefinition, ...]
    permission: str
    builder: Callable
    body_template: str
    default_orientation: str = 'portrait'
    available: Callable | None = None
    audiences: tuple[str, ...] = ()
    internal_permission: str | None = None
    required_permissions: tuple[str, ...] = ()
    watermark: Callable | None = None
    context_fields: tuple[str, ...] = ()
    filename_prefix: str | None = None
    parameter_permissions: Callable | None = None
    # A document (quotation, ...) rather than an analytical report: its own page, header and footer
    # templates, opened from its record instead of the report center, and margins sized to its footer.
    layout_templates: tuple[str, str, str] = ('base.html', 'header.html', 'footer.html')
    listed: bool = True
    page_margins: Callable | None = None  # (data) -> (top_inches, bottom_inches); default follows the classification
    # Corporate document identity (DOC-IDENTITY-001): 'internal' (operational header/footer, no legal or contact
    # data) or 'external' (customer-facing, with the company's legal identity, contacts and bank accounts).
    # None: the audience decides (audience 'customer' -> external, otherwise internal).
    classification: Literal['internal', 'external'] | None = None
    department: tuple[str, str] | None = None  # (Arabic, English) shown in an internal report's details
