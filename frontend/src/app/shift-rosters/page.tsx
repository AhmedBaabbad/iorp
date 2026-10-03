"use client";

import { ExecutionPanel } from "@/features/production-execution/ExecutionPanel";
import { PageFrame } from "@/components/layout/page-frame";
import { useTranslations } from "next-intl";
import { PermissionGuard } from "@/components/PermissionGuard";
import { P } from "@/lib/production-permissions";

export default function Page() {
  const t = useTranslations("production.shifts");
  return <PageFrame section="Production" title={t("rosters")}><PermissionGuard code={P.ROSTERS_READ}><ExecutionPanel /></PermissionGuard></PageFrame>;
}
