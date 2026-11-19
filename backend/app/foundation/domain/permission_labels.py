"""Permission display metadata derived from the shared translation source.

The existing registry tuple contract is preserved; labels are no longer copied here.
"""
from app.core.enum_i18n import enum_catalog

_ar = enum_catalog('ar')['foundation']
_en = enum_catalog('en')['foundation']
LABELS: dict[str, tuple[str, str, str, str]] = {
    code: (name, _en['permissionName'][code], _ar['permissionDescription'][code], _en['permissionDescription'][code])
    for code, name in _ar['permissionName'].items()
}
