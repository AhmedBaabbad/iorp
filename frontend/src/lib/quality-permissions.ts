// Quality permission codes (QUAL-001), mirroring backend/app/quality/domain/permissions.py.
// Screens refer to these names only; tests/quality-permissions.test.mjs keeps both lists identical.
// The server enforces every permission; the screens use them only to hide what a user cannot do.

const code = <R extends string, A extends string>(resource: R, action: A) => `quality:${resource}:${action}` as const;

export const Q = {
  CHECKS_READ: code("quality_checks", "read"),
  CHECKS_CREATE: code("quality_checks", "create"),
  CHECKS_UPDATE: code("quality_checks", "update"),
  CHECKS_START: code("quality_checks", "start"),
  CHECKS_CLOSE: code("quality_checks", "close"),
  CHECKS_CANCEL: code("quality_checks", "cancel"),
  CHECKS_MEASURE: code("quality_checks", "measure"),
  REJECTIONS_READ: code("rejections", "read"),
  REJECTIONS_CREATE: code("rejections", "create"),
  REJECTIONS_UPDATE: code("rejections", "update"),
  REJECTIONS_DECIDE: code("rejections", "decide"),
  REJECTIONS_EXECUTE: code("rejections", "execute"),
  DEFECTS_READ: code("quality_defects", "read"),
  DEFECTS_CREATE: code("quality_defects", "create"),
  DEFECTS_UPDATE: code("quality_defects", "update"),
  NCR_READ: code("ncr_reports", "read"),
  NCR_CREATE: code("ncr_reports", "create"),
  NCR_UPDATE: code("ncr_reports", "update"),
  SPECS_READ: code("specifications", "read"),
  SPECS_CREATE: code("specifications", "create"),
  SPECS_UPDATE: code("specifications", "update"),
  SPECS_ACTIVATE: code("specifications", "activate"),
} as const;

// Quality report center (QUAL-REPORT-001), mirroring backend/app/quality/domain/report_permissions.py.
const report = <K extends string>(key: K) => `reports:quality:${key}` as const;

export const QUALITY_REPORT = {
  CHECK_FULL: report("check_full"),
  CHECKS_SUMMARY: report("checks_summary"),
  REJECTIONS_ANALYSIS: report("rejections_analysis"),
  DEFECTS_ANALYSIS: report("defects_analysis"),
} as const;

/** Any one of these opens the quality reports screen. */
export const QUALITY_REPORTS: string[] = Object.values(QUALITY_REPORT);
