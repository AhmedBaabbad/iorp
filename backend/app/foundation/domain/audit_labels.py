"""How people read the audit trail (ORG-AUDIT-002): each action and each kind of record, in Arabic and English. The
screens carry the same words (tenantAudit.actions / tenantAudit.entities); the CSV export uses these."""

ACTIONS: dict[str, tuple[str, str]] = {
    "user.created": ("إنشاء مستخدم", "User created"),
    "user.archived": ("أرشفة حساب مستخدم", "User account archived"),
    "user.archive_restored": ("استعادة حساب من الأرشيف", "User account restored from archive"),
    "user.email_change_requested": ("طلب تغيير بريد الدخول", "Sign-in email change requested"),
    "user.email_changed": ("تغيير بريد الدخول", "Sign-in email changed"),
    "user.auto_lock_cleared": ("إزالة القفل التلقائي", "Automatic lock cleared"),
    "user.updated": ("تعديل بيانات مستخدم", "User details changed"),
    "user.deactivated": ("تعطيل مستخدم", "User deactivated"),
    "user.activated": ("تفعيل مستخدم", "User activated"),
    "user.locked": ("قفل حساب مستخدم", "User account locked"),
    "user.unlocked": ("فتح حساب مستخدم", "User account unlocked"),
    "user.password_changed": ("تغيير كلمة المرور", "Password changed"),
    "user.password_reset": ("إعادة تعيين كلمة مرور مستخدم", "User password reset"),
    "user.auto_locked": ("قفل تلقائي لحساب بعد محاولات فاشلة", "Account locked automatically after failed attempts"),
    "user.deleted": ("حذف مستخدم", "User deleted"),
    "role.created": ("إنشاء دور", "Role created"),
    "role.updated": ("تعديل دور", "Role changed"),
    "role.deleted": ("حذف دور", "Role deleted"),
    "role.permissions_updated": ("تعديل صلاحيات دور", "Role permissions changed"),
    "role_assignment.added": ("منح دور لمستخدم", "Role given to a user"),
    "role_assignment.removed": ("سحب دور من مستخدم", "Role removed from a user"),
    "organization.profile_updated": ("تعديل بيانات المنظمة", "Organization details changed"),
    "organization.logo_uploaded": ("رفع شعار المنظمة", "Organization logo uploaded"),
    "organization.logo_removed": ("إزالة شعار المنظمة", "Organization logo removed"),
    "organization.activated": ("تفعيل المنظمة", "Organization activated"),
    "organization.suspended": ("تعليق المنظمة", "Organization suspended"),
    "delegation.created": ("طلب أو إنشاء تفويض اعتماد", "Approval delegation requested or created"),
    "delegation.approved": ("الموافقة على تفويض اعتماد", "Approval delegation approved"),
    "delegation.rejected": ("رفض تفويض اعتماد", "Approval delegation rejected"),
    "delegation.revoked": ("إلغاء تفويض اعتماد", "Approval delegation revoked"),
    "announcement.sent": ("إرسال إعلان", "Announcement sent"),
    "announcement.withdrawn": ("سحب إعلان", "Announcement withdrawn"),
    "activity_log.archived": ("تنزيل أرشيف شهر من سجل النشاطات", "Activity log month archive downloaded"),
    "directory.create": ("إضافة سجل مرجعي (سائق، مركبة، شركة شحن، جهة اتصال، موقع)", "Reference record added (driver, vehicle, carrier, contact, site)"),
    "directory.update": ("تعديل سجل مرجعي (سائق، مركبة، شركة شحن، جهة اتصال، موقع)", "Reference record changed (driver, vehicle, carrier, contact, site)"),
    "activity_log.purged": ("حذف شهر من سجل النشاطات بعد انتهاء مدة حفظه", "Activity log month deleted after its retention"),
}

ENTITIES: dict[str, tuple[str, str]] = {
    "user": ("مستخدم", "User"),
    "role": ("دور", "Role"),
    "role_assignment": ("أدوار المستخدمين", "User roles"),
    "organization": ("المنظمة", "Organization"),
    "delegation": ("تفويض اعتماد", "Approval delegation"),
    "announcement": ("إعلان", "Announcement"),
    "activity_log": ("سجل النشاطات", "Activity log"),
    "shipping_drivers": ("سائق", "Driver"),
    "shipping_vehicles": ("مركبة", "Vehicle"),
    "shipping_carriers": ("شركة شحن", "Carrier"),
    "commercial_customer_contacts": ("جهة اتصال عميل", "Customer contact"),
    "commercial_customer_sites": ("موقع تسليم عميل", "Customer delivery site"),
    "procurement_supplier_contacts": ("جهة اتصال مورد", "Supplier contact"),
}


def action_label(action: str, locale: str) -> str:
    words = ACTIONS.get(action)
    return (words[0] if locale == "ar" else words[1]) if words else ("عملية إدارية" if locale == "ar" else "Administrative change")


def entity_label(entity: str, locale: str) -> str:
    words = ENTITIES.get(entity)
    return (words[0] if locale == "ar" else words[1]) if words else ("سجل" if locale == "ar" else "Record")
