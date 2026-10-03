"""Registers the quotation document with the reporting core (QUOTE-DOC-001)."""
from pathlib import Path
from typing import Literal
from uuid import UUID

from app.core.reporting.contracts import CommonParams, ReportDefinition, SectionDefinition
from app.core.reporting.registry import registry
from app.core.reporting.service import template_roots
from .builder import build

KEY = "customers.quotation"
QUOTES_READ = "commercial:quotes:read"


class QuotationParams(CommonParams):
    quote_id: UUID
    audience: Literal["customer"] = "customer"  # a quotation is always written for the customer


def register_quotation():
    if registry.get(KEY):
        return
    template_roots.append(Path(__file__).parent / "templates")
    registry.register(ReportDefinition(
        KEY, "customers", "عرض سعر", "Quotation", QuotationParams,
        (SectionDefinition("document", "عرض السعر", "Quotation"),), QUOTES_READ,
        lambda db, tenant, params, selected: build(db, tenant, params, selected), "quote_body.html",
        audiences=("customer",), required_permissions=("commercial:customers:read",),
        # The corporate header and footer are the core's shared external variant (DOC-IDENTITY-001).
        layout_templates=("quote_document.html", "header.html", "footer.html"),
        listed=False, classification="external",
    ))
