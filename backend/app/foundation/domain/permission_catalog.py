"""Canonical registry for every tenant permission in IORP.

Platform permissions deliberately live outside this module. Tenant permission
rows, API metadata, system-role grants, and tests all derive from this file.
"""

from dataclasses import dataclass, replace
import re


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
    "foundation": {"en": "Administration", "ar": "الإدارة"},
    "commercial": {"en": "Commercial", "ar": "التجاري"},
    "production": {"en": "Production", "ar": "الإنتاج"},
    "quality": {"en": "Quality", "ar": "الجودة"},
    "workforce": {"en": "Workforce", "ar": "القوى العاملة"},
}

RESOURCE_NAMES = {
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
    "orders": ("Orders", "الطلبات"), "work_centers": ("Work Centers", "مراكز العمل"),
    "production_orders": ("Production Orders", "أوامر الإنتاج"), "shift_reports": ("Shift Reports", "تقارير الورديات"),
    "downtime_events": ("Downtime Events", "أحداث التوقف"), "waste_records": ("Waste Records", "سجلات الهدر"),
    "shift_definitions": ("Shift Definitions", "تعريفات الورديات"), "production_outputs": ("Production Outputs", "مخرجات الإنتاج"),
    "quality_checks": ("Quality Checks", "فحوصات الجودة"), "quality_defects": ("Quality Defects", "عيوب الجودة"),
    "rejections": ("Rejections", "حالات الرفض"), "ncr_reports": ("NCR Reports", "تقارير عدم المطابقة"),
    "members": ("Workforce Members", "أعضاء القوى العاملة"),
}

ACTION_NAMES = {
    "start": ("Start", "بدء"),
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
    "users": ("read", "write", "activate", "deactivate", "lock", "reset_password"),
    "roles": ("read", "write"), "permissions": ("read",),
    "user_roles": ("write",), "role_permissions": ("write",), "audit": ("read",),
    "security_log": ("read",), "activity_log": ("read",),
})

# Row-level ownership scope (own/team/organization, see AccessScope) is only
# meaningful for READ permissions on entities with an owner-like column. Every
# other permission is implicitly organization-wide (scopable=False).
SCOPABLE_OWNER_FIELDS: dict[str, str] = {
    "commercial:customers:read": "sales_owner_user_id",
    "commercial:follow_ups:read": "assigned_user_id",
    "commercial:interactions:read": "created_by_user_id",
}


def _apply_scope_overrides(permissions: list["PermissionDefinition"]) -> list["PermissionDefinition"]:
    return [
        replace(p, scopable=True, owner_field=SCOPABLE_OWNER_FIELDS[p.code])
        if p.code in SCOPABLE_OWNER_FIELDS else p
        for p in permissions
    ]


COMMERCIAL_PERMISSIONS = _apply_scope_overrides(_resource_permissions("commercial", {
    "customers": ("read", "create", "update", "delete", "write", "assign_owner"),
    "interactions": ("read", "create", "update", "delete", "write"),
    "follow_ups": ("read", "create", "update", "delete", "write", "assign", "complete"),
    "samples": ("read", "create", "update", "delete", "write"),
    "evaluations": ("read", "create", "update", "delete"),
    "quotes": ("read", "create", "update", "delete", "write"),
    "orders": ("read", "create", "update", "delete", "write"),
}))

PRODUCTION_PERMISSIONS = _resource_permissions("production", {
    resource: ("read", "write") for resource in
    ("work_centers", "production_orders", "shift_reports", "downtime_events", "waste_records", "shift_definitions", "production_outputs")
})

PRODUCTION_PERMISSIONS += _resource_permissions("production", {"demands": ("read", "create", "update", "delete"), "planning": ("read", "sequence", "allocate", "release_allocation"), "orders": ("create", "cancel")})

PRODUCTION_PERMISSIONS += _resource_permissions("production", {"shifts": ("read", "create", "update", "delete"), "shift_rosters": ("read", "create", "update", "manage_members"), "runs": ("read", "create", "update", "start", "pause", "complete", "cancel", "manage_members")})

QUALITY_PERMISSIONS = _resource_permissions("quality", {
    resource: ("read", "write") for resource in
    ("quality_checks", "quality_defects", "rejections", "ncr_reports")
})

WORKFORCE_PERMISSIONS = _resource_permissions("workforce", {
    "members": ("read", "create", "update", "delete", "link_user"),
})

ALL_TENANT_PERMISSIONS = (
    FOUNDATION_PERMISSIONS + COMMERCIAL_PERMISSIONS + PRODUCTION_PERMISSIONS
    + QUALITY_PERMISSIONS + WORKFORCE_PERMISSIONS
)
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
