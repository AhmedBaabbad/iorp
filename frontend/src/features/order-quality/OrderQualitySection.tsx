"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { usePermission } from "@/features/auth/permission-hooks";
import s from "@/features/production-demands/demands.module.css";
import { getQualityChecks } from "@/features/quality-checks/api/quality-checks-api";
import { qualityErrorMessage } from "@/features/quality-checks/components/quality-errors";
import type { QualityCheckListItem } from "@/features/quality-checks/types";
import { getQualityRejections } from "@/features/quality-rejections/api/quality-rejections-api";
import type { QualityRejectionListItem } from "@/features/quality-rejections/types";
import { Q } from "@/lib/quality-permissions";

// Orders a lot can be inspected against; the same list the backend checks (quality/domain/rules.py ORDER_STATUSES).
const INSPECTABLE = ["in_progress", "on_hold", "completed"];

// "الجودة" on the order page: its inspections and rejections, and what still keeps the order from closing.
export function OrderQualitySection({ order, revision = 0 }: { order: { id: string; status: string }; revision?: number }) {
  const t = useTranslations("quality.orderSection");
  const errors = useTranslations("quality.errors");
  const canReadChecks = usePermission(Q.CHECKS_READ);
  const canReadRejections = usePermission(Q.REJECTIONS_READ);
  const canCreate = usePermission(Q.CHECKS_CREATE);
  const relevant = INSPECTABLE.includes(order.status) || order.status === "closed";
  const [checks, setChecks] = useState<QualityCheckListItem[] | null>(null);
  const [rejections, setRejections] = useState<QualityRejectionListItem[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!relevant) return;
    let active = true;
    const fail = (e: unknown) => { if (active) setError(qualityErrorMessage(e, errors)); };
    if (canReadChecks) getQualityChecks({ production_order_id: order.id }).then(v => { if (active) setChecks(v); }).catch(fail);
    if (canReadRejections) getQualityRejections({ production_order_id: order.id }).then(v => { if (active) setRejections(v); }).catch(fail);
    return () => { active = false; };
  }, [relevant, canReadChecks, canReadRejections, order.id, order.status, revision, errors]);

  if (!relevant || !(canReadChecks || canReadRejections)) return null;
  const openChecks = checks?.filter(c => c.status === "open" || c.status === "under_inspection").length ?? 0;
  const closedChecks = checks?.filter(c => c.status === "closed").length ?? 0;
  const unresolved = rejections?.filter(r => r.unresolved).length ?? 0;
  const tile = (label: string, value: number, href: string, warn = false) => <Link href={href} className={s.panel}
    style={{ margin: 0, padding: 14, textDecoration: "none", color: "inherit" }}>
    <span className={s.muted}>{label}</span>
    <strong style={{ display: "block", marginTop: 6, fontSize: 20, color: warn && value > 0 ? "var(--danger)" : undefined }}>{value}</strong>
  </Link>;

  return <section className={s.panel} aria-label={t("title")}>
    <div className={s.actions} style={{ justifyContent: "space-between" }}>
      <h2 style={{ margin: 0 }}>{t("title")}</h2>
      {canCreate && INSPECTABLE.includes(order.status) && <Link className={`${s.button} ${s.primary}`} href={`/quality-checks/new?order=${order.id}`}>{t("newCheck")}</Link>}
    </div>
    <p className={s.muted}>{t("hint")}</p>
    {error && <p role="alert" className={s.error}>{error}</p>}
    <div className={s.grid}>
      {canReadChecks && checks && <>
        {tile(t("openChecks"), openChecks, `/quality-checks?order=${order.id}`, true)}
        {tile(t("closedChecks"), closedChecks, `/quality-checks?order=${order.id}&status=closed`)}
      </>}
      {canReadRejections && rejections && <>
        {tile(t("unresolvedRejections"), unresolved, `/quality-rejections?order=${order.id}`, true)}
        {tile(t("allRejections"), rejections.length, `/quality-rejections?order=${order.id}`)}
      </>}
    </div>
    {(openChecks > 0 || unresolved > 0) && order.status !== "closed" && <p role="status" className={s.error} style={{ marginBottom: 0 }}>{t("blocksClose")}</p>}
  </section>;
}
