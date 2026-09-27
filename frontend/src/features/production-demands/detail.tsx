"use client";
import Link from "next/link";
import { DemandAllocations } from "./demand-allocations";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { PageFrame } from "@/components/layout/page-frame";
import { usePermission } from "@/features/auth/permission-hooks";
import { demandsApi, type Demand, type DemandStatus } from "./api";
import { Badge, ErrorMessage, errorKey, transitions, Specs } from "./shared";
import s from "./demands.module.css";

export function DemandDetail({ id }: { id: string }) {
  const t = useTranslations("production.demands");
  const router = useRouter();
  const canUpdate = usePermission("production:demands:update");
  const canDelete = usePermission("production:demands:delete");
  const [d, setDemand] = useState<Demand | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { let active = true; demandsApi.get(id).then(v => { if (active) setDemand(v); }).catch(e => { if (active) setError(errorKey(e)); }); return () => { active = false; }; }, [id]);
  async function change(status: DemandStatus) {
    if (status === "cancelled" && !window.confirm(t("confirmCancel"))) return;
    setBusy(true); setError("");
    try { await demandsApi.status(id, status); setDemand(await demandsApi.get(id)); } catch (e) { setError(errorKey(e)); } finally { setBusy(false); }
  }
  async function remove() {
    if (!window.confirm(t("confirmDelete"))) return;
    setBusy(true); setError("");
    try { await demandsApi.remove(id); router.push("/production/demands"); } catch (e) { setError(errorKey(e)); setBusy(false); }
  }
  return <PageFrame title={d?.demand_number ?? t("detailTitle")} subtitle={t("detailTitle")}>
    <Link href="/production/demands" className={s.button}>{t("backToList")}</Link><ErrorMessage code={error} />
    {!d && !error && <p>{t("loading")}</p>}
    {d && <><section className={s.panel}>
      <div className={s.toolbar}><Badge value={d.status} /><Badge value={d.priority} priority />
        {canUpdate && ["draft", "ready_for_planning"].includes(d.status) && <Link className={s.button} href={`/production/demands/${id}/edit`}>{t("editTitle")}</Link>}
        {canUpdate && transitions[d.status].map(status => <button key={status} disabled={busy} className={s.button} onClick={() => change(status)}>{t(`statuses.${status}`)}</button>)}
        {canDelete && d.status === "draft" && <button disabled={busy} className={s.button} onClick={remove}>{t("delete")}</button>}
      </div>
      <dl className={s.grid}>{[[t("customer"), `${d.customer.code} · ${d.customer.name}`], [t("quote"), d.quote?.number ?? t("none")], [t("requestDate"), d.request_date], [t("requestedDeliveryDate"), d.requested_delivery_date ?? t("none")], [t("createdBy"), d.created_by ?? t("none")], [t("atDate"), new Date(d.created_at).toLocaleString()], [t("notes"), d.notes ?? t("none")]].map(([label, value]) => <div key={label}><dt className={s.muted}>{label}</dt><dd style={{ margin: "6px 0" }}>{value}</dd></div>)}</dl>
    </section><section className={s.panel}><h2>{t("items")}</h2>{d.quote && <p className={s.muted}>{t("snapshotNote")}</p>}<div className={s.tableWrap}><table className={s.table}><thead><tr>{["lineNo", "productType", "specifications", "quantity", "unit", "itemNotes"].map(k => <th key={k}>{t(k)}</th>)}</tr></thead><tbody>{d.items.map(i => <tr key={i.id}><td>{i.line_no}</td><td>{i.product_type}</td><td><Specs value={i.target_spec_json} /></td><td>{i.required_quantity}</td><td>{i.unit}</td><td>{i.notes}</td></tr>)}</tbody></table></div></section><DemandAllocations demand={d} onChanged={() => { demandsApi.get(id).then(setDemand).catch(e => setError(errorKey(e))); }} /></>}
  </PageFrame>;
}
