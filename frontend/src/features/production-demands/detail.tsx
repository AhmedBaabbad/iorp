"use client";
import { customerDisplayName } from "@/lib/customer-name";
import { UnitLabel } from "@/components/UnitLabel";
import Link from "next/link";
import {Tabs} from "@/components/ui/Tabs";
import {RecordHistory} from "@/components/RecordHistory";
import {DemandItemDialog} from "./item-dialog";
import {ReasonDialog} from "./reason-dialog";
import type {Item} from "./api";
import { DemandAllocations } from "./demand-allocations";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { PageFrame } from "@/components/layout/page-frame";
import { usePermission } from "@/features/auth/permission-hooks";
import { demandsApi, type Demand, type DemandStatus } from "./api";
import { Badge, ErrorMessage, errorKey, transitions, Specs } from "./shared";
import s from "./demands.module.css";
import { P } from "@/lib/production-permissions";

export function DemandDetail({ id }: { id: string }) {
  const locale = useLocale();
  const t = useTranslations("production.demands");
  const router = useRouter();
  const history=useTranslations("production.recordHistory");
  const [editing,setEditing]=useState<Item|null|undefined>(undefined);
  const [revision,setRevision]=useState(0);
  const [pendingStatus,setPendingStatus]=useState<DemandStatus|null>(null);
  async function reload(){setDemand(await demandsApi.get(id));setRevision(v=>v+1);}
  async function removeItem(itemId:string){if(!window.confirm(t("removeItem")))return;try{await demandsApi.removeItem(id,itemId);await reload();}catch(e){setError(errorKey(e));}}
  const canUpdate = usePermission(P.DEMANDS_UPDATE);
  const canRelease = usePermission(P.DEMANDS_RELEASE);
  const canCancel = usePermission(P.DEMANDS_CANCEL);
  const canDelete = usePermission(P.DEMANDS_DELETE);
  const [d, setDemand] = useState<Demand | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { let active = true; demandsApi.get(id).then(v => { if (active) setDemand(v); }).catch(e => { if (active) setError(errorKey(e)); }); return () => { active = false; }; }, [id]);
  async function change(status: DemandStatus,reason:string) {
    setBusy(true); setError("");
    try { await demandsApi.status(id, status,reason); await reload();setPendingStatus(null); } catch (e) { setError(errorKey(e)); } finally { setBusy(false); }
  }
  async function remove() {
    if (!window.confirm(t("confirmDelete"))) return;
    setBusy(true); setError("");
    try { await demandsApi.remove(id); router.push("/production/demands"); } catch (e) { setError(errorKey(e)); setBusy(false); }
  }
  return <PageFrame title={d?.demand_number ?? t("detailTitle")} subtitle={t("detailTitle")}>
    <Link href="/production/demands" className={s.button}>{t("backToList")}</Link><ErrorMessage code={error} />
    {!d && !error && <p>{t("loading")}</p>}
    {d && <><Tabs label={t("detailTitle")} items={[{id:"data",label:t("details"),content:<><section className={s.panel}>
      <div className={s.toolbar}><Badge value={d.status} /><Badge value={d.priority} priority />
        {canUpdate && !d.items.some(i=>i.allocations?.length) && ["draft", "ready_for_planning"].includes(d.status) && <Link className={s.button} href={`/production/demands/${id}/edit`}>{t("editTitle")}</Link>}
        {transitions[d.status].filter(status => status === 'cancelled' ? canCancel : canRelease).map(status => <button key={status} disabled={busy} className={s.button} onClick={() => setPendingStatus(status)}>{t(`statuses.${status}`)}</button>)}
        {canDelete && d.status === "draft" && <button disabled={busy} className={s.button} onClick={remove}>{t("delete")}</button>}
      </div>
      <dl className={s.grid}>{[[t("customer"), `${d.customer.code} · ${customerDisplayName(d.customer, locale)}`], [t("fromSalesOrder.salesOrder"), d.sales_order ? <a key="so" href={`/commercial-orders/${d.sales_order.id}`}><bdi>{d.sales_order.number}</bdi></a> : t("none")], [t("quote"), d.quote?.number ?? t("none")], [t("requestDate"), d.request_date], [t("requestedDeliveryDate"), d.requested_delivery_date ?? t("none")], [t("createdBy"), d.created_by ?? t("none")], [t("atDate"), new Date(d.created_at).toLocaleString()], [t("notes"), d.notes ?? t("none")]].map(([label, value]) => <div key={String(label)}><dt className={s.muted}>{label}</dt><dd style={{ margin: "6px 0" }}>{value}</dd></div>)}</dl>
    </section><section className={s.panel}><h2>{t("items")}</h2>{canUpdate&&!d.sales_order&&["draft","ready_for_planning","partially_planned"].includes(d.status)&&<button type="button" className={s.button} onClick={()=>setEditing(null)}>{t("addItem")}</button>}{d.quote && <p className={s.muted}>{t("snapshotNote")}</p>}<div className={s.tableWrap}><table className={s.table}><thead><tr>{["lineNo", "productType", "specifications", "quantity", "unit", "itemNotes", "actions"].map(k => <th key={k}>{t(k)}</th>)}</tr></thead><tbody>{d.items.map(i => <tr key={i.id}><td>{i.line_no}</td><td>{i.product_type}</td><td><Specs value={i.target_spec_json} /></td><td>{i.required_quantity}</td><td><UnitLabel value={i.unit}/></td><td>{i.notes}</td><td>{i.allocations?.some(a=>a.status==="active")?<span>{t("itemAllocatedHint")} {i.allocations.filter(a=>a.status==="active").map(a=>a.production_order_number).join(", ")}</span>:canUpdate&&["draft","ready_for_planning","partially_planned","planned"].includes(d.status)&&<><button className={s.button} onClick={()=>setEditing(i)}>{t("editItem")}</button>{!i.allocations?.length&&<button className={s.button} onClick={()=>void removeItem(i.id!)}>{t("removeItem")}</button>}</>}</td></tr>)}</tbody></table></div></section><DemandAllocations demand={d} onChanged={()=>{void reload().catch(e=>setError(errorKey(e)));}} /></>},{id:"history",label:history("title"),content:<RecordHistory entityType="production_demand" entityId={id} revision={revision}/>}]} />{editing!==undefined&&<DemandItemDialog demandId={id} item={editing??undefined} salesOrder={!!d.sales_order} onClose={()=>setEditing(undefined)} onSaved={reload}/>}</>}
    {pendingStatus&&<ReasonDialog title={t(`statuses.${pendingStatus}`)} confirmLabel={t(`statuses.${pendingStatus}`)} busy={busy} onClose={()=>setPendingStatus(null)} onConfirm={reason=>void change(pendingStatus,reason)}/>}
  </PageFrame>;
}
