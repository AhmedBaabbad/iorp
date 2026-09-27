"use client";

import { ExecutionPanel } from "@/features/production-execution/ExecutionPanel";
import { PageFrame } from "@/components/layout/page-frame";
import { useTranslations } from "next-intl";
import { PermissionGuard } from "@/components/PermissionGuard";

export default function Page() {
  const t = useTranslations("production.shifts");
  return <PageFrame section="Production" title={t("rosters")}><PermissionGuard code="production:shift_rosters:read"><ExecutionPanel /></PermissionGuard></PageFrame>;
}
