"""PROD-EXPORT-001: customer production demands exported as a simple Arabic Excel sheet, from the screen's filters."""
from io import BytesIO

from openpyxl import load_workbook

from app.production.reporting import demand_export
from tests.test_production_allocation_lifecycle import other_org_demand
from tests.test_production_order_lines import ROOT, env, items, spec  # noqa: F401  (env is a fixture)

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def sheet(response):
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == XLSX and "attachment" in response.headers["content-disposition"]
    ws = load_workbook(BytesIO(response.content)).active
    rows = [r for r in ws.iter_rows(min_row=5, values_only=True) if any(v not in (None, "") for v in r)]
    return ws, [dict(zip(demand_export.HEADERS, r)) for r in rows]


def test_one_arabic_row_per_demand_line_with_its_planning(env):
    d = env.demand(spec(10, "red"), spec(12))
    po = env.order((items(d)[0], "400"))
    other_org_demand(env.db)
    ws, rows = sheet(env.client.get(f"{ROOT}/demands/export.xlsx"))
    assert ws.sheet_view.rightToLeft is True and ws.title == "طلبات العملاء"
    assert [c.value for c in ws[4]] == demand_export.HEADERS
    mine = [r for r in rows if r["رقم الطلب"] == d["demand_number"]]
    assert [r["رقم البند"] for r in mine] == [1, 2]
    first, second = mine
    assert first["العميل"] == "Lines Customer" and first["حالة الطلب"] == "مخطط جزئيًا" and first["الأولوية"] == "عادية"
    assert (first["الكمية المطلوبة"], first["المخصص للإنتاج"], first["المتبقي"], first["الوحدة"]) == (1000, 400, 600, "كجم")
    assert first["نسبة التخطيط %"] == 40 and first["حالة البند"] == "مخطط جزئيًا"
    assert first["المواصفات"] == "العرض: 10، اللون: red"
    assert first["أوامر الإنتاج"] == f'{po["production_order_number"]} (مسودة: 400)'
    assert second["المخصص للإنتاج"] == 0 and second["حالة البند"] == "غير مخطط" and second["أوامر الإنتاج"] in ("", None)
    assert all(r["رقم الطلب"] != "PD-OTHER" for r in rows)  # another organization's demand never appears


def test_the_file_follows_the_screens_filters_across_pages(env, monkeypatch):
    monkeypatch.setattr(demand_export, "PAGE", 2)  # several pages read for one file
    made = [env.demand(spec(10)) for _ in range(5)]
    ready = [r["رقم الطلب"] for r in sheet(env.client.get(f"{ROOT}/demands/export.xlsx", params={"statuses": "ready_for_planning"}))[1]]
    assert sorted(ready) == sorted(d["demand_number"] for d in made)
    one = sheet(env.client.get(f"{ROOT}/demands/export.xlsx", params={"search": made[3]["demand_number"]}))[1]
    assert [r["رقم الطلب"] for r in one] == [made[3]["demand_number"]]
    assert sheet(env.client.get(f"{ROOT}/demands/export.xlsx", params={"statuses": "cancelled"}))[1] == []


def test_the_planning_queue_exports_what_it_shows(env):
    open_demand = env.demand(spec(10))
    full = env.demand(spec(10), quantity="100")
    env.order((items(full)[0], "100"))
    queue = [r["رقم الطلب"] for r in sheet(env.client.get(f"{ROOT}/planning/demands/export.xlsx"))[1]]
    assert open_demand["demand_number"] in queue and full["demand_number"] not in queue  # fully planned leaves the active queue


def test_too_many_demands_ask_for_narrower_filters(env, monkeypatch):
    monkeypatch.setattr(demand_export, "MAX_DEMANDS", 1)
    env.demand(spec(10)); env.demand(spec(10))
    r = env.client.get(f"{ROOT}/demands/export.xlsx")
    assert r.status_code == 422 and r.json()["detail"]["code"] == "export_too_large"


def test_export_needs_the_read_permission(env):
    env.ctx.auth_user.permissions = set()
    assert env.client.get(f"{ROOT}/demands/export.xlsx").status_code == 403
    assert env.client.get(f"{ROOT}/planning/demands/export.xlsx").status_code == 403
