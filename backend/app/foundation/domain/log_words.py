"""The words of the organization's logs (ORG-AUDIT-003), in Arabic and English: kinds of record, verbs, detail fields and
values. The screens carry the same words (frontend locales logs.json; a test keeps both equal); the archive files use these."""

ENTITIES: dict[str, tuple[str, str]] = {
    'customer': ('عميل', 'Customer'),
    'followup': ('متابعة', 'Follow-up'),
    'interaction': ('تواصل مع عميل', 'Customer interaction'),
    'goods_receipt': ('استلام مواد', 'Goods receipt'),
    'material': ('مادة', 'Material'),
    'supplier': ('مورد', 'Supplier'),
    'purchase_order': ('أمر شراء', 'Purchase order'),
    'list_item': ('بند في قائمة مرجعية', 'Reference list item'),
    'product': ('منتج', 'Product'),
    'ncr_report': ('تقرير عدم مطابقة', 'Non-conformance report'),
    'organization': ('المنظمة', 'Organization'),
    'production_allocation': ('تخصيص إنتاج', 'Production allocation'),
    'production_downtime': ('توقف إنتاج', 'Production downtime'),
    'production_downtime_event': ('توقف إنتاج', 'Production downtime'),
    'production_order': ('أمر إنتاج', 'Production order'),
    'production_order_item': ('بند أمر إنتاج', 'Production order line'),
    'production_result': ('نتيجة إنتاج', 'Production result'),
    'production_result_entry': ('نتيجة إنتاج', 'Production result'),
    'production_waste': ('سجل هالك', 'Scrap record'),
    'production_waste_record': ('سجل هالك', 'Scrap record'),
    'production_demand': ('طلب إنتاج', 'Production demand'),
    'production_run': ('تشغيل إنتاج', 'Production run'),
    'quality_certificate': ('شهادة تحليل', 'Certificate of analysis'),
    'quality_check': ('فحص جودة', 'Quality check'),
    'quality_defect': ('عيب جودة', 'Quality defect'),
    'quality_rejection': ('حالة رفض', 'Rejection'),
    'quality_specification': ('مواصفة منتج', 'Product specification'),
    'return': ('مرتجع عميل', 'Customer return'),
    'shipment_return': ('مرتجع عميل', 'Customer return'),
    'shipment': ('شحنة', 'Shipment'),
    'shift': ('وردية', 'Shift'),
    'shift_roster': ('فريق وردية', 'Shift roster'),
    'work_center': ('مركز عمل', 'Work centre'),
    'workforce_member': ('عضو في القوى العاملة', 'Workforce member'),
    'user': ('مستخدم', 'User'),
    'role': ('دور', 'Role'),
    'role_assignment': ('أدوار مستخدم', 'User roles'),
    'delegation': ('تفويض اعتماد', 'Approval delegation'),
    'announcement': ('إعلان', 'Announcement'),
    'complaint': ('شكوى عميل', 'Customer complaint'),
    'quote': ('عرض سعر', 'Quotation'),
    'sample': ('عينة', 'Sample'),
    'order': ('أمر بيع', 'Sales order'),
    'sales_order': ('أمر بيع', 'Sales order'),
    'platform_account': ('حساب منصة', 'Platform account'),
    'event': ('سجل', 'Record'),
}

VERBS: dict[str, tuple[str, str]] = {
    'created': ('إنشاء', 'created'),
    'create': ('إنشاء', 'created'),
    'updated': ('تعديل', 'updated'),
    'update': ('تعديل', 'updated'),
    'deleted': ('حذف', 'deleted'),
    'cancelled': ('إلغاء', 'cancelled'),
    'cancel': ('إلغاء', 'cancelled'),
    'completed': ('إكمال', 'completed'),
    'reopened': ('إعادة فتح', 'reopened'),
    'received': ('استلام', 'received'),
    'approved': ('اعتماد', 'approved'),
    'approve': ('اعتماد', 'approved'),
    'rejected': ('رفض', 'rejected'),
    'issued': ('إصدار', 'issued'),
    'revoked': ('إلغاء', 'revoked'),
    'closed': ('إغلاق', 'closed'),
    'close': ('إغلاق', 'closed'),
    'started': ('بدء', 'started'),
    'decided': ('اتخاذ قرار', 'decided'),
    'executed': ('تنفيذ قرار', 'decision carried out'),
    'activated': ('تفعيل', 'activated'),
    'deactivated': ('تعطيل', 'deactivated'),
    'released': ('تحرير', 'released'),
    'status_changed': ('تغيير حالة', 'status changed'),
    'allocation_added': ('إضافة تخصيص إلى', 'allocation added'),
    'allocation_changed': ('تعديل تخصيص', 'allocation changed'),
    'action_added': ('إضافة إجراء تصحيحي إلى', 'corrective action added'),
    'action_updated': ('تعديل إجراء تصحيحي في', 'corrective action changed'),
    'action_done': ('إنجاز إجراء تصحيحي في', 'corrective action done'),
    'action_cancelled': ('إلغاء إجراء تصحيحي في', 'corrective action cancelled'),
    'item_added': ('إضافة بند إلى', 'line added'),
    'item_updated': ('تعديل بند في', 'line changed'),
    'item_removed': ('حذف بند من', 'line removed'),
    'contain': ('تسجيل احتواء', 'containment recorded'),
    'investigate': ('تسجيل السبب الجذري لـ', 'root cause recorded'),
    'submit': ('إرسال للتحقق', 'submitted for verification'),
    'verify': ('التحقق من', 'verified'),
    'effectiveness_review': ('مراجعة فعالية', 'effectiveness reviewed'),
    'member_added': ('إضافة عضو إلى', 'member added'),
    'member_removed': ('إزالة عضو من', 'member removed'),
    'delivered': ('تسليم', 'delivered'),
    'partially_delivered': ('تسليم جزئي لـ', 'partially delivered'),
    'dispatched': ('إخراج', 'dispatched'),
    'ready': ('تجهيز', 'made ready'),
    'requested': ('تسجيل', 'registered'),
    'returned': ('إرجاع', 'returned'),
    'rescheduled': ('إعادة جدولة', 'rescheduled'),
    'user_linked': ('ربط مستخدم بـ', 'user linked'),
    'user_unlinked': ('فك ربط مستخدم عن', 'user unlinked'),
    'legacy_mapped': ('ربط قيمة قديمة بـ', 'old value mapped'),
    'owner_changed': ('تغيير المسؤول عن', 'owner changed'),
    'bulk_reassigned': ('إعادة إسناد جماعي لـ', 'reassigned in bulk'),
    'corrected': ('تصحيح', 'corrected'),
    'send': ('إرسال', 'sent'),
    'sent': ('إرسال', 'sent'),
    'conditional': ('اعتماد مشروط لـ', 'conditionally approved'),
    'blocked': ('إيقاف', 'blocked'),
    'pending': ('إعادة إلى الانتظار لـ', 'set back to pending'),
    'logo_uploaded': ('رفع شعار', 'logo uploaded'),
    'logo_removed': ('إزالة شعار', 'logo removed'),
    'profile_updated': ('تعديل بيانات', 'details changed'),
    'permissions_updated': ('تعديل صلاحيات', 'permissions changed'),
    'password_reset': ('إعادة تعيين كلمة مرور', 'password reset'),
    'password_changed': ('تغيير كلمة مرور', 'password changed'),
    'locked': ('قفل', 'locked'),
    'unlocked': ('فتح', 'unlocked'),
    'auto_locked': ('قفل تلقائي لـ', 'locked automatically'),
    'added': ('إضافة', 'added'),
    'removed': ('إزالة', 'removed'),
    'suspended': ('تعليق', 'suspended'),
    'withdrawn': ('سحب', 'withdrawn'),
    'archived': ('أرشفة', 'archived'),
    'root_password_reset': ('إعادة تعيين كلمة مرور المدير الرئيسي لـ', 'root password reset'),
    'release': ('اعتماد وإطلاق', 'released'),
    'start': ('بدء تنفيذ', 'started'),
    'hold': ('إيقاف مؤقت لـ', 'put on hold'),
    'resume': ('استئناف', 'resumed'),
    'complete': ('إكمال', 'completed'),
    'pause': ('إيقاف مؤقت لـ', 'paused'),
    'archived_month': ('أرشفة', 'archived'),
}

FIELDS: dict[str, tuple[str, str]] = {
    'from_status': ('من حالة', 'From'),
    'to_status': ('إلى حالة', 'To'),
    'status': ('الحالة', 'Status'),
    'reason': ('السبب', 'Reason'),
    'role_name': ('الدور', 'Role'),
    'role_code': ('رمز الدور', 'Role code'),
    'user_name': ('المستخدم', 'User'),
    'permission': ('الصلاحية', 'Permission'),
    'operation': ('العملية', 'Operation'),
    'scope': ('النطاق', 'Scope'),
    'code': ('الرمز', 'Code'),
    'name': ('الاسم', 'Name'),
    'full_name': ('الاسم الكامل', 'Full name'),
    'email': ('البريد الإلكتروني', 'Email'),
    'phone': ('الهاتف', 'Phone'),
    'preferred_locale': ('لغة الواجهة', 'Language'),
    'timezone': ('المنطقة الزمنية', 'Time zone'),
    'default_locale': ('اللغة الافتراضية', 'Default language'),
    'industry_type': ('نوع النشاط', 'Industry'),
    'delegator': ('نيابةً عن', 'On behalf of'),
    'delegate': ('المفوَّض إليه', 'Delegated to'),
    'effective_from': ('من', 'From'),
    'effective_to': ('إلى', 'To'),
    'approval': ('الموافقة', 'Approval'),
    'severity': ('الأهمية', 'Importance'),
    'requires_ack': ('يتطلب تأكيد الاطلاع', 'Requires acknowledgement'),
    'audience': ('أُرسل إلى', 'Sent to'),
    'audience_label': ('الدور المستهدف', 'Role'),
    'recipients': ('عدد المستلمين', 'Recipients'),
    'action': ('الإجراء', 'Action'),
    'trigger': ('طريقة التغيير', 'Triggered by'),
    'released_allocations': ('التخصيصات المحرّرة', 'Allocations released'),
    'zero_output': ('بلا إنتاج', 'No output'),
    'disposition': ('القرار', 'Disposition'),
    'defects': ('العيوب', 'Defects'),
    'sessions_invalidated': ('إنهاء الجلسات المفتوحة', 'Open sessions ended'),
    'reset_by_admin': ('بواسطة المسؤول', 'By an administrator'),
    'password_changed': ('تغيير كلمة المرور', 'Password changed'),
    'kind': ('النوع', 'Kind'),
    'review_days': ('مراجعة الفعالية بعد (أيام)', 'Effectiveness review after (days)'),
    'effective': ('فعّال', 'Effective'),
    'lines': ('عدد البنود', 'Lines'),
    'channel': ('قناة الورود', 'Channel'),
    'category': ('التصنيف', 'Category'),
    'priority': ('الأولوية', 'Priority'),
    'title': ('العنوان', 'Title'),
    'quantity': ('الكمية', 'Quantity'),
    'unit': ('الوحدة', 'Unit'),
    'outcome': ('النتيجة', 'Outcome'),
    'error_code': ('رمز الخطأ', 'Error code'),
    'field': ('الحقل', 'Field'),
    'concession_approved_by': ('اعتماد التجاوز من', 'Concession approved by'),
    'previous_lines': ('البنود السابقة', 'Previous lines'),
    'is_active': ('نشط', 'Active'),
    'description': ('الوصف', 'Description'),
    'notes': ('الملاحظات', 'Notes'),
    'ip_address': ('عنوان الجهاز (IP)', 'IP address'),
    'user_agent': ('المتصفح', 'Browser'),
    'failed_login_attempts': ('عدد المحاولات الفاشلة المتتالية', 'Failed attempts in a row'),
    'auto_locked_until': ('مقفل حتى', 'Locked until'),
    'month': ('الشهر', 'Month'),
    'rows': ('عدد الأسطر', 'Rows'),
    'automatic': ('تلقائيًا', 'Automatically'),
}

VALUES: dict[str, tuple[str, str]] = {
    'added': ('أُضيفت', 'added'),
    'removed': ('سُحبت', 'removed'),
    'scope_changed': ('تغيّر نطاقها', 'scope changed'),
    'own': ('سجلاته فقط', 'own records'),
    'team': ('سجلات فريقه', 'team records'),
    'organization': ('كل المنظمة', 'whole organization'),
    'true': ('نعم', 'yes'),
    'false': ('لا', 'no'),
    'ar': ('العربية', 'Arabic'),
    'en': ('الإنجليزية', 'English'),
    'manual': ('يدويًا', 'manually'),
    'activity': ('تلقائيًا من النشاط', 'automatically from activity'),
    'automatic': ('تلقائيًا', 'automatically'),
    'draft': ('مسودة', 'draft'),
    'released': ('معتمد', 'released'),
    'in_progress': ('قيد التنفيذ', 'in progress'),
    'on_hold': ('موقوف مؤقتًا', 'on hold'),
    'completed': ('مكتمل', 'completed'),
    'closed': ('مغلق', 'closed'),
    'cancelled': ('ملغى', 'cancelled'),
    'active': ('نشط', 'active'),
    'inactive': ('غير نشط', 'inactive'),
    'locked': ('مقفل', 'locked'),
    'approved': ('معتمد', 'approved'),
    'pending': ('بانتظار', 'pending'),
    'rejected': ('مرفوض', 'rejected'),
    'awaiting_manager': ('بانتظار المدير', 'awaiting a manager'),
    'awaiting_holder': ('بانتظار صاحب الاعتماد', 'awaiting the holder'),
    'info': ('عادي', 'normal'),
    'important': ('مهم', 'important'),
    'urgent': ('عاجل', 'urgent'),
    'users': ('مستخدمون محددون', 'named users'),
    'role': ('أصحاب دور', "a role's members"),
    'everyone': ('كل المنظمة', 'everyone'),
    'success': ('نجاح', 'success'),
    'failure': ('فشل', 'failure'),
    'denied': ('مرفوض', 'denied'),
    'invalid_credentials': ('بيانات دخول غير صحيحة', 'wrong email or password'),
    'account_locked': ('الحساب مقفل', 'account locked'),
    'account_inactive': ('الحساب غير نشط', 'account inactive'),
    'password_reset': ('إعادة تعيين كلمة المرور', 'password reset'),
    'password_change': ('تغيير كلمة المرور', 'password change'),
    'logout': ('تسجيل الخروج', 'sign-out'),
}

LISTS: dict[str, tuple[str, str]] = {
    'city': ('المدن', 'cities'),
    'country': ('الدول', 'countries'),
    'sector': ('القطاعات', 'sectors'),
    'opportunity_source': ('مصادر الفرص', 'opportunity sources'),
}

# Operations whose composed words read badly; said in full.
EXACT: dict[str, tuple[str, str]] = {
    "goods_receipt.received": ("تأكيد استلام مواد", "Goods receipt confirmed"),
    "ncr_report.submit": ("إرسال تقرير عدم مطابقة للتحقق", "Non-conformance report submitted for verification"),
    "ncr_report.contain": ("تسجيل الاحتواء في تقرير عدم مطابقة", "Non-conformance containment recorded"),
    "ncr_report.investigate": ("تسجيل السبب الجذري في تقرير عدم مطابقة", "Non-conformance root cause recorded"),
    "return.requested": ("تسجيل مرتجع عميل", "Customer return registered"),
    "production_order.allocation_added": ("إضافة كمية مخصصة إلى أمر إنتاج", "Quantity allocated to a production order"),
}

PRODUCTION_STATUS_CHANGED = "production_order.status_changed"


def _pick(words: dict, key: str, locale: str) -> str | None:
    found = words.get(key)
    return None if found is None else found[0] if locale == "ar" else found[1]


def describe(action: str, details, locale: str) -> str:
    """An operation as people read it — the same rule as the screens (features/logs/log-words.tsx)."""
    if action == PRODUCTION_STATUS_CHANGED and isinstance(details, dict) and details.get("action") in VERBS:
        action = f"production_order.{details['action']}"
    if action in EXACT:
        return _pick(EXACT, action, locale)
    entity, _, rest = action.removeprefix("tenant.").partition(".")
    verb, _, listed = rest.partition(".")
    entity_words, verb_words = _pick(ENTITIES, entity, locale), _pick(VERBS, verb, locale)
    if not entity_words and not verb_words:
        return "عملية في النظام" if locale == "ar" else "An operation in the system"
    entity_words = entity_words or ("سجل" if locale == "ar" else "Record")
    verb_words = verb_words or ("تعديل" if locale == "ar" else "changed")
    text = (f"{verb_words} {entity_words}" if locale == "ar" else f"{entity_words} {verb_words}").replace("لـ ", "ل")
    if listed:
        text += f" ({_pick(LISTS, listed, locale) or listed.replace('_', ' ')})"
    return text


def detail_text(details, locale: str) -> str:
    """Details as "label: value" pairs, without ids."""
    if not isinstance(details, dict):
        return "" if details is None else str(details)
    parts = []
    for key, value in details.items():
        if key == "id" or key.endswith("_id") or key in ("performed_by",):
            continue
        label = _pick(FIELDS, key, locale) or key.replace("_", " ")
        if isinstance(value, dict) and ("before" in value or "after" in value):
            shown = f"{_value(value.get('before'), locale)} → {_value(value.get('after'), locale)}"
        else:
            shown = _value(value, locale)
        parts.append(f"{label}: {shown}")
    return " · ".join(parts)


def _value(value, locale: str) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, bool):
        return ("نعم" if value else "لا") if locale == "ar" else ("yes" if value else "no")
    return _pick(VALUES, str(value), locale) or str(value)
