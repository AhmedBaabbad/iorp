"""Units of measure offered on quotations: code -> (Arabic, English). Pure domain data.

Codes are stored on quote items; documents print the label in the document's language.
Older items may hold free text from before this list; they are kept and printed as written.
"""

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


def unit_label(code: str, lang: str) -> str:
    """The unit's name in `lang`; a code outside the list (older free text) is returned as written."""
    names = UNITS.get(code)
    return names[0 if lang == "ar" else 1] if names else code
