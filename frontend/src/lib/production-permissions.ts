// Production permission codes (PROD-RBAC-001), mirroring backend/app/production/domain/permissions.py.
// Screens refer to these names only; tests/production-permissions.test.mjs keeps both lists identical.
// The server enforces every permission; the screens use them only to hide what a user cannot do.

const code = <R extends string, A extends string>(resource: R, action: A) => `production:${resource}:${action}` as const;

export const P = {
  WORK_CENTERS_READ: code("work_centers", "read"),
  WORK_CENTERS_CREATE: code("work_centers", "create"),
  WORK_CENTERS_UPDATE: code("work_centers", "update"),
  WORK_CENTERS_DELETE: code("work_centers", "delete"),
  SHIFTS_READ: code("shifts", "read"),
  SHIFTS_CREATE: code("shifts", "create"),
  SHIFTS_UPDATE: code("shifts", "update"),
  SHIFTS_DELETE: code("shifts", "delete"),
  ROSTERS_READ: code("shift_rosters", "read"),
  ROSTERS_CREATE: code("shift_rosters", "create"),
  ROSTERS_UPDATE: code("shift_rosters", "update"),
  ROSTERS_MANAGE_MEMBERS: code("shift_rosters", "manage_members"),
  DEMANDS_READ: code("demands", "read"),
  DEMANDS_CREATE: code("demands", "create"),
  DEMANDS_UPDATE: code("demands", "update"),
  DEMANDS_DELETE: code("demands", "delete"),
  PLANNING_READ: code("planning", "read"),
  PLANNING_SEQUENCE: code("planning", "sequence"),
  PLANNING_ALLOCATE: code("planning", "allocate"),
  PLANNING_RELEASE_ALLOCATION: code("planning", "release_allocation"),
  ORDERS_READ: code("production_orders", "read"),
  ORDERS_UPDATE: code("production_orders", "update"),
  ORDERS_MANAGE_ITEMS: code("production_orders", "manage_items"),
  ORDERS_CREATE: code("production_orders", "create"),
  ORDERS_RELEASE: code("production_orders", "release"),
  ORDERS_START: code("production_orders", "start"),
  ORDERS_HOLD: code("production_orders", "hold"),
  ORDERS_COMPLETE: code("production_orders", "complete"),
  ORDERS_CLOSE: code("production_orders", "close"),
  ORDERS_CANCEL: code("production_orders", "cancel"),
  RUNS_READ: code("runs", "read"),
  RUNS_CREATE: code("runs", "create"),
  RUNS_UPDATE: code("runs", "update"),
  RUNS_START: code("runs", "start"),
  RUNS_PAUSE: code("runs", "pause"),
  RUNS_COMPLETE: code("runs", "complete"),
  RUNS_CANCEL: code("runs", "cancel"),
  RUNS_MANAGE_MEMBERS: code("runs", "manage_members"),
  RESULTS_READ: code("results", "read"),
  RESULTS_CREATE: code("results", "create"),
  RESULTS_UPDATE: code("results", "update"),
  RESULTS_DELETE: code("results", "delete"),
  RESULTS_CORRECT: code("results", "correct"),
  DOWNTIME_READ: code("downtime_events", "read"),
  DOWNTIME_CREATE: code("downtime_events", "create"),
  DOWNTIME_UPDATE: code("downtime_events", "update"),
  DOWNTIME_DELETE: code("downtime_events", "delete"),
  DOWNTIME_CLOSE: code("downtime_events", "close"),
  WASTE_READ: code("waste_records", "read"),
  WASTE_CREATE: code("waste_records", "create"),
  WASTE_UPDATE: code("waste_records", "update"),
  WASTE_DELETE: code("waste_records", "delete"),
} as const;

export const REPORT = {
  ORDER_FULL: "reports:production:order_full",
  ORDERS_SUMMARY: "reports:production:orders_summary",
  RESULTS_ANALYSIS: "reports:production:results_analysis",
  SHIFT_WORKFORCE: "reports:production:shift_workforce",
} as const;

/** Any one of these opens the production reports screen. */
export const PRODUCTION_REPORTS: string[] = [REPORT.ORDER_FULL, REPORT.ORDERS_SUMMARY, REPORT.RESULTS_ANALYSIS, REPORT.SHIFT_WORKFORCE];
