"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { PageFrame } from "@/components/layout/page-frame";

export function ProductionOrderForm() {
  const t = useTranslations("production.allocation");
  const router = useRouter();
  useEffect(() => { router.replace("/production/planning"); }, [router]);
  return <PageFrame title={t("create")} subtitle={t("fromPlanning")}>{null}</PageFrame>;
}
