"""Modules contribute evidence that makes an order line's allocations immutable."""
_providers = []


def register_order_line_evidence(provider):
    if provider not in _providers:
        _providers.append(provider)


def order_line_evidence(db, org, line_id):
    return sorted({name for provider in _providers for name in provider(db, org, line_id)})
