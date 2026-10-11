"use client";
import Link from "next/link";
import { PlanningAllocation } from "./planning-allocation";
import { useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { PageFrame } from "@/components/layout/page-frame";
import { usePermission } from "@/features/auth/permission-hooks";
import { demandsApi, type Customer, type Demand, type Page, type DemandStatus } from "./api";
import { Badge, ErrorMessage, errorKey, priorities, Specs, today } from "./shared";
import { PLANNABLE_STATUSES, progress } from "./planning-lifecycle";
import s from "./demands.module.css";
import { StatusVisibilityPicker } from "./StatusVisibilityPicker";
import { ALL_STATUSES, DEMANDS, PLANNING, initialStatuses, isActiveQueue, planningQuery, planningStatusesFromUrl, readStored, statusQuery, store, withStatusesInUrl } from "./status-visibility";
import { P } from "@/lib/production-permissions";
import { downloadFile, DownloadError } from "@/lib/download";

export function DemandList({ planning = false }: { planning?: boolean }) {
  const t = useTranslations("production.demands");
  const p = useTranslations("production.planning");
  const canCreate = usePermission(P.DEMANDS_CREATE);
  const canReorder = usePermission(P.PLANNING_SEQUENCE);
  const canRead = usePermission(P.DEMANDS_READ);
  const canUpdate = usePermission(P.DEMANDS_UPDATE);
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const [filters, setFilters] = useState<Record<string, string>>(() => {
    const search = searchParams.get("search");
    const initial: Record<string, string> = {};
    if (search) initial.search = search;
    return initial;
  });
  const [page, setPage] = useState(1);
  // The statuses shown (hidden ones are only hidden, never deleted). Read from the URL now and from this
  // browser after mount (localStorage is not available while rendering on the server); nothing loads until known.
  const config = planning ? PLANNING : DEMANDS;
  const fromUrl = planning ? planningStatusesFromUrl(searchParams.get("statuses"), searchParams.get("view")) : initialStatuses(searchParams.get("statuses"), null, []);
  const [visible, setVisible] = useState<DemandStatus[]>(() => fromUrl?.length ? fromUrl : config.defaults);
  const [visibleReady, setVisibleReady] = useState(Boolean(fromUrl?.length));
  useEffect(() => {
    if (visibleReady) return;
    setVisible(initialStatuses(null, readStored(config.storageKey), config.defaults));
    setVisibleReady(true);
  }, [config, visibleReady]);
  const [data, setData] = useState<Page | null>(null);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [revision, refresh] = useState(0);
  useEffect(() => { let active = true; demandsApi.customers().then(v => { if (active) setCustomers(v); }).catch(e => { if (active) setError(errorKey(e)); }); return () => { active = false; }; }, []);
  useEffect(() => {
    if (!visibleReady) return;
    let active = true; setBusy(true); setError("");
    const query = listQuery();
    demandsApi.list(query, planning).then(v => { if (active) setData(v); }).catch(e => { if (active) setError(errorKey(e)); }).finally(() => { if (active) setBusy(false); });
    return () => { active = false; };
  }, [filters, page, planning, revision, visible, visibleReady]); // eslint-disable-line react-hooks/exhaustive-deps -- listQuery reads only these
  const filter = (key: string, value: string) => { setFilters(old => ({ ...old, [key]: value })); setPage(1); };
  // The screen's query; the Excel export sends the same filters without the page (every matching demand).
  function listQuery() {
    return planning ? planningQuery(visible, filters, page) : new URLSearchParams([...Object.entries(filters).filter(([, v]) => v), ...statusQuery(visible), ["page", String(page)], ["page_size", "20"]]).toString();
  }
  const [exporting, setExporting] = useState(false);
  async function exportExcel() {
    const query = new URLSearchParams(listQuery());
    query.delete("page"); query.delete("page_size");
    setExporting(true); setError("");
    try { await downloadFile(`/production/${planning ? "planning/demands" : "demands"}/export.xlsx?${query}`, "demands.xlsx"); }
    catch (e) { setError(e instanceof DownloadError && e.code === "export_too_large" ? "export_too_large" : "export_failed"); }
    finally { setExporting(false); }
  }
  const changeVisible = (next: DemandStatus[]) => {
    setVisible(next); setPage(1); store(next, config.storageKey);
    const params = withStatusesInUrl(searchParams.toString(), next, config.defaults);
    router.replace(params.size ? `${pathname}?${params}` : pathname, { scroll: false });
  };
  const hidden = data?.hidden_by_status ?? 0;
  // The queue proper: sequence order, reordering and allocation.
  const activeQueue = planning && isActiveQueue(visible);
  const reorderable = activeQueue && canReorder;
  // Stable reference: PlanningAllocation clears the planner's selection whenever this list changes.
  const allocatable = useMemo(() => data?.items.filter(d => PLANNABLE_STATUSES.includes(d.status)) ?? [], [data]);
  const filtered = Object.values(filters).some(Boolean);
  async function reorder(id: string, position: number) {
    setBusy(true); setNotice("");
    try { await demandsApi.reorder(id, position); setNotice(p("reorderSuccess")); refresh(v => v + 1); }
    catch (e) { setError(errorKey(e)); setBusy(false); }
  }
  async function changeStatus(id: string, status: DemandStatus) {
    if (status === "cancelled" && !window.confirm(t("confirmCancel"))) return;
    setBusy(true); setError("");
    try { await demandsApi.status(id, status); refresh(v => v + 1); }
    catch (e) { setError(errorKey(e)); setBusy(false); }
  }
  return <PageFrame title={planning ? p("title") : t("listTitle")} subtitle={planning ? p("subtitle") : t("listSubtitle")}>
    <section className={s.panel}>
      <div className={s.toolbar}>
        <label className={s.field}>{t("search")}<input value={filters.search ?? ""} onChange={e => filter("search", e.target.value)} /></label>
        <label className={s.field}>{t("customer")}<select value={filters.customer_id ?? ""} onChange={e => filter("customer_id", e.target.value)}><option value="">{t("all")}</option>{customers.map(c => <option key={c.id} value={c.id}>{c.code} · {c.name}</option>)}</select></label>
        <label className={s.field}>{t("priority")}<select value={filters.priority ?? ""} onChange={e => filter("priority", e.target.value)}><option value="">{t("all")}</option>{priorities.map(v => <option key={v} value={v}>{t(`priorities.${v}`)}</option>)}</select></label>
        <StatusVisibilityPicker value={visible} defaults={config.defaults} onChange={changeVisible} />
        {planning && <><label className={s.field}>{t("productType")}<input value={filters.product_type ?? ""} onChange={e => filter("product_type", e.target.value)} /></label><label className={s.field}>{t("deliveryFrom")}<input type="date" value={filters.requested_delivery_from ?? ""} onChange={e => filter("requested_delivery_from", e.target.value)} /></label><label className={s.field}>{t("deliveryTo")}<input type="date" value={filters.requested_delivery_to ?? ""} onChange={e => filter("requested_delivery_to", e.target.value)} /></label></>}
        <button type="button" className={s.button} disabled={exporting || busy} onClick={() => void exportExcel()}>{exporting ? t("exporting") : t("exportExcel")}</button>
        {!planning && canCreate && <Link className={`${s.button} ${s.primary}`} href="/production/demands/new">{t("createTitle")}</Link>}
      </div>
      <ErrorMessage code={error} />
      {hidden > 0 && <p role="status" className={s.muted}>{t("statusVisibility.hidden", { count: hidden })} <button type="button" className={s.linkButton} onClick={() => changeVisible([...ALL_STATUSES])}>{t("statusVisibility.showAll")}</button></p>}
      {notice && <p role="status" className={s.success}>{notice}</p>}
      {busy && <p role="status">{t("loading")}</p>}
      {reorderable && filtered && <p className={s.muted}>{p("clearFiltersToReorder")}</p>}
      <div className={s.tableWrap}><table className={s.table}><thead><tr>
        {planning && <th>{p("sequence")}</th>}<th>{t("demandNumber")}</th><th>{t("customer")}</th>
        {planning ? <><th>{t("productType")}</th><th>{p("specColumns.width_mm")}</th><th>{p("specColumns.thickness_mm")}</th><th>{p("specColumns.color")}</th><th>{p("specColumns.roll_weight_kg")}</th><th>{t("specifications")}</th><th>{p("requiredQuantity")}</th><th>{p("activeAllocated")}</th><th>{p("remaining")}</th></> : <><th>{t("quote")}</th><th>{t("requestDate")}</th><th>{t("items")}</th></>}
        {!planning && <><th>{t("totalQuantity")}</th><th>{t("atDate")}</th></>}
        <th>{t("requestedDeliveryDate")}</th><th>{t("priority")}</th><th>{t("status")}</th>{(!planning || reorderable) && <th>{t("actions")}</th>}
      </tr></thead><tbody>{data?.items.map((d, index) => {
        const overdue = planning && !!d.requested_delivery_date && d.requested_delivery_date < today();
        const position = (page - 1) * 20 + index + 1;
        return <tr key={d.id} className={overdue ? s.overdue : ""}>
          {planning && <td>{d.planning_sequence ?? position}</td>}<td>{canRead ? <Link href={`/production/demands/${d.id}`}>{d.demand_number}</Link> : d.demand_number}</td><td>{d.customer.name}<div className={s.muted}>{d.customer.code}</div></td>
          {planning ? <><td>{d.items?.map(i => i.product_type).filter(Boolean).join(", ")}</td>{["width_mm", "thickness_mm", "color", "roll_weight_kg"].map(k => <td key={k}>{String(d.spec_summary?.[k] ?? "")}</td>)}<td><Specs value={d.spec_summary ?? null} /></td><PlanningQuantities demand={d} /></> : <><td>{d.quote?.number ?? t("none")}</td><td>{d.request_date}</td><td>{t("itemCount", { count: d.item_count })}</td></>}
          {!planning && <><td>{Object.entries(d.quantities_by_unit ?? {}).map(([unit, quantity]) => <div key={unit}>{quantity} {unit}</div>)}</td><td>{new Date(d.created_at).toLocaleDateString()}</td></>}
          <td>{d.requested_delivery_date ?? t("none")}{overdue && <div>{p("overdue")}</div>}</td><td><Badge value={d.priority} priority /></td><td><Badge value={d.status} /></td>
          {!planning && <td><div className={s.actions}><Link className={s.button} href={`/production/demands/${d.id}`}>{t("detailTitle")}</Link>{canUpdate && <>{["draft", "ready_for_planning"].includes(d.status) && <Link className={s.button} href={`/production/demands/${d.id}/edit`}>{t("editTitle")}</Link>}{d.status === "draft" && <button disabled={busy} className={s.button} onClick={() => changeStatus(d.id, "ready_for_planning")}>{t("markReady")}</button>}{["draft", "ready_for_planning"].includes(d.status) && <button disabled={busy} className={s.button} onClick={() => changeStatus(d.id, "cancelled")}>{t("cancel")}</button>}</>}</div></td>}
          {reorderable && <td><div className={s.actions}><button className={s.button} disabled={busy || filtered || position === 1} aria-label={p("moveUp")} onClick={() => reorder(d.id, position - 1)}>↑</button><button className={s.button} disabled={busy || filtered || position >= (data?.total ?? 0)} aria-label={p("moveDown")} onClick={() => reorder(d.id, position + 1)}>↓</button></div></td>}
        </tr>;
      })}</tbody></table></div>
      {!busy && data?.total === 0 && <p>{planning ? p(`views.empty.${activeQueue ? "active" : "all"}`) : t("empty")}</p>}
      <div className={s.toolbar}><button className={s.button} disabled={busy || page <= 1} onClick={() => setPage(v => v - 1)}>{t("previous")}</button><span>{t("page", { page, count: Math.max(1, Math.ceil((data?.total ?? 0) / 20)) })}</span><button className={s.button} disabled={busy || page * 20 >= (data?.total ?? 0)} onClick={() => setPage(v => v + 1)}>{t("next")}</button></div>
    </section>
    {activeQueue && data && <PlanningAllocation demands={allocatable} busy={busy} onRefresh={() => refresh(v => v + 1)} />}
  </PageFrame>;
}

// Per item: required, ACTIVE allocated with progress, and remaining. Released allocations never count here.
function PlanningQuantities({ demand }: { demand: Demand }) {
  const p = useTranslations("production.planning");
  const rows = (demand.items ?? []).map(item => ({ item, q: progress(item) }));
  return <>
    <td>{rows.map(({ item, q }, n) => <div key={item.id ?? n}>{q.required} {item.unit}</div>)}</td>
    <td>{rows.map(({ item, q }, n) => <div key={item.id ?? n}>
      <span>{p("plannedOf", { allocated: q.allocated, required: q.required, unit: item.unit })}</span>
      {q.partial && <progress aria-label={p("progressLabel", { line: item.line_no ?? n + 1 })} max={100} value={q.percent} style={{ display: "block", width: "100%" }} />}
    </div>)}</td>
    <td>{rows.map(({ item, q }, n) => <div key={item.id ?? n}>{p("remainingOf", { remaining: q.remaining, unit: item.unit })}</div>)}</td>
  </>;
}
