"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { usePermission } from "@/features/auth/permission-hooks";
import { getWorkCenters } from "@/features/work-centers";
import { apiClient, ApiClientError } from "@/lib/api-client";
import type { Demand, Item } from "./api";
import { Specs, priorities } from "./shared";
import { ArrangementTable, type ArrangedLine } from "./arrangement-table";
import { ExistingOrderDialog } from "./existing-order-dialog";
import s from "./demands.module.css";
import { P } from "@/lib/production-permissions";

// Integer thousandths avoid floating-point drift when summing decimal quantities.
function milli(value: string): bigint | null {
  if (!/^\d+(\.\d{1,3})?$/.test(value)) return null;
  const [whole, fraction = ""] = value.split(".");
  return BigInt(whole) * BigInt(1000) + BigInt(fraction.padEnd(3, "0"));
}
function decimal(value: bigint) { return `${value / BigInt(1000)}.${String(value % BigInt(1000)).padStart(3, "0")}`; }
type PreviewLine = { line_no: number; target_spec_json: Record<string, unknown> | null; planned_quantity: string; unit: string; allocations: { production_demand_item_id: string; demand_number: string; customer_name: string | null; demand_item_line_no: number; allocated_quantity: string }[] };
type Selection = { demand: Demand; item: Item; quantity: string };

export function PlanningAllocation({ demands, busy, onRefresh }: { demands: Demand[]; busy: boolean; onRefresh: () => void }) {
  const t = useTranslations("production.allocation");
  const d = useTranslations("production.demands");
  const p = useTranslations("production.productionOrders");
  const common = useTranslations("common");
  const canAllocate = usePermission(P.PLANNING_ALLOCATE);
  const canCreate = usePermission(P.ORDERS_CREATE);
  const router = useRouter();
  const dialog = useRef<HTMLDialogElement>(null);
  const [selected, setSelected] = useState<Record<string, Selection>>({});
  const [centers, setCenters] = useState<{ id: string; name: string }[]>([]);
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);
  const [review, setReview] = useState(false);
  const [lines, setLines] = useState<PreviewLine[]>([]);
  const [previewError, setPreviewError] = useState("");
  const [toExisting, setToExisting] = useState(false);
  useEffect(() => { setSelected({}); setReview(false); }, [demands]);
  useEffect(() => { if (review) dialog.current?.showModal(); else dialog.current?.close(); }, [review]);
  useEffect(() => {
    if (!canAllocate || !canCreate) return;
    let active = true;
    getWorkCenters().then(v => { if (active) setCenters(v); }).catch(() => { if (active) setError("error"); });
    return () => { active = false; };
  }, [canAllocate, canCreate]);
  const rows = Object.values(selected);
  const base = rows[0]?.item;
  // Differing specifications become separate order lines; product type and unit must still match.
  const compatible = rows.every(({ item }) => item.product_type === base?.product_type && item.unit === base?.unit);
  const missingProductType = rows.some(({ item }) => !item.product_type);
  const valid = rows.length > 0 && !missingProductType && rows.every(({ item, quantity }) => { const n = milli(quantity); return n !== null && n > BigInt(0) && n <= (milli(item.remaining_quantity ?? "0") ?? BigInt(0)); });
  const total = decimal(rows.reduce((sum, row) => sum + (milli(row.quantity) ?? BigInt(0)), BigInt(0)));
  // Serialized so the preview effect re-runs only when a selection or quantity really changes.
  const payload = JSON.stringify(rows.map(({ item, quantity }) => ({ production_demand_item_id: item.id, allocated_quantity: quantity })));
  // The server arranges lines (width -> color -> thickness -> weight); refresh while the review is open.
  useEffect(() => {
    if (!review || !valid || !compatible) { setLines([]); return; }
    let active = true;
    const timer = setTimeout(() => {
      apiClient<{ lines: PreviewLine[] }>("/production/planning/preview-production-order", { method: "POST", body: { allocations: JSON.parse(payload) } })
        .then(result => { if (active) { setLines(result.lines); setPreviewError(""); } })
        .catch(e => { if (active) { setLines([]); setPreviewError(e instanceof ApiClientError && e.status === 409 ? "conflict" : "error"); } });
    }, 250);
    return () => { active = false; clearTimeout(timer); };
  }, [review, valid, compatible, payload]);
  const arranged: ArrangedLine[] = lines.map(line => ({ key: String(line.line_no), line_no: line.line_no, target_spec_json: line.target_spec_json, planned_quantity: line.planned_quantity, unit: line.unit,
    allocations: line.allocations.map(a => ({ key: a.production_demand_item_id, customer_name: a.customer_name, demand_number: a.demand_number, demand_item_line_no: a.demand_item_line_no, allocated_quantity: a.allocated_quantity })) }));
  const setQuantity = (id: string, quantity: string) => setSelected(old => old[id] ? { ...old, [id]: { ...old[id], quantity } } : old);
  const remove = (id: string) => setSelected(old => { const next = { ...old }; delete next[id]; if (!Object.keys(next).length) setReview(false); return next; });
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!valid || !compatible || sending) return;
    const values = new FormData(event.currentTarget);
    setSending(true); setError("");
    try {
      const order = await apiClient<{ id: string }>("/production/planning/create-production-order", { method: "POST", body: {
        allocations: rows.map(({ item, quantity }) => ({ production_demand_item_id: item.id, allocated_quantity: quantity })),
        work_center_id: values.get("work_center_id"), priority: values.get("priority"), planned_start_date: values.get("start"), planned_end_date: values.get("end"), notes: values.get("notes") || null,
      } });
      sessionStorage.setItem("production-order-created", order.id);
      router.push(`/production-orders/${order.id}`);
    } catch (e) {
      setError(e instanceof ApiClientError && e.status === 409 ? "conflict" : "error");
      setReview(false);
    } finally { setSending(false); }
  }
  if (!canAllocate) return null;
  return <section className={s.panel}><h2>{t("title")}</h2><p>{t("select")}</p>
    {error && <div role="alert" className={s.error}>{t(error)} <button className={s.button} onClick={onRefresh}>{t("refresh")}</button></div>}
    <div className={s.tableWrap}><table className={s.table}><thead><tr><th>{t("select")}</th><th>{d("customer")}</th><th>{d("demandNumber")}</th><th>{d("lineNo")}</th><th>{d("productType")}</th><th>{d("specifications")}</th><th>{t("required")}</th><th>{t("allocated")}</th><th>{t("remaining")}</th><th>{t("quantity")}</th></tr></thead>
      <tbody>{demands.flatMap(demand => demand.items.map(item => { const id = item.id!; return <tr key={id}>
        <td><input type="checkbox" aria-label={`${t("select")} ${demand.demand_number} ${item.line_no}`} disabled={busy || sending || Number(item.remaining_quantity) <= 0 || !item.product_type} checked={!!selected[id]} onChange={e => setSelected(old => { const next = { ...old }; if (e.target.checked) next[id] = { demand, item, quantity: item.remaining_quantity ?? "0" }; else delete next[id]; return next; })} /></td>
        <td>{demand.customer.name}</td><td>{demand.demand_number}</td><td>{item.line_no}</td><td>{item.product_type || <span role="alert">{t("missingProductType")}</span>}</td><td><Specs value={item.target_spec_json} /></td><td>{item.required_quantity} {item.unit}</td><td>{item.allocated_quantity} {item.unit}</td><td>{item.remaining_quantity} {item.unit}</td>
        <td>{selected[id] && <input aria-label={`${t("quantity")} ${demand.demand_number} ${item.line_no}`} type="number" min="0.001" max={item.remaining_quantity} step="0.001" value={selected[id].quantity} disabled={sending} onChange={e => setSelected(old => ({ ...old, [id]: { ...old[id], quantity: e.target.value } }))} />}</td>
      </tr>; }))}</tbody></table></div>
    {rows.length > 0 && <div className={s.panel} style={{ position: "sticky", bottom: 0, zIndex: 2 }}>
      <p>{t("selected", { count: rows.length })} · {t("total")}: {total} {compatible ? base?.unit : ""}</p>
      {!compatible && <p role="alert">{t("incompatible")}</p>}{missingProductType && <p role="alert">{t("missingProductType")}</p>}{!missingProductType && !valid && <p role="alert">{t("invalid")}</p>}
      <div className={s.actions}><button className={s.button} disabled={sending} onClick={() => setSelected({})}>{t("clear")}</button>{rows.length === 1 && <button className={s.button} disabled={!valid || busy || sending} onClick={() => setToExisting(true)}>{t("addToExisting")}</button>}
        {canCreate && <button className={`${s.button} ${s.primary}`} disabled={!compatible || !valid || busy || sending} onClick={() => setReview(true)}>{t("create")}</button>}</div>
      {rows.length > 1 && <p className={s.muted}>{t("addToExistingOne")}</p>}
    </div>}
    {toExisting && rows.length === 1 && <ExistingOrderDialog item={rows[0].item} quantity={rows[0].quantity} onClose={() => setToExisting(false)} />}
    <dialog ref={dialog} onCancel={() => setReview(false)} className={s.panel} aria-labelledby="allocation-review-title" style={{ width: "min(850px, 90vw)", maxHeight: "85vh", overflow: "auto" }}>
      <h2 id="allocation-review-title">{t("review")}</h2>
      <p>{d("productType")}: <strong>{base?.product_type}</strong> · {t("total")}: <strong>{total} {base?.unit}</strong> · {t("lineCount", { count: arranged.length })}</p>
      <h3>{t("arrangement")}</h3><p className={s.muted}>{t("arrangementHint")}</p>
      {previewError && <p role="alert" className={s.error}>{t(previewError)}</p>}
      {!valid && <p role="alert">{t("invalid")}</p>}
      <ArrangementTable lines={arranged}
        quantityCell={a => <input aria-label={`${t("quantity")} ${a.demand_number} ${a.demand_item_line_no}`} type="number" min="0.001" step="0.001" value={selected[a.key]?.quantity ?? a.allocated_quantity} disabled={sending} onChange={e => setQuantity(a.key, e.target.value)} />}
        actionsCell={a => <button type="button" className={s.button} disabled={sending} onClick={() => remove(a.key)}>{t("removeFromOrder")}</button>} />
      <form onSubmit={submit}><fieldset disabled={sending} className={s.grid}>
        <label className={s.field}>{p("fields.workCenter")}<select name="work_center_id" required defaultValue=""><option value="">{t("selectCenter")}</option>{centers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
        <label className={s.field}>{d("priority")}<select name="priority" defaultValue="normal">{priorities.map(v => <option key={v} value={v}>{d(`priorities.${v}`)}</option>)}</select></label>
        <label className={s.field}>{p("fields.plannedStartDate")}<input name="start" type="date" required /></label>
        <label className={s.field}>{p("fields.plannedEndDate")}<input name="end" type="date" required /></label>
        <label className={s.field}>{d("notes")}<textarea name="notes" /></label>
      </fieldset><div className={s.actions}><button className={s.button} type="button" disabled={sending} onClick={() => setReview(false)}>{common("actions.cancel")}</button><button className={`${s.button} ${s.primary}`} disabled={sending || !centers.length || !valid || !arranged.length} type="submit">{sending ? d("loading") : t("create")}</button></div></form>
    </dialog>
  </section>;
}
