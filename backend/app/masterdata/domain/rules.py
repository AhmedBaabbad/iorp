"""Master data (MD-001): the organization's products, their specification templates, and its general settings. Pure.

A product is what the organization makes or buys and names on its documents: quotations, commercial orders, samples,
production demands and orders, quality specifications and purchased materials. Every module stores the product's **key**
(`pp_strap`), so they match one another by it, never by how a name was typed. The key is fixed once the product exists;
names (Arabic and English) may be corrected, and a product is deactivated, never deleted, so documents keep resolving it.

A product's specification template lists its properties in order (width, thickness, colour…): a number with its unit, a
text, or a choice among options (each with an Arabic and an English label). Lines store `{property key: value}`; the
order of the template is the order a document prints.

General settings: the VAT rate (15 % in the Kingdom) and the default currency of new quotations and purchase orders.
"""
import re
from decimal import Decimal


class MasterDataError(ValueError):
    def __init__(self, code: str, status: int = 409, **detail):
        super().__init__(code)
        self.code, self.status, self.detail = code, status, detail


KEY = re.compile(r"^[a-z][a-z0-9_]{1,59}$")
KINDS = ("finished", "material")  # a finished product, or a material it is made from (resin, masterbatch, cores…)
PROPERTY_KINDS = ("number", "text", "choice")
CURRENCIES = ("SAR", "USD")
DEFAULT_VAT_RATE = Decimal("15")
DEFAULT_CURRENCY = "SAR"
MAX_PROPERTIES, MAX_OPTIONS = 30, 60


def key_from(text: str) -> str:
    """A key suggested from an English name: «PP Strap 19 mm» → pp_strap_19_mm. Empty when nothing usable remains."""
    key = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")[:60]
    return key if KEY.match(key) else ""


def assert_key(key: str, code="PRODUCT_KEY_INVALID") -> None:
    if not KEY.match(key or ""):
        raise MasterDataError(code, 400, key=key)


def assert_template(properties) -> None:
    """Keys unique and well-formed; a choice has options with unique values and both labels; a number may carry a unit."""
    if len(properties) > MAX_PROPERTIES:
        raise MasterDataError("TOO_MANY_PROPERTIES", 400, limit=MAX_PROPERTIES)
    seen = set()
    for number, prop in enumerate(properties, 1):
        assert_key(prop.key, "PROPERTY_KEY_INVALID")
        if prop.key in seen:
            raise MasterDataError("PROPERTY_KEY_DUPLICATE", 400, key=prop.key)
        seen.add(prop.key)
        if prop.kind not in PROPERTY_KINDS:
            raise MasterDataError("PROPERTY_KIND_UNKNOWN", 400, line=number)
        options = prop.options or []
        if prop.kind == "choice":
            if not options:
                raise MasterDataError("OPTIONS_REQUIRED", 400, key=prop.key)
            if len(options) > MAX_OPTIONS or len({o.value for o in options}) != len(options):
                raise MasterDataError("OPTIONS_INVALID", 400, key=prop.key)
        elif options:
            raise MasterDataError("OPTIONS_ONLY_FOR_CHOICE", 400, key=prop.key)
        if prop.unit and prop.kind != "number":
            raise MasterDataError("UNIT_ONLY_FOR_NUMBER", 400, key=prop.key)


def assert_settings(vat_rate, currency) -> None:
    if vat_rate is not None and not (Decimal(0) <= Decimal(vat_rate) <= Decimal(100)):
        raise MasterDataError("VAT_RATE_INVALID", 400)
    if currency is not None and currency not in CURRENCIES:
        raise MasterDataError("CURRENCY_UNKNOWN", 400)


def product_actions(can) -> list[str]:
    return [a for a in ("edit",) if can(a)]


def assert_property_values(properties, values, preserved=None):
    """Validate values against the owning product template, never a Commercial-specific schema.

    Retired/legacy keys already on this sample may remain unchanged, but cannot be added or edited.
    Known fields are validated against the current template whenever specifications are edited.
    """
    from app.core.interfaces.product_catalog import ProductSpecificationError
    from json import dumps
    known={p.key:p for p in properties}
    for key,value in values.items():
        if key not in known and not (preserved is not None and key in preserved and dumps(value, sort_keys=True)==dumps(preserved[key], sort_keys=True)):
            raise ProductSpecificationError('SAMPLE_PROPERTY_UNKNOWN',key)
    for prop in properties:
        value=values.get(prop.key)
        if value is None or (isinstance(value,str) and not value.strip()):
            if prop.required:
                raise ProductSpecificationError('SAMPLE_PROPERTY_REQUIRED',prop.key)
            continue
        if prop.kind=='number':
            if isinstance(value,bool) or not isinstance(value,(int,float,Decimal)) or not Decimal(str(value)).is_finite():
                raise ProductSpecificationError('SAMPLE_PROPERTY_NUMBER',prop.key)
        elif prop.kind=='text':
            if not isinstance(value,str):
                raise ProductSpecificationError('SAMPLE_PROPERTY_TEXT',prop.key)
        elif prop.kind=='choice':
            if not isinstance(value,str) or value not in {o[0] for o in prop.options}:
                raise ProductSpecificationError('SAMPLE_PROPERTY_CHOICE',prop.key)
        else:
            raise ProductSpecificationError('SAMPLE_PROPERTY_KIND',prop.key)
