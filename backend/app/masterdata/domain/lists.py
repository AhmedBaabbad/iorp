"""Reference lists (MD-002): the organization's sectors, opportunity sources, countries and cities. Pure.

Customers, suppliers and shipments name them; each stores the item's **key** in its own column (as with products), so
the same sector is never written two ways and documents print the name in their language. A city belongs to a country.
An item is deactivated, never deleted, and its key never changes.

«Add the usual values» offers a starting list for each — common sectors, opportunity sources, the region's countries and
the Kingdom's main cities — which the organization then edits.
"""
from .rules import KEY, MasterDataError

SECTOR, SOURCE, COUNTRY, CITY = "sector", "opportunity_source", "country", "city"
# Operational lists: the record keeps the item's English name as a snapshot (core reference_lists.assert_reference_text).
DOWNTIME_REASON, WASTE_REASON, WORKFORCE_SKILL, TEST_METHOD = "downtime_reason", "waste_reason", "workforce_skill", "test_method"
# Classifications a department names (MD-003): the record keeps the item's key, as for sectors.
SUPPLIER_CATEGORY, MATERIAL_CATEGORY, DEFECT_CATEGORY, REJECTION_REASON = "supplier_category", "material_category", "defect_category", "rejection_reason"
COMPLAINT_CATEGORY, INTERACTION_TYPE, VEHICLE_TYPE = "complaint_category", "interaction_type", "vehicle_type"
LISTS = (SECTOR, SOURCE, COUNTRY, CITY, DOWNTIME_REASON, WASTE_REASON, WORKFORCE_SKILL, TEST_METHOD, SUPPLIER_CATEGORY, MATERIAL_CATEGORY,
         DEFECT_CATEGORY, REJECTION_REASON, COMPLAINT_CATEGORY, INTERACTION_TYPE, VEHICLE_TYPE)
TEXT_LISTS = (DOWNTIME_REASON, WASTE_REASON, WORKFORCE_SKILL, TEST_METHOD)  # stored as the English name, not the key
# Items the system itself writes (an automatic rejection's reason): never deleted, whatever their use.
PROTECTED: dict[str, frozenset[str]] = {
    REJECTION_REASON: frozenset({"failed_quality_check", "out_of_spec", "other"}),
    COMPLAINT_CATEGORY: frozenset({"quality"}),  # a quality complaint is referred to quality (commercial complaint rules)
}
PARENT = {CITY: COUNTRY}  # a list whose items belong to an item of another list
MAX_ITEMS = 500

# (key, Arabic, English[, parent key])
STANDARD: dict[str, tuple[tuple[str, ...], ...]] = {
    DOWNTIME_REASON: (
        ("power_outage", "انقطاع الكهرباء", "Power outage"), ("mechanical_breakdown", "عطل ميكانيكي", "Mechanical breakdown"),
        ("electrical_fault", "عطل كهربائي", "Electrical fault"), ("die_change", "تغيير القالب / المقاس", "Die or size change"),
        ("material_shortage", "نقص المواد الخام", "Material shortage"), ("planned_maintenance", "صيانة مخططة", "Planned maintenance"),
        ("cleaning", "تنظيف", "Cleaning"), ("quality_hold", "إيقاف للجودة", "Quality hold"), ("operator_shortage", "نقص المشغلين", "Operator shortage"),
        ("startup_adjustment", "ضبط عند التشغيل", "Start-up adjustment"), ("other", "أخرى", "Other"),
    ),
    WASTE_REASON: (
        ("startup_scrap", "هالك بداية التشغيل", "Start-up scrap"), ("edge_trim", "قص الحواف", "Edge trim"), ("film_break", "انقطاع الفيلم", "Film break"),
        ("gauge_variation", "تفاوت السماكة", "Gauge variation"), ("contamination", "تلوث / شوائب", "Contamination"),
        ("winding_defect", "عيب اللف", "Winding defect"), ("color_change", "تغيير اللون", "Color change"), ("roll_end", "نهاية الرول", "Roll end"),
        ("handling_damage", "تلف أثناء المناولة", "Handling damage"), ("other", "أخرى", "Other"),
    ),
    WORKFORCE_SKILL: (
        ("extruder_operator", "مشغل خط بثق", "Extruder operator"), ("rewinder_operator", "مشغل خط لف", "Rewinder operator"),
        ("packer", "عامل تعبئة", "Packer"), ("quality_inspector", "مفتش جودة", "Quality inspector"), ("maintenance_technician", "فني صيانة", "Maintenance technician"),
        ("electrician", "كهربائي", "Electrician"), ("forklift_driver", "سائق رافعة شوكية", "Forklift driver"), ("storekeeper", "أمين مستودع", "Storekeeper"),
        ("supervisor", "مشرف وردية", "Shift supervisor"),
    ),
    TEST_METHOD: (
        ("micrometer", "ميكرومتر", "Micrometer"), ("caliper", "قدمة ورنية", "Caliper"), ("measuring_tape", "شريط قياس", "Measuring tape"),
        ("weighing", "وزن بالميزان", "Weighing"), ("tensile_test", "اختبار الشد", "Tensile test"), ("elongation_test", "اختبار الاستطالة", "Elongation test"),
        ("visual_inspection", "فحص بصري", "Visual inspection"), ("color_comparison", "مقارنة اللون", "Color comparison"),
        ("puncture_test", "اختبار الثقب", "Puncture test"), ("cling_test", "اختبار الالتصاق", "Cling test"),
    ),
    SUPPLIER_CATEGORY: (
        ("raw_material", "مواد خام", "Raw materials"), ("packaging", "مواد تغليف", "Packaging"), ("consumables", "مستهلكات", "Consumables"),
        ("services", "خدمات", "Services"), ("other", "أخرى", "Other"),
    ),
    MATERIAL_CATEGORY: (
        ("resin", "حبيبات (ريزن)", "Resin"), ("masterbatch", "ماستر باتش", "Masterbatch"), ("additive", "إضافات", "Additive"), ("core", "كور", "Core"),
        ("carton", "كراتين", "Carton"), ("film", "استريتش / أفلام", "Film"), ("accessory", "ملحقات", "Accessory"), ("other", "أخرى", "Other"),
    ),
    DEFECT_CATEGORY: (
        ("dimension", "أبعاد", "Dimension"), ("thickness", "السماكة / القياس", "Thickness / Gauge"), ("surface", "عيب سطحي", "Surface Defect"),
        ("color", "انحراف اللون", "Color Deviation"), ("strength", "إخفاق في المتانة", "Strength Failure"), ("winding", "عيب اللف", "Winding Defect"),
        ("weight", "وزن خارج المعيار", "Weight Out of Tolerance"), ("packaging", "عيب التعبئة", "Packaging Defect"),
        ("labeling", "خطأ في التسمية", "Labeling Error"), ("finish", "نعومة / الملمس", "Finish / Texture"), ("other", "أخرى", "Other"),
    ),
    REJECTION_REASON: (
        ("failed_quality_check", "فشل فحص الجودة", "Failed Quality Check"), ("critical_defect", "عيب حرج", "Critical Defect"),
        ("out_of_spec", "خارج المواصفات", "Out of Specification"), ("dimension_failure", "فشل الأبعاد", "Dimension Failure"),
        ("surface_failure", "فشل السطح", "Surface Failure"), ("packaging_failure", "فشل التعبئة", "Packaging Failure"),
        ("labeling_issue", "مشكلة في التسمية", "Labeling Issue"), ("other", "أخرى", "Other"),
    ),
    COMPLAINT_CATEGORY: (
        ("quality", "الجودة", "Quality"), ("delivery", "التسليم", "Delivery"), ("quantity", "الكمية", "Quantity"), ("packaging", "التغليف", "Packaging"),
        ("commercial", "الشروط التجارية", "Commercial terms"), ("service", "الخدمة", "Service"), ("other", "أخرى", "Other"),
    ),
    INTERACTION_TYPE: (
        ("call", "مكالمة هاتفية", "Phone Call"), ("visit", "زيارة ميدانية", "Site Visit"), ("whatsapp", "واتساب", "WhatsApp"),
        ("email", "بريد إلكتروني", "Email"), ("meeting", "اجتماع", "Meeting"),
    ),
    VEHICLE_TYPE: (
        ("pickup", "بيك أب (ونيت)", "Pickup"), ("dyna", "دينا", "Dyna (light truck)"), ("lorry", "لوري", "Lorry"),
        ("trailer", "تريلا", "Trailer"), ("refrigerated", "شاحنة مبردة", "Refrigerated truck"), ("van", "فان", "Van"),
    ),
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
