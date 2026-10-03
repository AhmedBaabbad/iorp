"use client";
import { useTranslations } from "next-intl";
import { ReportCenter } from "@/features/reports/ReportsPage";
import { PermissionGate } from "@/features/auth/permission-gate";
import { QUALITY_REPORTS } from "@/lib/quality-permissions";

// The quality report center: the same center as production's, listing the quality reports the user may run.
export default function Page() {
  const t = useTranslations("quality.reportCenter");
  return <PermissionGate anyOf={QUALITY_REPORTS}><ReportCenter module="quality" title={t("title")} /></PermissionGate>;
}
