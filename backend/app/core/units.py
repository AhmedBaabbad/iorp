"""Units of measure shared by every module (quotations, shipments, ...). Pure reference data.

UNITS: code -> the full name (Arabic, English), shown where a unit is chosen. SYMBOLS: code -> the short form (Arabic,
English) printed after a number on every document and screen: 19 مم / 19 mm, 10 كجم / 10 kg (UNIT-SYM-001).
Codes are stored on lines; documents print the symbol in the document's language. A line written before this list
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
    "roll": ("لفة", "Roll"),
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

# What documents and screens print after a number (the short form); the full name stays in UNITS.
SYMBOLS: dict[str, tuple[str, str]] = {
    "piece": ("قطعة", "pcs"),
    "unit": ("وحدة", "unit"),
    "pair": ("زوج", "pair"),
    "set": ("طقم", "set"),
    "dozen": ("دستة", "doz"),
    "lot": ("دفعة", "lot"),
    "roll": ("لفة", "roll"),
    "reel": ("بكرة", "reel"),
    "coil": ("لفّة", "coil"),
    "bundle": ("حزمة", "bdl"),
    "pack": ("عبوة", "pack"),
    "box": ("صندوق", "box"),
    "carton": ("كرتون", "ctn"),
    "bag": ("كيس", "bag"),
    "sack": ("شوال", "sack"),
    "pallet": ("طبلية", "plt"),
    "drum": ("برميل", "drum"),
    "can": ("علبة", "can"),
    "bottle": ("قارورة", "btl"),
    "sheet": ("لوح", "sheet"),
    "container": ("حاوية", "cntr"),
    "g": ("جم", "g"),
    "kg": ("كجم", "kg"),
    "ton": ("طن", "t"),
    "lb": ("رطل", "lb"),
    "oz": ("أونصة", "oz"),
    "mm": ("مم", "mm"),
    "cm": ("سم", "cm"),
    "m": ("م", "m"),
    "linear_m": ("م.ط", "lm"),
    "km": ("كم", "km"),
    "sqm": ("م²", "m²"),
    "cbm": ("م³", "m³"),
    "ml": ("مل", "mL"),
    "l": ("لتر", "L"),
    "hour": ("ساعة", "h"),
    "day": ("يوم", "day"),
}

# Weight units and their value in kilograms (metric ton; avoirdupois pound and ounce).
KILOGRAMS: dict[str, Decimal] = {"g": Decimal("0.001"), "kg": Decimal("1"), "ton": Decimal("1000"),
                                 "lb": Decimal("0.45359237"), "oz": Decimal("0.028349523125")}
WEIGHT_UNITS: tuple[str, ...] = tuple(KILOGRAMS)


def unit_label(code: str, lang: str) -> str:
    """The unit as printed after a number in `lang` (its symbol: مم, mm, كجم, kg); older free text is returned as written."""
    symbols = SYMBOLS.get(code)
    return symbols[0 if lang == "ar" else 1] if symbols else code


def unit_name(code: str, lang: str) -> str:
    """The unit's full name in `lang` (مليمتر, Millimetre), for where it is chosen; older free text as written."""
    names = UNITS.get(code)
    return names[0 if lang == "ar" else 1] if names else code


def to_kilograms(value: Decimal | None, unit: str) -> Decimal | None:
    return None if value is None else value * KILOGRAMS[unit]


def spec_text(spec, separator: str = " × ") -> str:
    """A line's specification as printed: its values in order ("5 × 0.35 × Black"); empty when there is none.
    A row written without a value (a whole description typed as the property) prints its property text in its place."""
    if not isinstance(spec, dict):
        return ""
    parts = [str(value) if value not in (None, "") else str(key).strip() for key, value in spec.items()]
    return separator.join(part for part in parts if part)
