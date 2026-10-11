"use client";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useTranslations } from "next-intl";
import { usePermission } from "@/features/auth/permission-hooks";
import { demandsApi } from "@/features/production-demands/api";
import { ArrangementTable, type ArrangedLine } from "@/features/production-demands/arrangement-table";
import { lifecycleErrorCode } from "@/features/production-demands/planning-lifecycle";
import { ReasonDialog } from "@/features/production-demands/reason-dialog";
import { addOrderAllocation, changeAllocationQuantity, getEligibleDemandItems, type EligibleDemandItem } from "../api/production-orders-api";
import type { ProductionOrderData } from "../types";
import s from "@/features/production-demands/demands.module.css";
import { P } from "@/lib/production-permissions";

type Allocation = ProductionOrderData["allocations"][number];
const QUANTITY = /^\d+(\.\d{1,3})?$/;

// Order lines grouped by specification; an open order's allocations (draft, released, in progress, on hold) can be changed here.
export function OrderLines({ order, onChanged }: { order: ProductionOrderData; onChanged?: () => void }) {
  const t = useTranslations("production.allocation");
  const d = useTranslations("production.demands");
  const canAllocate = usePermission(P.PLANNING_ALLOCATE);
  const canRelease = usePermission(P.PLANNING_RELEASE_ALLOCATION);
  // The server says whether allocations are open; adding/changing and releasing each need their own permission.
  const open = Boolean(order.allocation_open);
  const editing = open && canAllocate;
  const releasing_allowed = open && canRelease;
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [releasing, setReleasing] = useState<Allocation | null>(null);
  const [candidates, setCandidates] = useState<EligibleDemandItem[]>([]);
  const [search, setSearch] = useState("");
  const [searching, setSearching] = useState(false);
  const [addItem, setAddItem] = useState("");
  const [addQuantity, setAddQuantity] = useState("");

  const byId = useMemo(() => new Map(order.allocations.map(a => [a.id, a])), [order.allocations]);
  const lines: ArrangedLine[] = (order.lines ?? []).map(line => ({
    key: line.id, line_no: line.line_no, target_spec_json: line.target_spec_json, planned_quantity: line.planned_quantity, unit: line.unit,
    allocations: line.allocation_ids.map(id => byId.get(id)).filter((a): a is Allocation => Boolean(a)).map(a => ({
      key: a.id, customer_name: a.customer_name, demand_number: a.demand_number, demand_item_line_no: a.demand_item_line_no, allocated_quantity: a.allocated_quantity, status: a.status,
      addedAfterStart: Boolean(a.added_after_start) })),
  }));

  // Demand items that could join this order (same product and unit, quantity left, not in it yet): the server searches
  // every demand and answers the first matches, so a demand far down the queue is found by its number or customer.
  useEffect(() => {
    if (!editing) return;
    let active = true;
    setSearching(true);
    const timer = setTimeout(() => {
      getEligibleDemandItems(order.id, search.trim()).then(found => { if (active) setCandidates(found); })
        .catch(() => { if (active) setCandidates([]); }).finally(() => { if (active) setSearching(false); });
    }, search ? 250 : 0);
    return () => { active = false; clearTimeout(timer); };
  }, [editing, order.id, order.allocations, search]);
  const options = candidates.map(item => ({ id: item.production_demand_item_id, remaining: item.remaining_quantity,
    label: `${item.customer_name ?? "—"} · ${item.demand_number} · ${d("lineNo")} ${item.line_no} — ${t("remaining")}: ${item.remaining_quantity} ${item.unit}` }));
  const chosen = useMemo(() => options.find(o => o.id === addItem), [options, addItem]);

  async function run(action: () => Promise<unknown>) {
    setBusy(true); setError("");
    try { await action(); setDrafts({}); onChanged?.(); return true; }
    catch (e) { setError(lifecycleErrorCode(e)); return false; }
    finally { setBusy(false); }
  }
  async function add(event: FormEvent) {
    event.preventDefault();
    if (!addItem || !QUANTITY.test(addQuantity)) return;
    if (await run(() => addOrderAllocation(order.id, addItem, addQuantity))) { setAddItem(""); setAddQuantity(""); }
  }

  if (!lines.length && !editing) return null;
  const hint = !editing ? t("arrangementHint") : order.editable ? t("orderLinesEditHint") : t("orderLinesStartedHint");
  return <section className={s.panel}><h2>{t("orderLines")}</h2>
    <p className={s.muted}>{hint}</p>
    {error && <p role="alert" className={s.error}>{t(`errors.${t.has(`errors.${error}`) ? error : "request_failed"}`)}</p>}
    <ArrangementTable lines={lines} caption={t("orderLines")}
      quantityCell={editing ? (a, line) => a.status === "released" ? `${a.allocated_quantity} ${line.unit}` : (() => {
        const value = drafts[a.key] ?? a.allocated_quantity;
        const changed = value !== a.allocated_quantity;
        return <span className={s.actions}>
          <input aria-label={`${t("quantity")} ${a.demand_number} ${a.demand_item_line_no}`} type="number" min="0.001" step="0.001" value={value} disabled={busy}
            onChange={e => setDrafts(old => ({ ...old, [a.key]: e.target.value }))} /> {line.unit}
          {changed && <button type="button" className={`${s.button} ${s.primary}`} disabled={busy || !QUANTITY.test(value) || Number(value) <= 0}
            onClick={() => run(() => changeAllocationQuantity(a.key, value))}>{t("saveQuantity")}</button>}
        </span>;
      })() : undefined}
      actionsCell={releasing_allowed ? a => a.status === "released" ? null : <button type="button" className={s.button} disabled={busy} onClick={() => setReleasing(byId.get(a.key) ?? null)}>{t("removeFromOrder")}</button> : undefined} />
    {editing && <form className={s.toolbar} onSubmit={add} aria-label={t("addDemand")} style={{ marginTop: 16 }}>
      <label className={s.field}>{t("findDemand")}
        <input type="search" value={search} disabled={busy} placeholder={t("findDemandHint")} onChange={e => setSearch(e.target.value)} />
      </label>
      <label className={s.field}>{t("addDemand")}
        <select value={addItem} disabled={busy} onChange={e => { setAddItem(e.target.value); setAddQuantity(options.find(o => o.id === e.target.value)?.remaining ?? ""); }}>
          <option value="">{searching ? t("searching") : options.length ? t("selectDemandItem") : search.trim() ? t("noMatches") : t("noCandidates")}</option>
          {/* The chosen item stays listed while another search runs. */}
          {addItem && !chosen && <option value={addItem}>{t("chosenItem")}</option>}
          {options.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}
        </select>
      </label>
      <label className={s.field}>{t("quantity")}<input type="number" min="0.001" step="0.001" value={addQuantity} disabled={busy || !addItem} onChange={e => setAddQuantity(e.target.value)} /></label>
      <button className={`${s.button} ${s.primary}`} disabled={busy || !addItem || !QUANTITY.test(addQuantity) || Number(addQuantity) <= 0}>{t("addToOrder")}</button>
    </form>}
    {releasing && <ReasonDialog title={t("releaseTitle", { order: order.production_order_number })} description={t("releaseHint")} confirmLabel={t("release")} busy={busy}
      onClose={() => setReleasing(null)}
      onConfirm={reason => run(() => demandsApi.releaseAllocation(releasing.id, reason)).then(() => setReleasing(null))} />}
  </section>;
}
