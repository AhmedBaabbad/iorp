"""Organization-scoped system role catalog (RBAC-003).

One manager per module owns it entirely; an executing role sits under the manager where recording and deciding are
separate jobs (a production supervisor records the shift, a quality inspector the check; their managers decide). The
factory manager oversees: reads every operational module and takes the major decisions, not the daily work. The
organization administrator holds everything and never changes. A role a department may need later (warehouse,
maintenance, safety, finance, HR) is made as a custom role from the roles screen.

The VAT rate and default currency (masterdata:settings:update) belong to the administrator only; the administrator may
give that permission to another role from the roles screen.
"""

from app.foundation.domain.permission_catalog import ALL_PERMISSION_CODES
from app.production.domain import permissions as P
from app.quality.domain import permissions as Q
from app.quality.domain import report_permissions as QR
from app.shipping.domain import permissions as S
from app.procurement.domain import permissions as PR
from app.masterdata.domain import permissions as MD
from app.commercial.domain.report_permissions import ALL as CUSTOMER_REPORTS

_MD_DEFINE = (*MD.READ, MD.PRODUCTS_CREATE, MD.PRODUCTS_UPDATE, MD.PRODUCTS_MAP_LEGACY)  # managers who define products
_MD_LISTS = (MD.LISTS_UPDATE, MD.LISTS_MAP_LEGACY)  # managers who keep sectors, countries and cities
_NCR_ACTION_OWNER = (Q.NCR_READ, Q.NCR_ACTIONS_READ, Q.NCR_ACTIONS_COMPLETE)  # a department completes the actions assigned to it
_OPERATIONAL = ("production", "quality", "shipping", "procurement", "masterdata", "workforce")
_OPERATIONAL_READS = tuple(sorted(c for c in ALL_PERMISSION_CODES if c.endswith(":read") and c.split(":")[0] in _OPERATIONAL))
# The viewer reads the business, never the administration (users, roles, audit, security and activity logs).
_BUSINESS_READS = tuple(sorted(c for c in ALL_PERMISSION_CODES if c.endswith(":read") and not c.startswith(("foundation:", "reports:"))))

_SALES_REP = (
    "commercial:customers:read", "commercial:customers:update",
    "commercial:interactions:read", "commercial:interactions:create", "commercial:interactions:update",
    "commercial:follow_ups:read", "commercial:follow_ups:create", "commercial:follow_ups:update", "commercial:follow_ups:complete",
    "commercial:quotes:read", "commercial:quotes:create", "commercial:quotes:update", "commercial:quotes:issue", "commercial:quotes:accept",
    "commercial:quotes:reject", "commercial:quotes:expire", "commercial:quotes:revise",
    "commercial:samples:read", "commercial:samples:create", "commercial:samples:update", "commercial:samples:start",
    "commercial:samples:deliver", "commercial:samples:cancel", "commercial:samples:reopen", "commercial:samples:decide",
    "commercial:evaluations:read", "commercial:evaluations:create",
    # draft sales orders only: confirming, revising and cancelling stay with the commercial manager
    "commercial:orders:read", "commercial:orders:create", "commercial:orders:update",
    "reports:customers:customer_profile", "reports:customers:directory", "reports:customers:activity_summary",
    "reports:customers:customer_statement", S.SHIPMENTS_READ, S.RETURNS_READ, S.RETURNS_CREATE, *MD.READ,
)
_PRODUCTION_SUPERVISOR = (
    P.WORK_CENTERS_READ, P.code("shifts", "read"), P.code("shift_rosters", "read"), P.code("shift_rosters", "manage_members"),
    P.DEMANDS_READ, P.ORDERS_READ,
    *(P.code("runs", a) for a in ("read", "create", "update", "start", "pause", "complete", "manage_members")),
    *(P.code("results", a) for a in ("read", "create", "update")),
    P.DOWNTIME_READ, P.DOWNTIME_CREATE, P.DOWNTIME_UPDATE, P.DOWNTIME_CLOSE,
    P.WASTE_READ, P.WASTE_CREATE, P.WASTE_UPDATE,
    "workforce:members:read", P.REPORT_ORDER_FULL, *_NCR_ACTION_OWNER, Q.NCR_CREATE, *MD.READ,
)
_QUALITY_INSPECTOR = (
    Q.CHECKS_READ, Q.CHECKS_CREATE, Q.CHECKS_UPDATE, Q.CHECKS_START, Q.CHECKS_MEASURE, Q.CHECKS_CLOSE,
    Q.DEFECTS_READ, Q.DEFECTS_CREATE, Q.DEFECTS_UPDATE, Q.REJECTIONS_READ, Q.REJECTIONS_CREATE,
    Q.NCR_READ, Q.NCR_CREATE, Q.NCR_ACTIONS_READ, Q.NCR_ACTIONS_COMPLETE, Q.SPECS_READ, Q.COA_READ,
    P.ORDERS_READ, PR.RECEIPTS_READ, PR.MATERIALS_READ, S.RETURNS_READ, "reports:quality:check_full", *MD.READ,
)
_FACTORY_MANAGER = (
    *_OPERATIONAL_READS, "commercial:customers:read", "commercial:quotes:read", "commercial:orders:read",
    P.DEMANDS_RELEASE, P.DEMANDS_CANCEL, P.ORDERS_RELEASE, P.ORDERS_HOLD, P.ORDERS_CLOSE, P.ORDERS_CANCEL, P.RESULTS_CORRECT,
    Q.REJECTIONS_DECIDE, Q.NCR_VERIFY, Q.NCR_CANCEL, Q.SPECS_ACTIVATE, Q.COA_ISSUE, Q.COA_REVOKE,
    S.RETURNS_APPROVE, S.RETURNS_REJECT, PR.PO_APPROVE, PR.SUPPLIERS_APPROVE, *P.REPORTS, *QR.ALL,
)

SYSTEM_ROLES: tuple[dict[str, object], ...] = (
    {"code": "organization_admin", "name_en": "Organization Administrator", "name_ar": "مدير المنظمة", "description_en": "Full organization administration access", "description_ar": "صلاحيات إدارة المنظمة الكاملة", "is_protected": True, "permissions": ("ALL",)},
    {"code": "commercial_manager", "name_en": "Commercial Manager", "name_ar": "المدير التجاري", "description_en": "Runs the commercial module: customers, samples, quotations, sales orders and follow-ups",
     "description_ar": "يدير الموديل التجاري كاملاً: العملاء والعينات وعروض الأسعار وأوامر البيع والمتابعات",
     "permissions": ("commercial:*", *CUSTOMER_REPORTS, S.SHIPMENTS_READ, S.RETURNS_READ, S.RETURNS_CREATE, S.RETURNS_APPROVE, S.RETURNS_REJECT,
                     S.RETURNS_CANCEL, P.DEMANDS_READ, *_MD_DEFINE, *_MD_LISTS)},
    {"code": "sales_rep", "name_en": "Sales Representative", "name_ar": "مندوب مبيعات", "description_en": "Works their own customers: quotations, samples, draft sales orders and follow-ups",
     "description_ar": "يعمل على عملائه فقط: عروض الأسعار والعينات وأوامر البيع المسودة والمتابعات", "permissions": _SALES_REP},
    {"code": "production_manager", "name_en": "Production Manager", "name_ar": "مدير الإنتاج", "description_en": "Runs the production module, its crews and reports",
     "description_ar": "يدير موديل الإنتاج كاملاً مع فرق العمل وتقارير الإنتاج",
     "permissions": (*P.ALL, *P.REPORTS, "workforce:*", "commercial:orders:read", *_NCR_ACTION_OWNER, *_MD_DEFINE)},
    {"code": "production_supervisor", "name_en": "Production Supervisor", "name_ar": "مشرف إنتاج", "description_en": "Records the shift: runs, results, downtime and scrap",
     "description_ar": "يسجّل عمل الوردية: التشغيل والنتائج والتوقف والهالك", "permissions": _PRODUCTION_SUPERVISOR},
    {"code": "quality_manager", "name_en": "Quality Manager", "name_ar": "مدير الجودة", "description_en": "Runs the quality module, its decisions and reports",
     "description_ar": "يدير موديل الجودة كاملاً مع قراراته وتقاريره",
     "permissions": (*Q.ALL, *QR.ALL, P.ORDERS_READ, S.SHIPMENTS_READ, S.RETURNS_READ, *PR.READ, PR.SUPPLIERS_APPROVE, PR.MATERIALS_UPDATE, *_MD_DEFINE)},
    {"code": "quality_inspector", "name_en": "Quality Inspector", "name_ar": "مفتش جودة", "description_en": "Carries out inspections: checks, measurements, defects",
     "description_ar": "ينفّذ الفحوصات: القياسات والعيوب وتسجيل المرفوض", "permissions": _QUALITY_INSPECTOR},
    {"code": "procurement_manager", "name_en": "Procurement Manager", "name_ar": "مدير المشتريات", "description_en": "Runs procurement: suppliers, materials, purchase orders and goods receipts",
     "description_ar": "يدير المشتريات: الموردين والمواد وأوامر الشراء واستلام المواد",
     "permissions": (*PR.ALL, P.ORDERS_READ, "commercial:orders:read", P.REPORT_ORDERS_SUMMARY, *_NCR_ACTION_OWNER, *MD.READ, *_MD_LISTS)},
    {"code": "shipping_manager", "name_en": "Shipping Manager", "name_ar": "مدير الشحن", "description_en": "Runs shipping: preparing, dispatching, delivering and returns",
     "description_ar": "يدير الشحن: التجهيز والإخراج والتسليم والمرتجعات",
     "permissions": (*S.ALL, "commercial:orders:read", "commercial:customers:read", P.ORDERS_READ, P.REPORT_ORDER_FULL, P.REPORT_ORDERS_SUMMARY,
                     *_NCR_ACTION_OWNER, Q.NCR_CREATE, *MD.READ, *_MD_LISTS)},
    {"code": "factory_manager", "name_en": "Factory Manager", "name_ar": "مدير المصنع", "description_en": "Oversees the factory and takes its major decisions",
     "description_ar": "يشرف على المصنع ويتخذ القرارات الكبرى", "permissions": _FACTORY_MANAGER},
    {"code": "viewer", "name_en": "Viewer", "name_ar": "مستخدم للعرض", "description_en": "Reads the business modules and their reports",
     "description_ar": "يعرض بيانات العمل وتقاريرها فقط", "permissions": (*_BUSINESS_READS, *P.REPORTS, *QR.ALL)},
)
# Removed in RBAC-003 (migration f6a1b2k9 turns one still assigned to a user into a custom role with its permissions).
RETIRED_SYSTEM_ROLES = ("warehouse_manager", "maintenance_manager", "safety_manager", "finance_manager", "hr_manager")

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
        "commercial:quotes:read": "own",
        "commercial:orders:read": "own",
        "commercial:samples:read": "own",
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
