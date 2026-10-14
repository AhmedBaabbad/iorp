"""How complaint values and decisions read in Arabic and English (reports; the screens use the locale files).

Each history entry is worded from its stored facts: nothing is shown as a code, an id or a symbol.
"""
from datetime import date

WORDS: dict[str, tuple[str, str]] = {
    # statuses
    "new": ("جديدة", "New"), "assessment": ("قيد التقييم", "Under assessment"), "processing": ("قيد المعالجة", "In processing"),
    "pending_closure": ("بانتظار اعتماد الإغلاق", "Awaiting closure approval"), "closed": ("مغلقة", "Closed"), "cancelled": ("ملغاة", "Cancelled"),
    # findings
    "pending": ("لم يكتمل التحقق", "Not yet verified"), "verified": ("مثبتة", "Verified"), "not_verified": ("غير مثبتة", "Not verified"),
    "inconclusive": ("غير حاسمة", "Inconclusive"),
    # departments and categories
    "commercial": ("المبيعات وخدمة العملاء", "Sales and customer service"), "quality": ("الجودة", "Quality"), "shipping": ("الشحن والتسليم", "Shipping and delivery"),
    "production": ("الإنتاج", "Production"), "delivery": ("التسليم", "Delivery"), "quantity": ("الكمية", "Quantity"), "packaging": ("التغليف", "Packaging"),
    "service": ("الخدمة", "Service"), "other": ("أخرى", "Other"),
    # priorities and channels
    "low": ("منخفضة", "Low"), "medium": ("متوسطة", "Medium"), "high": ("عالية", "High"), "critical": ("حرجة", "Critical"),
    "phone": ("الهاتف", "Phone"), "email": ("البريد الإلكتروني", "E-mail"), "visit": ("زيارة", "Visit"), "message": ("رسالة", "Message"),
    # references
    "order": ("أمر بيع", "Sales order"), "sample": ("عينة", "Sample"), "shipment": ("شحنة", "Shipment"), "return": ("مرتجع", "Return"),
    "production_order": ("أمر إنتاج", "Production order"), "quality_check": ("فحص جودة", "Quality inspection"),
    "ncr": ("تقرير عدم مطابقة", "Non-conformance report"), "manual": ("مُدخلة يدويًا", "Entered by hand"),
    # fields
    "investigation": ("التحقيق", "Investigation"), "containment": ("الاحتواء", "Containment"), "waiting_reason": ("سبب الانتظار", "Waiting reason"),
    "resolution": ("الحل", "Resolution"), "implementation_evidence": ("دليل التنفيذ", "Implementation evidence"),
    "customer_response": ("موقف العميل", "Customer response"),
}

ACTIONS: dict[str, tuple[str, str]] = {
    "created": ("تسجيل الشكوى", "Complaint registered"), "assign": ("إسناد المسؤولية", "Responsibility assigned"),
    "investigate": ("تحديث التحقيق", "Investigation updated"), "resolve": ("تسجيل الحل", "Resolution recorded"),
    "items_updated": ("تعديل بنود المنتجات", "Product lines edited"), "note": ("متابعة داخلية", "Internal follow-up"), "response": ("تواصل مع العميل", "Contact with the customer"),
    "linked": ("ربط مرجع", "Reference linked"), "attachment": ("إرفاق دليل", "Evidence attached"), "refer_quality": ("إحالة إلى الجودة", "Referred to quality"),
    "assess": ("بدء التقييم", "Assessment started"), "start": ("بدء المعالجة", "Processing started"), "request_close": ("طلب الإغلاق", "Closure requested"),
    "approve_close": ("اعتماد الإغلاق", "Closure approved"), "return": ("إعادة للمعالجة", "Returned for processing"), "reopen": ("إعادة الفتح", "Reopened"),
    "cancel": ("إلغاء الشكوى", "Complaint cancelled"),
}


def word(key, lang):
    pair = WORDS.get(key)
    return (pair[0] if lang == "ar" else pair[1]) if pair else (key or "")


def action_title(action, lang):
    pair = ACTIONS.get(action)
    return (pair[0] if lang == "ar" else pair[1]) if pair else action


def _date(value):
    try:
        return date.fromisoformat(str(value)).strftime("%d/%m/%Y")
    except ValueError:
        return str(value)


def describe(action, details, notes, lang):
    """The entry as sentences in `lang`: its facts by name, then what the person wrote."""
    ar = lang == "ar"
    d = details or {}
    lines = []
    if action == "assign":
        lines.append((f"المسؤول: {d.get('owner_name') or '—'}" if ar else f"Owner: {d.get('owner_name') or '—'}"))
        lines.append((f"القسم المعالج: {word(d.get('department'), lang)}" if ar else f"Handling department: {word(d.get('department'), lang)}"))
        if d.get("due_date"):
            lines.append((f"موعد الحل: {_date(d['due_date'])}" if ar else f"Resolution due: {_date(d['due_date'])}"))
        if d.get("previous_owner_name") and d.get("previous_owner_name") != d.get("owner_name"):
            lines.append((f"المسؤول السابق: {d['previous_owner_name']}" if ar else f"Previous owner: {d['previous_owner_name']}"))
        if d.get("from_status"):
            lines.append((f"من «{word(d['from_status'], lang)}» إلى «{word(d['to_status'], lang)}»" if ar
                          else f"From «{word(d['from_status'], lang)}» to «{word(d['to_status'], lang)}»"))
    elif action in ("assess", "start", "request_close", "approve_close", "return", "reopen", "cancel") and d.get("from_status"):
        lines.append((f"من «{word(d['from_status'], lang)}» إلى «{word(d['to_status'], lang)}»" if ar
                      else f"From «{word(d['from_status'], lang)}» to «{word(d['to_status'], lang)}»"))
    elif action == "created":
        bits = [word(d[k], lang) for k in ("category", "priority", "channel") if d.get(k)]
        if bits:
            lines.append(("النوع والأولوية والقناة: " if ar else "Category, priority, channel: ") + "، ".join(bits))
    elif action in ("investigate", "resolve"):
        if d.get("finding"):
            lines.append((f"نتيجة التحقق: {word(d['finding'], lang)}" if ar else f"Finding: {word(d['finding'], lang)}"))
        for key, value in (d.get("fields") or {}).items():
            if value:
                lines.append(f"{word(key, lang)}: {value}")
        for item in d.get("items") or []:
            measured = item.get("measured" if ar else "measured_en") or {}
            text = "، ".join(f"{k}: {v}" for k, v in measured.items())
            confirmed = item.get("confirmed_quantity")
            lines.append(f"{item.get('product')}: " + "؛ ".join(x for x in (
                text and ((f"القياسات: {text}") if ar else f"Measured: {text}"),
                confirmed and ((f"الكمية المثبت تأثرها: {confirmed}") if ar else f"Confirmed affected: {confirmed}")) if x))
        for key, value in (d.get("previous") or {}).items():
            lines.append((f"القيمة السابقة لـ{word(key, lang)}: {value}" if ar else f"Previous {word(key, lang).lower()}: {value}"))
    elif action == "linked":
        lines.append(f"{word(d.get('kind'), lang)}: {d.get('label', '')}")
    elif action == "refer_quality" and d.get("ncr_number"):
        lines.append((f"فُتح تقرير عدم المطابقة رقم {d['ncr_number']}" if ar else f"Non-conformance report {d['ncr_number']} opened"))
    elif action == "attachment" and d.get("filename"):
        lines.append((f"الملف: {d['filename']}" if ar else f"File: {d['filename']}"))
    elif action == "items_updated":
        lines.append((f"عدد البنود: {d.get('lines', 0)}" if ar else f"Lines: {d.get('lines', 0)}"))
    if notes:
        label = {"assign": ("سبب الإسناد", "Reason"), "note": ("المتابعة", "Follow-up"), "response": ("ما أُرسل للعميل", "Sent to the customer"),
                 "refer_quality": ("ملاحظة الإحالة", "Referral note")}.get(action, ("السبب", "Reason"))
        lines.append(f"{label[0] if ar else label[1]}: {notes}")
    return "\n".join(lines)
