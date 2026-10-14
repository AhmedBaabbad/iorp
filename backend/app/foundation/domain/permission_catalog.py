"""Canonical registry for every tenant permission in IORP.

Platform permissions deliberately live outside this module. Tenant permission
rows, API metadata, system-role grants, and tests all derive from this file.
"""

from dataclasses import dataclass, replace
import re

# Each module declares its own permissions (a pure domain module); the catalog registers them.
from app.production.domain import permissions as production_permissions
from app.quality.domain import permissions as quality_permissions
from app.shipping.domain import permissions as shipping_permissions
from app.procurement.domain import permissions as procurement_permissions
from app.masterdata.domain import permissions as masterdata_permissions
from app.notifications.domain import permissions as notification_permissions


@dataclass(frozen=True)
class PermissionDefinition:
    code: str
    module: str
    resource: str
    action: str
    name_en: str
    name_ar: str
    description_en: str
    description_ar: str
    scopable: bool = False
    owner_field: str | None = None


MODULE_NAMES = {
    "organization": {"en": "Organization identity", "ar": "هوية المؤسسة"},
    "reports": {"en": "Reports", "ar": "التقارير"},
    "foundation": {"en": "Administration", "ar": "الإدارة"},
    "commercial": {"en": "Commercial", "ar": "التجاري"},
    "production": {"en": "Production", "ar": "الإنتاج"},
    "quality": {"en": "Quality", "ar": "الجودة"},
    "shipping": {"en": "Shipping", "ar": "الشحن والتسليم"},
    "procurement": {"en": "Procurement", "ar": "المشتريات"},
    "masterdata": {"en": "Master data", "ar": "البيانات الأساسية"},
    "workforce": {"en": "Workforce", "ar": "القوى العاملة"},
    "notifications": {"en": "Notifications", "ar": "الإشعارات"},
}

RESOURCE_NAMES = {
    "directory": ("Transport directory", "دليل النقل"),
    "delegations": ("Approval Delegations", "تفويضات الاعتماد"),
    "announcements": ("Announcements", "الإعلانات"),
    "complaints": ("Customer complaints", "شكاوى العملاء"),
    "shifts": ("Shifts", "الورديات"),
    "shift_rosters": ("Shift Rosters", "فرق الورديات"),
    "runs": ("Production Runs", "تشغيل الإنتاج"),
    "demands": ("Production Demands", "طلبات الإنتاج"),
    "planning": ("Planning Queue", "قائمة التخطيط"),
    "organization": ("Organization", "المنظمة"), "users": ("Users", "المستخدمين"),
    "roles": ("Roles", "الأدوار"), "permissions": ("Permissions", "الصلاحيات"),
    "user_roles": ("User Roles", "أدوار المستخدمين"), "role_permissions": ("Role Permissions", "صلاحيات الأدوار"),
    "audit": ("Audit Log", "سجل التدقيق"),
    "security_log": ("Security Events", "سجل الأحداث الأمنية"),
    "activity_log": ("Activity Log", "سجل النشاطات"),
    "customers": ("Customers", "العملاء"), "interactions": ("Interactions", "التفاعلات"),
    "follow_ups": ("Follow-ups", "المتابعات"), "samples": ("Samples", "العينات"),
    "evaluations": ("Evaluations", "التقييمات"), "quotes": ("Quotes", "عروض الأسعار"),
    "quote_settings": ("Quotation Settings", "إعدادات عروض الأسعار"),
    "orders": ("Orders", "الطلبات"), "work_centers": ("Work Centers", "مراكز العمل"),
    "production_orders": ("Production Orders", "أوامر الإنتاج"),
    "downtime_events": ("Downtime Events", "أحداث التوقف"), "waste_records": ("Waste Records", "سجلات الهدر"),
    "results": ("Production Results", "النتيجة النهائية للإنتاج"),
    "quality_checks": ("Quality Checks", "فحوصات الجودة"), "quality_defects": ("Quality Defects", "عيوب الجودة"),
    "rejections": ("Rejections", "حالات الرفض"), "ncr_reports": ("NCR Reports", "تقارير عدم المطابقة"),
    "specifications": ("Product Specifications", "مواصفات المنتجات"),
    "certificates": ("Certificates of Analysis", "شهادات التحليل"),
    "ncr_actions": ("Corrective Actions", "الإجراءات التصحيحية"),
    "suppliers": ("Suppliers", "الموردين"), "materials": ("Materials", "المواد"),
    "receipts": ("Goods Receipts", "استلام المواد"), "purchase_orders": ("Purchase Orders", "أوامر الشراء"),
    "shipments": ("Shipments", "الشحنات"), "returns": ("Returns", "المرتجعات"), "settings": ("Settings", "الإعدادات"),
    "members": ("Workforce Members", "أعضاء القوى العاملة"),
    "products": ("Products", "المنتجات"), "lists": ("Reference Lists", "القوائم المرجعية"),
}

ACTION_NAMES = {
    "manage": ("Manage", "إدارة"),
    "resolve": ("Resolve", "معالجة"),
    "report": ("Report", "تقارير"),
    'ready': ('Mark Ready', 'تجهيز للإرسال'),
    'contain': ('Record Containment of', 'تسجيل احتواء'), 'investigate': ('Record Root Cause of', 'تسجيل السبب الجذري لـ'),
    'submit': ('Submit for Verification', 'إرسال للتحقق'), 'fail': ('Record Failed Delivery of', 'تسجيل تعذّر تسليم'),
    'send': ('Send', 'إرسال'), 'map_legacy': ('Map Legacy Values to', 'ربط القيم القديمة بـ'),
    'reschedule': ('Reschedule', 'إعادة جدولة'),
    'confirm': ('Confirm', 'اعتماد'), 'accept': ('Accept', 'قبول'), 'reject': ('Reject', 'رفض'),
    'expire': ('Expire', 'إنهاء صلاحية'), 'revise': ('Revise', 'فتح مراجعة'),
    'reopen': ('Reopen', 'إعادة فتح'),
    "start": ("Start", "بدء"),
    "release": ("Release", "اعتماد"),
    "verify": ("Verify", "التحقق من"),
    "correct": ("Correct", "تصحيح"),
    "hold": ("Hold", "تعليق"),
    "close": ("Close", "إغلاق"),
    "pause": ("Pause", "إيقاف مؤقت لـ"),
    "cancel": ("Cancel", "إلغاء"),
    "release_allocation": ("Release Allocations in", "تحرير تخصيصات"),
    "manage_members": ("Manage Members", "إدارة الأعضاء"),
    "allocate": ("Allocate Quantities for", "تخصيص كميات"),
    "sequence": ("Manage Sequence for", "ترتيب"),
    "read": ("Read", "عرض"), "create": ("Create", "إنشاء"), "update": ("Update", "تحديث"),
    "delete": ("Delete", "حذف"), "write": ("Manage", "إدارة"), "activate": ("Activate", "تفعيل"),
    "deactivate": ("Deactivate", "تعطيل"), "lock": ("Lock or Unlock", "قفل أو فتح"),
    "reset_password": ("Reset Password for", "إعادة تعيين كلمة مرور"),
    "branding": ("Manage Branding for", "إدارة الهوية البصرية لـ"), "assign": ("Assign", "تعيين"),
    "complete": ("Complete", "إكمال"), "assign_owner": ("Assign Owner for", "تعيين المسؤول عن"),
    "link_user": ("Link User to", "ربط مستخدم بـ"),
    "manage_items": ("Manage Items of", "إدارة بنود"),
    "decide": ("Decide", "اتخاذ قرار"),
    "execute": ("Execute", "تنفيذ"),
    "measure": ("Record Measurements for", "تسجيل قياسات"),
    "issue": ("Issue", "إصدار"),
    "revoke": ("Revoke", "إلغاء"),
    "dispatch": ("Dispatch", "إخراج"),
    "deliver": ("Confirm Delivery of", "تأكيد تسليم"),
    "approve": ("Approve", "اعتماد"),
    "archive": ("Archive", "أرشفة"),
    "receive": ("Receive", "استلام"),
}


def _permission(module: str, resource: str, action: str) -> PermissionDefinition:
    resource_en, resource_ar = RESOURCE_NAMES[resource]
    action_en, action_ar = ACTION_NAMES[action]
    return PermissionDefinition(
        code=f"{module}:{resource}:{action}", module=module, resource=resource, action=action,
        name_en=f"{action_en} {resource_en}", name_ar=f"{action_ar} {resource_ar}",
        description_en=f"Allows the account to {action_en.lower()} {resource_en.lower()}.",
        description_ar=f"تسمح للحساب بـ{action_ar} {resource_ar}.",
    )


def _resource_permissions(module: str, definitions: dict[str, tuple[str, ...]]) -> list[PermissionDefinition]:
    return [_permission(module, resource, action) for resource, actions in definitions.items() for action in actions]


FOUNDATION_PERMISSIONS = _resource_permissions("foundation", {
    "organization": ("read", "update", "branding"),
    "users": ("read", "write", "activate", "deactivate", "delete", "lock", "reset_password"),
    "roles": ("read", "write"), "permissions": ("read",),
    "user_roles": ("write",), "role_permissions": ("write",), "audit": ("read",),
    "security_log": ("read",), "activity_log": ("read", "archive"),
    # PROJECT-GOV-004: read every delegation; approve holders' requests, give and revoke anyone's. A holder delegates
    # their own approvals without a further permission (a manager then agrees).
    "delegations": ("read", "manage"),
})

# Row-level ownership scope (own/team/organization, see AccessScope) is only
# meaningful for READ permissions on entities with an owner-like column. Every
# other permission is implicitly organization-wide (scopable=False).
SCOPABLE_OWNER_FIELDS: dict[str, str] = {
    "commercial:complaints:read": "customer.sales_owner_user_id",
    "commercial:customers:read": "sales_owner_user_id",
    "commercial:follow_ups:read": "assigned_user_id",
    "commercial:interactions:read": "created_by_user_id",
    # RBAC-002: a quotation, sales order or sample is its customer's; "own" = the customers whose sales owner is the user.
    "commercial:quotes:read": "customer.sales_owner_user_id",
    "commercial:orders:read": "customer.sales_owner_user_id",
    "commercial:samples:read": "customer.sales_owner_user_id",
}


def _apply_scope_overrides(permissions: list["PermissionDefinition"]) -> list["PermissionDefinition"]:
    return [
        replace(p, scopable=True, owner_field=SCOPABLE_OWNER_FIELDS[p.code])
        if p.code in SCOPABLE_OWNER_FIELDS else p
        for p in permissions
    ]


# RBAC-002: the vague "write" (manage) permissions were removed: create, update and delete say exactly what is allowed.
COMMERCIAL_PERMISSIONS = _apply_scope_overrides(_resource_permissions("commercial", {
    "complaints": ("read", "create", "update", "assign", "investigate", "resolve", "close", "reopen", "cancel", "report"),
    "customers": ("read", "create", "update", "delete", "assign_owner"),
    "interactions": ("read", "create", "update", "delete"),
    "follow_ups": ("read", "create", "update", "delete", "assign", "complete"),
    "samples": ("read", "create", "update", "delete"),
    "evaluations": ("read", "create", "update", "delete"),
    "quotes": ("read", "create", "update", "delete"),
    # Quotation document settings: signature and the bilingual terms and conditions (QUOTE-DOC-001).
    "quote_settings": ("read", "update"),
    "orders": ("read", "create", "update", "delete"),
}))

def _labelled(permission: PermissionDefinition, labels: dict[str, tuple[str, str]]) -> PermissionDefinition:
    if permission.code not in labels:
        return permission
    en, ar = labels[permission.code]
    return replace(permission, name_en=en, name_ar=ar, description_en=f"Allows the account to {en[0].lower()}{en[1:]}.",
                   description_ar=f"تسمح للحساب بـ{ar}.")


from app.commercial.domain.action_permissions import EXTRA_ACTIONS
COMMERCIAL_PERMISSIONS += _resource_permissions('commercial', EXTRA_ACTIONS)


# PROD-RBAC-001: read/create/update/delete plus explicit actions, from production/domain/permissions.py.
PRODUCTION_PERMISSIONS = [_labelled(p, production_permissions.LABELS)
                          for p in _resource_permissions(production_permissions.MODULE, production_permissions.RESOURCES)]

# QUAL-001: one permission per action, from quality/domain/permissions.py.
QUALITY_PERMISSIONS = [_labelled(p, quality_permissions.LABELS)
                       for p in _resource_permissions(quality_permissions.MODULE, quality_permissions.RESOURCES)]

# SHIP-001: one permission per action, from shipping/domain/permissions.py.
SHIPPING_PERMISSIONS = [_labelled(p, shipping_permissions.LABELS)
                        for p in _resource_permissions(shipping_permissions.MODULE, shipping_permissions.RESOURCES)]

# PROC-001: one permission per action, from procurement/domain/permissions.py.
PROCUREMENT_PERMISSIONS = [_labelled(p, procurement_permissions.LABELS)
                           for p in _resource_permissions(procurement_permissions.MODULE, procurement_permissions.RESOURCES)]

# MD-001: products, their specification templates and the general settings, from masterdata/domain/permissions.py.
MASTERDATA_PERMISSIONS = [_labelled(p, masterdata_permissions.LABELS)
                          for p in _resource_permissions(masterdata_permissions.MODULE, masterdata_permissions.RESOURCES)]

# PROJECT-NOTIFY-001: announcements, from notifications/domain/permissions.py (every user reads their own notifications).
NOTIFICATION_PERMISSIONS = [_labelled(p, notification_permissions.LABELS)
                            for p in _resource_permissions(notification_permissions.MODULE, notification_permissions.RESOURCES)]

WORKFORCE_PERMISSIONS = _resource_permissions("workforce", {
    "members": ("read", "create", "update", "delete", "link_user"),
})

REPORTING_PERMISSIONS = [PermissionDefinition(code, *code.split(":"), en, ar, en, ar) for code, en, ar in (
    ("organization:branding:read", "Read company identity", "عرض هوية الشركة"),
    ("organization:branding:update", "Update company identity", "تعديل هوية الشركة"),
    (production_permissions.REPORT_ORDER_FULL, "Production order report", "تقرير أمر الإنتاج"),
    (production_permissions.REPORT_ORDERS_SUMMARY, "Production orders summary", "ملخص أوامر الإنتاج"),
    (production_permissions.REPORT_RESULTS_ANALYSIS, "Production results analysis", "تحليل نتائج الإنتاج"),
    (production_permissions.REPORT_SHIFT_WORKFORCE, "Shift workforce report", "تقرير فرق الورديات"),
)]

from app.commercial.domain.report_permissions import LABELS as CUSTOMER_REPORT_LABELS
REPORTING_PERMISSIONS += [PermissionDefinition('reports:customers:'+key, 'reports', 'customers', key, en, ar, en, ar)
                         for key, (en, ar) in CUSTOMER_REPORT_LABELS.items()]
from app.quality.domain.report_permissions import LABELS as QUALITY_REPORT_LABELS
REPORTING_PERMISSIONS += [PermissionDefinition('reports:quality:'+key, 'reports', 'quality', key, en, ar, en, ar)
                         for key, (en, ar) in QUALITY_REPORT_LABELS.items()]

# RBAC-002: every permission's name and description, as people read them (permission_labels.py); the code never changes.
from app.foundation.domain.permission_labels import LABELS as PERMISSION_LABELS


def _named(permission: PermissionDefinition) -> PermissionDefinition:
    if permission.code not in PERMISSION_LABELS:
        return permission
    ar, en, description_ar, description_en = PERMISSION_LABELS[permission.code]
    return replace(permission, name_ar=ar, name_en=en, description_ar=description_ar, description_en=description_en)


ALL_TENANT_PERMISSIONS = [_named(p) for p in (
    FOUNDATION_PERMISSIONS + COMMERCIAL_PERMISSIONS + PRODUCTION_PERMISSIONS
    + QUALITY_PERMISSIONS + SHIPPING_PERMISSIONS + PROCUREMENT_PERMISSIONS + MASTERDATA_PERMISSIONS + WORKFORCE_PERMISSIONS + NOTIFICATION_PERMISSIONS
    + REPORTING_PERMISSIONS
)]
PERMISSION_BY_CODE = {permission.code: permission for permission in ALL_TENANT_PERMISSIONS}
ALL_PERMISSION_CODES = frozenset(PERMISSION_BY_CODE)
PERMISSIONS_BY_MODULE: dict[str, list[PermissionDefinition]] = {}
for permission in ALL_TENANT_PERMISSIONS:
    PERMISSIONS_BY_MODULE.setdefault(permission.module, []).append(permission)

# code -> owner_field, for every permission a role-permission scope can restrict.
# Repositories/routes read this to know which column to filter on for scope=own;
# it does not itself perform any filtering.
SCOPABLE_PERMISSIONS: dict[str, str] = {
    permission.code: permission.owner_field
    for permission in ALL_TENANT_PERMISSIONS
    if permission.scopable and permission.owner_field
}
for permission in ALL_TENANT_PERMISSIONS:
    if permission.scopable and not permission.owner_field:
        raise ValueError(f"Scopable permission missing owner_field: {permission.code}")
    if permission.owner_field and not permission.scopable:
        raise ValueError(f"owner_field set without scopable=True: {permission.code}")

# Compatibility representation for older callers while retaining this file as
# the only definition source.
PERMISSIONS = [
    {"code": permission.code, "name": permission.name_en, "module_name": permission.module,
     "description": permission.description_en, "resource_name": permission.resource,
     "action_name": permission.action}
    for permission in ALL_TENANT_PERMISSIONS
]

_codes = [permission.code for permission in ALL_TENANT_PERMISSIONS]
_duplicates = {code for code in _codes if _codes.count(code) > 1}
if _duplicates:
    raise ValueError(f"Duplicate permission codes in catalog: {_duplicates}")
_code_pattern = re.compile(r"^[a-z_]+:[a-z_]+:[a-z_]+$")
for permission in ALL_TENANT_PERMISSIONS:
    if not _code_pattern.fullmatch(permission.code):
        raise ValueError(f"Invalid permission code format: {permission.code}")
    if permission.code.split(":") != [permission.module, permission.resource, permission.action]:
        raise ValueError(f"Permission code/fields mismatch: {permission.code}")
    if permission.module not in MODULE_NAMES:
        raise ValueError(f"Missing module display name: {permission.module}")
