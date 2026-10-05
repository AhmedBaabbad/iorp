"""Units of measure shared by every module (quotations, shipments, ...): code -> (Arabic, English). Pure reference data.

Codes are stored on lines; documents print the label in the document's language. A line written before this list
existed may hold free text; it is kept and printed as written. Weights also convert to kilograms for totals.
The frontend mirrors this list in src/lib/units.ts (tests/quote-units.test.mjs keeps both identical).
"""
from decimal import Decimal

UNITS: dict[str, tuple[str, str]] = {
    # Count
    "piece": ("قطعة", "Piece"),
    "unit": ("وحدة", "Unit"),
    "pair": ("زوج", "Pair"),
    "set": ("طقم", "Set"),
    "dozen": ("دستة", "Dozen"),
    "lot": ("دفعة", "Lot"),
    # Packaging
    "roll": ("رول", "Roll"),
    "reel": ("بكرة", "Reel"),
    "coil": ("لفّة", "Coil"),
    "bundle": ("حزمة", "Bundle"),
    "pack": ("عبوة", "Pack"),
    "box": ("صندوق", "Box"),
    "carton": ("كرتون", "Carton"),
    "bag": ("كيس", "Bag"),
    "sack": ("شوال", "Sack"),
    "pallet": ("طبلية", "Pallet"),
    "drum": ("برميل", "Drum"),
    "can": ("علبة", "Can"),
    "bottle": ("قارورة", "Bottle"),
    "sheet": ("لوح", "Sheet"),
    "container": ("حاوية", "Container"),
    # Weight
    "g": ("جرام", "Gram"),
    "kg": ("كيلوجرام", "Kilogram"),
    "ton": ("طن", "Ton"),
    "lb": ("رطل (باوند)", "Pound"),
    "oz": ("أونصة", "Ounce"),
    # Length
    "mm": ("مليمتر", "Millimetre"),
    "cm": ("سنتيمتر", "Centimetre"),
    "m": ("متر", "Metre"),
    "linear_m": ("متر طولي", "Linear metre"),
    "km": ("كيلومتر", "Kilometre"),
    # Area and volume
    "sqm": ("متر مربع", "Square metre"),
    "cbm": ("متر مكعب", "Cubic metre"),
    "ml": ("مليلتر", "Millilitre"),
    "l": ("لتر", "Litre"),
    # Time (services)
    "hour": ("ساعة", "Hour"),
    "day": ("يوم", "Day"),
}

# Weight units and their value in kilograms (metric ton; avoirdupois pound and ounce).
KILOGRAMS: dict[str, Decimal] = {"g": Decimal("0.001"), "kg": Decimal("1"), "ton": Decimal("1000"),
                                 "lb": Decimal("0.45359237"), "oz": Decimal("0.028349523125")}
WEIGHT_UNITS: tuple[str, ...] = tuple(KILOGRAMS)


def unit_label(code: str, lang: str) -> str:
    """The unit's name in `lang`; a code outside the list (older free text) is returned as written."""
    names = UNITS.get(code)
    return names[0 if lang == "ar" else 1] if names else code


def to_kilograms(value: Decimal | None, unit: str) -> Decimal | None:
    return None if value is None else value * KILOGRAMS[unit]


def spec_text(spec, separator: str = " × ") -> str:
    """A line's specification as printed: its values in order ("5 × 0.35 × Black"); empty when there is none."""
    if not isinstance(spec, dict):
        return ""
    return separator.join(str(v) for v in spec.values() if v not in (None, ""))
