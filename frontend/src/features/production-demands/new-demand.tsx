"use client";
import Link from "next/link";
import { useState } from "react";
import { useTranslations } from "next-intl";
import { PageFrame } from "@/components/layout/page-frame";
import { DemandForm } from "./form";
import { DemandFromSalesOrder } from "./from-sales-order";
import s from "./demands.module.css";

// A new production demand: from a confirmed sales order (the usual way, SALES-001), or entered by hand (stock, trials).
export function NewDemand() {
  const t = useTranslations("production.demands");
  const [mode, setMode] = useState<"sales_order" | "manual">("sales_order");
  if (mode === "manual") return <DemandForm onBack={() => setMode("sales_order")} />;
  return <PageFrame title={t("createTitle")} subtitle={t("listSubtitle")}>
    <div className={s.toolbar}>
      <Link href="/production/demands" className={s.button}>{t("backToList")}</Link>
      <button type="button" className={s.linkButton} onClick={() => setMode("manual")}>{t("fromSalesOrder.manualInstead")}</button>
    </div>
    <DemandFromSalesOrder />
  </PageFrame>;
}
