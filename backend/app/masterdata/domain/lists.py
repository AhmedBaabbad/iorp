"""Reference lists (MD-002): the organization's sectors, opportunity sources, countries and cities. Pure.

Customers, suppliers and shipments name them; each stores the item's **key** in its own column (as with products), so
the same sector is never written two ways and documents print the name in their language. A city belongs to a country.
An item is deactivated, never deleted, and its key never changes.

«Add the usual values» offers a starting list for each — common sectors, opportunity sources, the region's countries and
the Kingdom's main cities — which the organization then edits.
"""
from .rules import KEY, MasterDataError

SECTOR, SOURCE, COUNTRY, CITY = "sector", "opportunity_source", "country", "city"
LISTS = (SECTOR, SOURCE, COUNTRY, CITY)
PARENT = {CITY: COUNTRY}  # a list whose items belong to an item of another list
MAX_ITEMS = 500

# (key, Arabic, English[, parent key])
STANDARD: dict[str, tuple[tuple[str, ...], ...]] = {
    SECTOR: (
        ("packaging", "التعبئة والتغليف", "Packaging"), ("food_beverage", "الأغذية والمشروبات", "Food and beverages"),
        ("construction", "البناء والمقاولات", "Construction"), ("electrical_cables", "الكهرباء والكابلات", "Electrical and cables"),
        ("paper_cartons", "الورق والكرتون", "Paper and cartons"), ("plastics_chemicals", "البلاستيك والكيماويات", "Plastics and chemicals"),
        ("logistics", "النقل والخدمات اللوجستية", "Logistics"), ("agriculture", "الزراعة", "Agriculture"),
        ("wholesale_retail", "الجملة والتجزئة", "Wholesale and retail"), ("manufacturing", "الصناعات التحويلية", "Manufacturing"),
        ("government", "القطاع الحكومي", "Government"), ("other", "أخرى", "Other"),
    ),
    SOURCE: (
        ("website", "الموقع الإلكتروني", "Website"), ("exhibition", "معرض", "Exhibition"), ("referral", "توصية", "Referral"),
        ("cold_call", "اتصال مباشر", "Cold call"), ("existing_customer", "عميل حالي", "Existing customer"),
        ("social_media", "وسائل التواصل الاجتماعي", "Social media"), ("tender", "مناقصة", "Tender"), ("walk_in", "زيارة مباشرة", "Walk-in"),
        ("other", "أخرى", "Other"),
    ),
    COUNTRY: (
        ("sa", "المملكة العربية السعودية", "Saudi Arabia"), ("ae", "الإمارات العربية المتحدة", "United Arab Emirates"), ("kw", "الكويت", "Kuwait"),
        ("qa", "قطر", "Qatar"), ("bh", "البحرين", "Bahrain"), ("om", "عُمان", "Oman"), ("eg", "مصر", "Egypt"), ("jo", "الأردن", "Jordan"),
        ("iq", "العراق", "Iraq"), ("ye", "اليمن", "Yemen"), ("sd", "السودان", "Sudan"), ("cn", "الصين", "China"), ("in", "الهند", "India"),
        ("tr", "تركيا", "Turkey"),
    ),
    CITY: tuple((key, ar, en, "sa") for key, ar, en in (
        ("riyadh", "الرياض", "Riyadh"), ("jeddah", "جدة", "Jeddah"), ("makkah", "مكة المكرمة", "Makkah"), ("madinah", "المدينة المنورة", "Madinah"),
        ("dammam", "الدمام", "Dammam"), ("khobar", "الخبر", "Al Khobar"), ("dhahran", "الظهران", "Dhahran"), ("jubail", "الجبيل", "Jubail"),
        ("al_kharj", "الخرج", "Al Kharj"), ("al_ahsa", "الأحساء", "Al Ahsa"), ("qatif", "القطيف", "Qatif"), ("taif", "الطائف", "Taif"),
        ("tabuk", "تبوك", "Tabuk"), ("buraidah", "بريدة", "Buraidah"), ("unaizah", "عنيزة", "Unaizah"), ("abha", "أبها", "Abha"),
        ("khamis_mushait", "خميس مشيط", "Khamis Mushait"), ("hail", "حائل", "Hail"), ("jazan", "جازان", "Jazan"), ("najran", "نجران", "Najran"),
        ("yanbu", "ينبع", "Yanbu"), ("al_baha", "الباحة", "Al Baha"), ("sakaka", "سكاكا", "Sakaka"), ("arar", "عرعر", "Arar"),
    )),
}


def assert_list(name: str) -> None:
    if name not in LISTS:
        raise MasterDataError("LIST_UNKNOWN", 404, list=name)


def assert_item(list_name: str, key: str, parent: str | None, parents: set[str]) -> None:
    """A well-formed key; a city names one of the organization's countries; other lists have no parent."""
    if not KEY.match(key or ""):
        raise MasterDataError("ITEM_KEY_INVALID", 400, key=key)
    if list_name in PARENT:
        if not parent or parent not in parents:
            raise MasterDataError("PARENT_REQUIRED", 400, list=PARENT[list_name])
    elif parent:
        raise MasterDataError("PARENT_NOT_ALLOWED", 400)
