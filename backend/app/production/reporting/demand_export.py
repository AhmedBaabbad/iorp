"""Customer production demands as a simple Arabic Excel sheet (PROD-EXPORT-001): one row per demand line, everything a
planner needs at a glance. Built on request from the same filters as the screen and streamed; nothing is stored.

The rows come from the demand service page by page (the same query, filters and order as the list), so the file always
matches what the screen shows, without one large query and without a cap hidden from the user (EXPORT_TOO_LARGE above
MAX_ROWS asks to narrow the filters).
"""
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.core.interfaces import product_catalog
from app.core.units import SYMBOLS
from app.production.application.demand_service import DemandError

MAX_DEMANDS = 5000
PAGE = 100

STATUS = {"draft": "مسودة", "ready_for_planning": "جاهز للتخطيط", "partially_planned": "مخطط جزئيًا", "planned": "مخطط بالكامل", "cancelled": "ملغى"}
PRIORITY = {"low": "منخفضة", "normal": "عادية", "high": "عالية", "urgent": "عاجلة"}
ORDER_STATUS = {"draft": "مسودة", "released": "معتمد", "in_progress": "قيد الإنتاج", "on_hold": "معلق", "completed": "مكتمل", "closed": "مغلق",
                "cancelled": "ملغى"}
LINE_STATE = {"ready_for_planning": "غير مخطط", "partially_planned": "مخطط جزئيًا", "planned": "مخطط بالكامل"}
SPEC_NAMES = {"width_mm": "العرض", "width": "العرض", "color": "اللون", "colour": "اللون", "thickness_mm": "السماكة", "thickness": "السماكة",
              "roll_weight_kg": "وزن الرول", "weight_kg": "الوزن", "weight": "الوزن", "length_m": "الطول", "core_mm": "الكور", "material": "الخامة"}

HEADERS = ["رقم الطلب", "العميل", "رمز العميل", "أمر البيع", "عرض السعر", "تاريخ الطلب", "التسليم المطلوب", "الأولوية", "حالة الطلب",
           "ترتيب التخطيط", "رقم البند", "المنتج", "المواصفات", "الكمية المطلوبة", "المخصص للإنتاج", "المتبقي", "الوحدة", "نسبة التخطيط %",
           "حالة البند", "أوامر الإنتاج", "ملاحظات الطلب", "ملاحظات البند", "أنشأه", "تاريخ الإنشاء"]
WIDTHS = [16, 26, 12, 16, 16, 12, 14, 10, 15, 10, 8, 20, 34, 13, 13, 12, 10, 12, 14, 34, 26, 22, 16, 17]

BLUE = PatternFill("solid", fgColor="1F3FAE")
STRIPE = PatternFill("solid", fgColor="F5F7FF")
THIN = Border(*(Side(style="thin", color="D1D5DB"),) * 4)


def _number(value):
    if value is None:
        return None
    value = Decimal(value)
    return int(value) if value == value.to_integral_value() else float(value)


def _unit(code):
    return SYMBOLS.get(code, (code,))[0] if code else ""


def _spec(spec, product=None):
    """«العرض: 5، اللون: أسود»: each property by the product's own Arabic name (master data), a choice by its label."""
    if not isinstance(spec, dict):
        return ""
    props = {p.key: p for p in (product.properties if product else ())}
    def name(key):
        return props[key].name_ar if key in props else SPEC_NAMES.get(key, key)
    def value(key, raw):
        options = {o[0]: o[1] for o in props[key].options} if key in props else {}
        return options.get(raw, raw)
    return "، ".join(f"{name(k)}: {value(k, v)}" for k, v in spec.items() if v not in (None, ""))


def demands(svc, filters, statuses, planning=False):
    """Every demand matching the screen's filters, in the screen's order, read a page at a time."""
    total, rows, page = None, [], 1
    while total is None or len(rows) < total:
        batch = filters.model_copy(update=dict(page=page, page_size=PAGE))
        customers = svc.customers.find_customers(svc.db, svc.org_id, batch.search, active_only=False) if batch.search else []
        found, total, _ = svc.repo.list(svc.org_id, batch, [c.id for c in customers], planning, statuses)
        if total > MAX_DEMANDS:
            raise DemandError("export_too_large", 422)
        if not found:
            break
        rows.extend(found)
        page += 1
    return rows


def build(svc, filters, statuses, planning=False, zone="UTC") -> bytes:
    rows = demands(svc, filters, statuses, planning)
    names = product_catalog.products(svc.db, svc.org_id, {i.product_type for d in rows for i in d.items if i.product_type})
    tz = ZoneInfo(zone)
    wb = Workbook()
    ws = wb.active
    ws.title = "طلبات العملاء"
    ws.sheet_view.rightToLeft = True
    ws["A1"] = "طلبات العملاء للإنتاج"
    ws["A1"].font = Font(bold=True, size=15, color="1F3FAE")
    ws["A2"] = f"تاريخ التصدير: {datetime.now(tz):%Y-%m-%d %H:%M} — عدد الطلبات: {len(rows)}"
    ws["A2"].font = Font(color="6B7280")
    head = 4
    for col, name in enumerate(HEADERS, 1):
        cell = ws.cell(row=head, column=col, value=name)
        cell.fill, cell.font, cell.border = BLUE, Font(bold=True, color="FFFFFF"), THIN
        cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
    ws.row_dimensions[head].height = 30
    r = head + 1
    for n, d in enumerate(rows):
        info = svc.response(d)
        for item in sorted(d.items, key=lambda i: i.line_no):
            orders = "، ".join(f"{a.production_order.production_order_number} ({ORDER_STATUS.get(str(getattr(a.production_order.status, 'value', a.production_order.status)), '')}: "
                              f"{_number(a.allocated_quantity)})" for a in item.allocations if a.status == "active")
            required, allocated = Decimal(item.required_quantity), Decimal(item.active_allocated_quantity)
            product = names.get(item.product_type)
            values = [d.demand_number, info["customer"]["name"], info["customer"]["code"], d.source_order_number or "",
                      (info["quote"] or {}).get("number") or "", d.request_date, d.requested_delivery_date,
                      PRIORITY.get(d.priority, d.priority), STATUS.get(d.status, d.status), d.planning_sequence, item.line_no,
                      product.name("ar") if product else (item.product_type or ""), _spec(item.target_spec_json, product), _number(required), _number(allocated),
                      _number(required - allocated), _unit(item.unit), round(float(allocated / required * 100), 1) if required else None,
                      LINE_STATE.get(item.planning_state, item.planning_state), orders, d.notes or "", item.notes or "", info["created_by"] or "",
                      d.created_at.astimezone(tz).replace(tzinfo=None) if d.created_at and d.created_at.tzinfo else d.created_at]
            for col, value in enumerate(values, 1):
                cell = ws.cell(row=r, column=col, value=value)
                cell.border, cell.alignment = THIN, Alignment(wrap_text=True, vertical="top")
                if n % 2:
                    cell.fill = STRIPE
                if col in (6, 7):
                    cell.number_format = "yyyy-mm-dd"
                elif col == 24:
                    cell.number_format = "yyyy-mm-dd hh:mm"
            r += 1
    for col, width in enumerate(WIDTHS, 1):
        ws.column_dimensions[get_column_letter(col)].width = width
    ws.freeze_panes = ws.cell(row=head + 1, column=3)
    if r > head + 1:
        ws.auto_filter.ref = f"A{head}:{get_column_letter(len(HEADERS))}{r - 1}"
    out = BytesIO()
    wb.save(out)
    return out.getvalue()
