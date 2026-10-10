"use client";
import Link from "next/link";
import { useState } from "react";
import { useTranslations } from "next-intl";
import { usePermission } from "@/features/auth/permission-hooks";
import { demandsApi, type Demand, type DemandItemAllocation } from "./api";
import { ReasonDialog } from "./reason-dialog";
import { canReleaseFromOrder, lifecycleErrorCode, PLANNABLE_STATUSES, progress } from "./planning-lifecycle";
import s from "./demands.module.css";
import { P } from "@/lib/production-permissions";

export function AllocationStatusBadge({ status }: { status: DemandItemAllocation["status"] }) {
  const t = useTranslations("production.allocation");
  return <span className={`${s.badge} ${status === "active" ? s.green : s.released}`}>{t(`statuses.${status}`)}</span>;
}

export function DemandAllocations({ demand, onChanged }: { demand: Demand; onChanged?: () => void }) {
  const t = useTranslations("production.allocation");
  const d = useTranslations("production.demands");
  const enums = useTranslations();
  const canAllocate = usePermission(P.PLANNING_ALLOCATE);
  const canRelease = usePermission(P.PLANNING_RELEASE_ALLOCATION);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [releasing, setReleasing] = useState<DemandItemAllocation | null>(null);
  // Allocating needs only the allocation permission: the planning screen offers a new order (with the create
  // permission) or an existing open one.
  const showAllocateLink = canAllocate && PLANNABLE_STATUSES.includes(demand.status) && Number(demand.total_remaining) > 0;
  const summary: [string, string][] = [
    [t("required"), demand.total_required], [t("activeAllocated"), demand.total_active_allocated ?? demand.total_allocated],
    [t("releasedAllocated"), demand.total_released_allocated ?? "0"], [t("remaining"), demand.total_remaining],
  ];
  const units = [...new Set(demand.items.map(i => i.unit))];
  async function release(allocation: DemandItemAllocation, reason: string) {
    setBusy(true); setError(""); setNotice("");
    try { await demandsApi.releaseAllocation(allocation.id, reason); setNotice(t("releaseSuccess")); setReleasing(null); onChanged?.(); }
    catch (e) { setError(lifecycleErrorCode(e)); setReleasing(null); }
    finally { setBusy(false); }
  }
  return <section className={s.panel}><h2>{t("planningTitle")}</h2>
    {showAllocateLink && <p><Link className={`${s.button} ${s.primary}`} href={`/production/planning?search=${encodeURIComponent(demand.demand_number)}`}>{t("allocateNow")}</Link></p>}
    {error && <p role="alert" className={s.error}>{t(`errors.${t.has(`errors.${error}`) ? error : "request_failed"}`)}</p>}
    {notice && <p role="status" className={s.success}>{notice}</p>}
    <dl className={s.grid} aria-label={t("summary")}>{summary.map(([label, value]) => <div key={label}><dt className={s.muted}>{label}</dt><dd style={{ margin: "6px 0", fontWeight: 700 }}>{value} {units.length === 1 ? units[0] : ""}</dd></div>)}</dl>
    <label>{t("percentage")}: {Number(demand.allocation_percentage).toFixed(1)}% <progress aria-label={t("percentage")} max={100} value={Number(demand.allocation_percentage)} /></label>
    {demand.items.map(item => { const q = progress(item); return <section key={item.id} className={s.panel}>
      <h3>{d("lineNo")} {item.line_no}</h3>
      <p>{t("required")}: {q.required} {item.unit} · {t("activeAllocated")}: {q.allocated} {item.unit} · {t("releasedAllocated")}: {item.released_allocated_quantity ?? "0"} {item.unit} · {t("remaining")}: {q.remaining} {item.unit}</p>
      <progress aria-label={`${t("percentage")} ${item.line_no}`} max={100} value={q.percent} />
      {item.allocations?.length ? <div className={s.tableWrap}><table className={s.table} aria-label={t("history")}><thead><tr>
        <th>{t("order")}</th><th>{t("orderStatus")}</th><th>{t("quantityColumn")}</th><th>{t("allocationStatus")}</th><th>{t("allocatedAt")}</th><th>{t("releasedAt")}</th><th>{t("releaseReason")}</th>{canRelease && <th>{d("actions")}</th>}
      </tr></thead><tbody>{item.allocations.map(a => <tr key={a.id} style={a.status === "released" ? { opacity: 0.75 } : undefined}>
        <td><Link href={`/production-orders/${a.production_order_id}`}>{a.production_order_number}</Link></td>
        <td>{enums(`enums.productionOrder.status.${a.production_order_status}`)}</td>
        <td>{a.allocated_quantity} {item.unit}</td>
        <td><AllocationStatusBadge status={a.status} /></td>
        <td>{new Date(a.created_at).toLocaleString()}</td>
        <td>{a.released_at ? new Date(a.released_at).toLocaleString() : "—"}</td>
        <td>{a.release_reason ?? "—"}</td>
        {canRelease && <td>{a.status === "active" && canReleaseFromOrder(a.production_order_status) && <button className={s.button} disabled={busy} onClick={() => { setNotice(""); setReleasing(a); }}>{t("release")}</button>}</td>}
      </tr>)}</tbody></table></div> : <p>{t("empty")}</p>}
    </section>; })}
    {releasing && <ReasonDialog title={t("releaseTitle", { order: releasing.production_order_number })} description={t("releaseHint")} confirmLabel={t("release")} busy={busy} onClose={() => setReleasing(null)} onConfirm={reason => release(releasing, reason)} />}
  </section>;
}
