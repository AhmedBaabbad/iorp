"""Composition seams for reporting.

The reporting core never imports a business module (foundation included). The composition
root (app/main.py) sets the organization identity provider at startup; tests may replace it.
"""
from collections.abc import Callable

# (db, organization_id) -> the branding dict the header and footer templates read.
branding_provider: Callable | None = None


def branding(db, organization_id):
    if branding_provider is None:
        raise RuntimeError('No branding provider is configured for reporting')
    return branding_provider(db, organization_id)
