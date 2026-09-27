"""Organization-scoped system role catalog."""

from app.foundation.domain.permission_catalog import ALL_PERMISSION_CODES

SYSTEM_ROLES: tuple[dict[str, object], ...] = (
    {"code": "organization_admin", "name_en": "Organization Administrator", "name_ar": "مدير المنظمة", "description_en": "Full organization administration access", "description_ar": "صلاحيات إدارة المنظمة الكاملة", "is_protected": True, "permissions": ("ALL",)},
    {"code": "factory_manager", "name_en": "Factory Manager", "name_ar": "مدير المصنع", "description_en": "Oversee factory operations and departments", "description_ar": "الإشراف على عمليات المصنع وأقسامه", "permissions": ("production:*", "quality:*", "workforce:members:read", "commercial:orders:read")},
    {"code": "commercial_manager", "name_en": "Commercial Manager", "name_ar": "المدير التجاري", "description_en": "Manage commercial operations, customers, and sales", "description_ar": "إدارة العمليات التجارية والعملاء والمبيعات", "permissions": ("commercial:*",)},
    {"code": "sales_rep", "name_en": "Sales Representative", "name_ar": "مندوب مبيعات", "description_en": "Manage customers and commercial follow-ups", "description_ar": "إدارة العملاء والمتابعات التجارية", "permissions": ("production:demands:read", "commercial:customers:read", "commercial:customers:update", "commercial:interactions:read", "commercial:interactions:create", "commercial:follow_ups:read", "commercial:follow_ups:create", "commercial:follow_ups:update", "commercial:follow_ups:complete")},
    {"code": "production_manager", "name_en": "Production Manager", "name_ar": "مدير الإنتاج", "description_en": "Manage production operations and orders", "description_ar": "إدارة عمليات الإنتاج والأوامر", "permissions": ("production:*", "workforce:members:read")},
    {"code": "quality_manager", "name_en": "Quality Manager", "name_ar": "مدير الجودة", "description_en": "Manage quality control and inspections", "description_ar": "إدارة مراقبة الجودة والفحوصات", "permissions": ("quality:*",)},
    {"code": "warehouse_manager", "name_en": "Warehouse Manager", "name_ar": "مدير المستودع", "description_en": "Oversee warehouse-related factory operations", "description_ar": "الإشراف على عمليات المستودع المرتبطة بالمصنع", "permissions": ("production:production_orders:read", "workforce:members:read")},
    {"code": "shipping_manager", "name_en": "Shipping Manager", "name_ar": "مدير الشحن", "description_en": "Oversee shipping and order dispatch operations", "description_ar": "الإشراف على عمليات الشحن وتسليم الطلبات", "permissions": ("commercial:orders:read", "commercial:orders:update", "production:production_orders:read")},
    {"code": "maintenance_manager", "name_en": "Maintenance Manager", "name_ar": "مدير الصيانة", "description_en": "Manage factory maintenance and downtime", "description_ar": "إدارة صيانة المصنع وأحداث التوقف", "permissions": ("production:work_centers:read", "production:work_centers:write", "production:downtime_events:read", "production:downtime_events:write")},
    {"code": "procurement_manager", "name_en": "Procurement Manager", "name_ar": "مدير المشتريات", "description_en": "Oversee factory procurement requirements", "description_ar": "الإشراف على متطلبات مشتريات المصنع", "permissions": ("commercial:orders:read", "production:production_orders:read")},
    {"code": "hr_manager", "name_en": "Human Resources Manager", "name_ar": "مدير الموارد البشرية", "description_en": "Manage factory workforce records", "description_ar": "إدارة سجلات القوى العاملة في المصنع", "permissions": ("workforce:*",)},
    {"code": "safety_manager", "name_en": "Health and Safety Manager", "name_ar": "مدير السلامة والصحة المهنية", "description_en": "Oversee factory safety, incidents, and waste", "description_ar": "الإشراف على السلامة والحوادث والهدر في المصنع", "permissions": ("production:downtime_events:*", "production:waste_records:*", "quality:ncr_reports:*", "workforce:members:read")},
    {"code": "finance_manager", "name_en": "Finance Manager", "name_ar": "المدير المالي", "description_en": "Review quotations and commercial orders", "description_ar": "مراجعة عروض الأسعار والأوامر التجارية", "permissions": ("commercial:quotes:read", "commercial:orders:read")},
    {"code": "viewer", "name_en": "Viewer", "name_ar": "مستخدم للعرض", "description_en": "Read-only access to available modules", "description_ar": "صلاحية قراءة للوحدات المتاحة", "permissions": ("*:read",)},
)

SYSTEM_ROLE_BY_CODE = {str(role["code"]): role for role in SYSTEM_ROLES}

# Per-role scope override for scopable permissions (see SCOPABLE_PERMISSIONS in
# permission_catalog.py). Every permission not listed here keeps the default
# scope="organization" -- i.e. the exact pre-v0.2 behavior. Only sales_rep is
# narrowed to "own" for the entities it should only see its own records of.
SYSTEM_ROLE_SCOPE_OVERRIDES: dict[str, dict[str, str]] = {
    "sales_rep": {
        "commercial:customers:read": "own",
        "commercial:follow_ups:read": "own",
        "commercial:interactions:read": "own",
    },
}


def scope_for(role_code: str, permission_code: str) -> str:
    """Default scope="organization" unless overridden for this role/permission."""
    return SYSTEM_ROLE_SCOPE_OVERRIDES.get(role_code, {}).get(permission_code, "organization")


def permission_matches(code: str, pattern: str) -> bool:
    if pattern == "ALL":
        return not code.startswith("platform:")
    if pattern == "*:read":
        return code.endswith(":read")
    if pattern.endswith(":*"):
        return code.startswith(pattern[:-1])
    return code == pattern


for _role in SYSTEM_ROLES:
    for _pattern in _role["permissions"]:
        if _pattern not in {"ALL", "*:read"} and not str(_pattern).endswith(":*") and _pattern not in ALL_PERMISSION_CODES:
            raise ValueError(f"System role {_role['code']} references unknown permission: {_pattern}")
