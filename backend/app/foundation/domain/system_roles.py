"""Organization-scoped system role catalog."""

from app.foundation.domain.permission_catalog import ALL_PERMISSION_CODES
from app.production.domain import permissions as P
from app.quality.domain import permissions as Q
from app.quality.domain import report_permissions as QR
from app.shipping.domain import permissions as S
from app.commercial.domain.report_permissions import ALL as CUSTOMER_REPORTS, SALES as SALES_REPORTS

# Shipping and delivery (SHIP-004): the shipping manager runs it all; the warehouse prepares, dispatches and receives
# goods back; sales register a customer's return, the commercial and factory managers approve it; quality and
# finance follow returns (quality decides on returned goods later, finance credits them).
_SHIP_READ = (S.SHIPMENTS_READ, S.RETURNS_READ)

# Production roles list their permissions explicitly (PROD-RBAC-001), generated from the
# production catalog: a new production permission is granted by editing these lists, never by a wildcard.
_PRODUCTION_FULL = P.ALL + P.REPORTS
# A report follows the data it shows: a role that reads production orders may run the order reports,
# one that reads workforce members the shift workforce report (as granted by migration f6a1b2h8).
_VIEWER_REPORTS = (P.REPORT_ORDER_FULL, P.REPORT_ORDERS_SUMMARY, P.REPORT_RESULTS_ANALYSIS, P.REPORT_SHIFT_WORKFORCE)

SYSTEM_ROLES: tuple[dict[str, object], ...] = (
    {"code": "organization_admin", "name_en": "Organization Administrator", "name_ar": "مدير المنظمة", "description_en": "Full organization administration access", "description_ar": "صلاحيات إدارة المنظمة الكاملة", "is_protected": True, "permissions": ("ALL",)},
    {"code": "factory_manager", "name_en": "Factory Manager", "name_ar": "مدير المصنع", "description_en": "Oversee factory operations and departments", "description_ar": "الإشراف على عمليات المصنع وأقسامه", "permissions": (*_PRODUCTION_FULL, *Q.ALL, *QR.ALL, "workforce:members:read", "commercial:orders:read", *_SHIP_READ, S.RETURNS_APPROVE)},
    {"code": "commercial_manager", "name_en": "Commercial Manager", "name_ar": "المدير التجاري", "description_en": "Manage commercial operations, customers, and sales", "description_ar": "إدارة العمليات التجارية والعملاء والمبيعات", "permissions": ("commercial:*", *CUSTOMER_REPORTS, *_SHIP_READ, S.RETURNS_CREATE, S.RETURNS_APPROVE, S.RETURNS_CANCEL)},
    {"code": "sales_rep", "name_en": "Sales Representative", "name_ar": "مندوب مبيعات", "description_en": "Manage customers and commercial follow-ups", "description_ar": "إدارة العملاء والمتابعات التجارية", "permissions": (*SALES_REPORTS, P.DEMANDS_READ, "commercial:customers:read", "commercial:customers:update", "commercial:interactions:read", "commercial:interactions:create", "commercial:follow_ups:read", "commercial:follow_ups:create", "commercial:follow_ups:update", "commercial:follow_ups:complete", *_SHIP_READ, S.RETURNS_CREATE)},
    {"code": "production_manager", "name_en": "Production Manager", "name_ar": "مدير الإنتاج", "description_en": "Manage production operations and orders", "description_ar": "إدارة عمليات الإنتاج والأوامر", "permissions": (*_PRODUCTION_FULL, "workforce:members:read")},
    {"code": "quality_manager", "name_en": "Quality Manager", "name_ar": "مدير الجودة", "description_en": "Manage quality control and inspections", "description_ar": "إدارة مراقبة الجودة والفحوصات", "permissions": (*Q.ALL, *QR.ALL, P.ORDERS_READ, *_SHIP_READ)},
    {"code": "warehouse_manager", "name_en": "Warehouse Manager", "name_ar": "مدير المستودع", "description_en": "Oversee warehouse-related factory operations", "description_ar": "الإشراف على عمليات المستودع المرتبطة بالمصنع", "permissions": (P.ORDERS_READ, "workforce:members:read", P.REPORT_ORDER_FULL, P.REPORT_ORDERS_SUMMARY, P.REPORT_SHIFT_WORKFORCE,
        S.SHIPMENTS_READ, S.SHIPMENTS_CREATE, S.SHIPMENTS_UPDATE, S.SHIPMENTS_DISPATCH, S.RETURNS_READ, S.RETURNS_RECEIVE)},
    {"code": "shipping_manager", "name_en": "Shipping Manager", "name_ar": "مدير الشحن", "description_en": "Oversee shipping and order dispatch operations", "description_ar": "الإشراف على عمليات الشحن وتسليم الطلبات", "permissions": ("commercial:orders:read", "commercial:orders:update", P.ORDERS_READ, P.REPORT_ORDER_FULL, P.REPORT_ORDERS_SUMMARY, *S.ALL)},
    {"code": "maintenance_manager", "name_en": "Maintenance Manager", "name_ar": "مدير الصيانة", "description_en": "Manage factory maintenance and downtime", "description_ar": "إدارة صيانة المصنع وأحداث التوقف", "permissions": (P.WORK_CENTERS_READ, P.WORK_CENTERS_CREATE, P.WORK_CENTERS_UPDATE, P.WORK_CENTERS_DELETE,
        P.DOWNTIME_READ, P.DOWNTIME_CREATE, P.DOWNTIME_UPDATE, P.DOWNTIME_DELETE, P.DOWNTIME_CLOSE)},
    {"code": "procurement_manager", "name_en": "Procurement Manager", "name_ar": "مدير المشتريات", "description_en": "Oversee factory procurement requirements", "description_ar": "الإشراف على متطلبات مشتريات المصنع", "permissions": ("commercial:orders:read", P.ORDERS_READ, P.REPORT_ORDER_FULL, P.REPORT_ORDERS_SUMMARY)},
    {"code": "hr_manager", "name_en": "Human Resources Manager", "name_ar": "مدير الموارد البشرية", "description_en": "Manage factory workforce records", "description_ar": "إدارة سجلات القوى العاملة في المصنع", "permissions": ("workforce:*", P.REPORT_SHIFT_WORKFORCE)},
    {"code": "safety_manager", "name_en": "Health and Safety Manager", "name_ar": "مدير السلامة والصحة المهنية", "description_en": "Oversee factory safety, incidents, and waste", "description_ar": "الإشراف على السلامة والحوادث والهدر في المصنع", "permissions": (P.DOWNTIME_READ, P.DOWNTIME_CREATE, P.DOWNTIME_UPDATE, P.DOWNTIME_DELETE, P.DOWNTIME_CLOSE,
        P.WASTE_READ, P.WASTE_CREATE, P.WASTE_UPDATE, P.WASTE_DELETE, Q.NCR_READ, Q.NCR_CREATE, Q.NCR_UPDATE, "workforce:members:read", P.REPORT_SHIFT_WORKFORCE)},
    {"code": "finance_manager", "name_en": "Finance Manager", "name_ar": "المدير المالي", "description_en": "Review quotations and commercial orders", "description_ar": "مراجعة عروض الأسعار والأوامر التجارية", "permissions": ("commercial:quotes:read", "commercial:orders:read", *_SHIP_READ)},
    {"code": "viewer", "name_en": "Viewer", "name_ar": "مستخدم للعرض", "description_en": "Read-only access to available modules", "description_ar": "صلاحية قراءة للوحدات المتاحة", "permissions": ("*:read", *_VIEWER_REPORTS, *QR.ALL)},
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
