"""Production permissions (PROD-RBAC-001): the single source of every production permission code.

The platform catalog (foundation/domain/permission_catalog.py) registers these, system roles
are generated from them, and routes, services and action maps refer to these names only;
no production code spells a permission string itself. Pure: no imports from other modules.
"""

MODULE = "production"

# resource -> actions, in the order the roles screen shows them.
RESOURCES: dict[str, tuple[str, ...]] = {
    "work_centers": ("read", "create", "update", "delete"),
    "shifts": ("read", "create", "update", "delete"),
    "shift_rosters": ("read", "create", "update", "manage_members"),
    "demands": ("read", "create", "update", "delete"),
    "planning": ("read", "sequence", "allocate", "release_allocation"),
    "production_orders": ("read", "update", "manage_items", "create", "release", "start", "hold", "complete", "close", "cancel"),
    "runs": ("read", "create", "update", "start", "pause", "complete", "cancel", "manage_members"),
    "results": ("read", "create", "update", "delete", "correct"),
    "downtime_events": ("read", "create", "update", "delete", "close"),
    "waste_records": ("read", "create", "update", "delete"),
}


def code(resource: str, action: str) -> str:
    assert action in RESOURCES[resource], f"{resource}:{action} is not a production permission"
    return f"{MODULE}:{resource}:{action}"


ALL: tuple[str, ...] = tuple(code(resource, action) for resource, actions in RESOURCES.items() for action in actions)

WORK_CENTERS_READ, WORK_CENTERS_CREATE, WORK_CENTERS_UPDATE, WORK_CENTERS_DELETE = (code("work_centers", a) for a in RESOURCES["work_centers"])
SHIFTS_READ, SHIFTS_CREATE, SHIFTS_UPDATE, SHIFTS_DELETE = (code("shifts", a) for a in RESOURCES["shifts"])
ROSTERS_READ, ROSTERS_CREATE, ROSTERS_UPDATE, ROSTERS_MANAGE_MEMBERS = (code("shift_rosters", a) for a in RESOURCES["shift_rosters"])
DEMANDS_READ, DEMANDS_CREATE, DEMANDS_UPDATE, DEMANDS_DELETE = (code("demands", a) for a in RESOURCES["demands"])
PLANNING_READ, PLANNING_SEQUENCE, PLANNING_ALLOCATE, PLANNING_RELEASE_ALLOCATION = (code("planning", a) for a in RESOURCES["planning"])
(ORDERS_READ, ORDERS_UPDATE, ORDERS_MANAGE_ITEMS, ORDERS_CREATE, ORDERS_RELEASE, ORDERS_START, ORDERS_HOLD,
 ORDERS_COMPLETE, ORDERS_CLOSE, ORDERS_CANCEL) = (code("production_orders", a) for a in RESOURCES["production_orders"])
(RUNS_READ, RUNS_CREATE, RUNS_UPDATE, RUNS_START, RUNS_PAUSE, RUNS_COMPLETE, RUNS_CANCEL,
 RUNS_MANAGE_MEMBERS) = (code("runs", a) for a in RESOURCES["runs"])
RESULTS_READ, RESULTS_CREATE, RESULTS_UPDATE, RESULTS_DELETE, RESULTS_CORRECT = (code("results", a) for a in RESOURCES["results"])
DOWNTIME_READ, DOWNTIME_CREATE, DOWNTIME_UPDATE, DOWNTIME_DELETE, DOWNTIME_CLOSE = (code("downtime_events", a) for a in RESOURCES["downtime_events"])
WASTE_READ, WASTE_CREATE, WASTE_UPDATE, WASTE_DELETE = (code("waste_records", a) for a in RESOURCES["waste_records"])

# ---- action -> permission maps (one place per resource) --------------------------------------

# Production order lifecycle actions (domain/order_lifecycle.py). Reverting to draft undoes a
# release, so it needs the release permission; resuming a held order is starting it again.
ORDER_TRANSITIONS: dict[str, str] = {
    "release": ORDERS_RELEASE, "return_to_draft": ORDERS_RELEASE, "start": ORDERS_START, "hold": ORDERS_HOLD,
    "resume": ORDERS_START, "complete": ORDERS_COMPLETE, "close": ORDERS_CLOSE, "cancel": ORDERS_CANCEL,
}
# Production run lifecycle (application/execution_service.py). "start" also resumes a paused run.
RUN_TRANSITIONS: dict[str, str] = {"start": RUNS_START, "pause": RUNS_PAUSE, "complete": RUNS_COMPLETE, "cancel": RUNS_CANCEL}
# Final result entries: create/edit/delete while the order is completed, corrections once closed.
RESULT_ACTIONS: dict[str, str] = {"create": RESULTS_CREATE, "edit": RESULTS_UPDATE, "delete": RESULTS_DELETE, "correct": RESULTS_CORRECT}
DOWNTIME_ACTIONS: dict[str, str] = {"create": DOWNTIME_CREATE, "edit": DOWNTIME_UPDATE, "delete": DOWNTIME_DELETE, "close": DOWNTIME_CLOSE}
WASTE_ACTIONS: dict[str, str] = {"create": WASTE_CREATE, "edit": WASTE_UPDATE, "delete": WASTE_DELETE}

# Production report permissions (registered by production/reporting/definitions.py).
REPORT_ORDER_FULL = "reports:production:order_full"
REPORT_ORDERS_SUMMARY = "reports:production:orders_summary"
REPORT_RESULTS_ANALYSIS = "reports:production:results_analysis"
REPORT_SHIFT_WORKFORCE = "reports:production:shift_workforce"
REPORTS: tuple[str, ...] = (REPORT_ORDER_FULL, REPORT_ORDERS_SUMMARY, REPORT_RESULTS_ANALYSIS, REPORT_SHIFT_WORKFORCE)

# Labels where "<action> <resource>" reads badly; everything else is composed by the catalog.
LABELS: dict[str, tuple[str, str]] = {
    ORDERS_MANAGE_ITEMS: ("Manage Production Order Items", "إدارة بنود أوامر الإنتاج"),
    ORDERS_START: ("Start or Resume Production Orders", "بدء أو استئناف أوامر الإنتاج"),
    ORDERS_HOLD: ("Hold Production Orders", "تعليق أوامر الإنتاج"),
    ORDERS_UPDATE: ("Update Production Order Data", "تعديل بيانات أوامر الإنتاج"),
    RUNS_START: ("Start or Resume Production Runs", "بدء أو استئناف تشغيل الإنتاج"),
    RUNS_PAUSE: ("Pause Production Runs", "إيقاف تشغيل الإنتاج مؤقتاً"),
    RUNS_MANAGE_MEMBERS: ("Manage Production Run Teams", "إدارة فريق تشغيل الإنتاج"),
    ROSTERS_MANAGE_MEMBERS: ("Manage Shift Roster Members", "إدارة أعضاء فرق الورديات"),
    RESULTS_CORRECT: ("Correct Closed Production Results", "تصحيح نتائج الأوامر المغلقة"),
    DOWNTIME_CLOSE: ("End Open Downtime Events", "إنهاء أحداث التوقف المفتوحة"),
}
