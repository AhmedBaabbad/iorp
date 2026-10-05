"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useState, type FormEvent } from "react";

import { UnitSelect } from "@/components/forms/UnitSelect";
import { PageFrame } from "@/components/layout/page-frame";
import s from "@/features/production-demands/demands.module.css";
import { createNcrReport, getNcrReport, getNcrSuppliers, getNcrUsers, updateNcrReport } from "../api";
import { DECIMAL, MONEY, ncrErrorMessage, todayIso } from "../ncr-errors";
import {
  CLAIM_STATUSES, COSTS, DISPOSITIONS, NCR_SOURCES, NCR_TYPES, SEVERITIES, SUPPLIER_ACTIONS, SUPPLIER_SOURCES,
  type NcrHeader, type NcrItemInput, type NcrReportType, type NcrSeverity, type NcrSourceType, type UserOption,
} from "../types";

type Text = { [K in Exclude<keyof NcrHeader, "source_type" | "report_type" | "severity" | "supplier_action" | "claim_status">]: string };
const EMPTY: Text = { report_date: "", title: "", description: "", reference_code: "", customer_name: "", supplier_id: "", supplier_name: "", supplier_reference: "",
  owner_user_id: "", due_date: "", supplier_response: "", supplier_responded_at: "", cost_material: "", cost_labor: "", cost_scrap: "",
  cost_transport: "", cost_other: "", claim_amount: "" };
type Item = { [K in keyof NcrItemInput]: string };
const EMPTY_ITEM: Item = { item_name: "", item_reference: "", quantity_affected: "", unit: "", issue_description: "", disposition: "", disposition_notes: "", notes: "" };
const blank = (v: string) => v.trim() || null;

// A non-conformance report: open one (with what it affects), or edit its details while it is not closed.
export function NcrReportForm({ reportId }: { reportId?: string }) {
  const t = useTranslations("ncr");
  const errors = useTranslations("ncr.errors");
  const messages = useTranslations("messages");
  const router = useRouter();
  const params = useSearchParams();
  const editing = Boolean(reportId);
  // Opened from a supplier or a goods receipt: the supplier, the receipt and lot, and the item are filled in.
  const [v, setV] = useState<Text>({ ...EMPTY, report_date: todayIso(), supplier_id: params.get("supplier") ?? "", reference_code: params.get("reference") ?? "" });
  const [suppliers, setSuppliers] = useState<{ id: string; supplier_code: string; name: string }[]>([]);
  const [source, setSource] = useState<NcrSourceType>("incoming_material");
  const [type, setType] = useState<NcrReportType>("material_non_conformance");
  const [severity, setSeverity] = useState<NcrSeverity>("major");
  const [supplierAction, setSupplierAction] = useState<(typeof SUPPLIER_ACTIONS)[number]>("none");
  const [claim, setClaim] = useState<(typeof CLAIM_STATUSES)[number]>("none");
  const [items, setItems] = useState<Item[]>([{ ...EMPTY_ITEM, item_name: params.get("item") ?? "", item_reference: params.get("reference") ?? "" }]);
  const [users, setUsers] = useState<UserOption[]>([]);
  const [locked, setLocked] = useState(false);
  const [loading, setLoading] = useState(editing);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => { getNcrUsers().then(setUsers).catch(() => setUsers([])); }, []);
  useEffect(() => { getNcrSuppliers().then(setSuppliers).catch(() => setSuppliers([])); }, []);
  useEffect(() => {
    if (!reportId) return;
    let active = true;
    getNcrReport(reportId).then(r => {
      if (!active) return;
      setV(Object.fromEntries(Object.keys(EMPTY).map(k => [k, r[k as keyof Text] === null ? "" : String(r[k as keyof Text])])) as Text);
      setSource(r.source_type); setType(r.report_type); setSeverity(r.severity); setSupplierAction(r.supplier_action); setClaim(r.claim_status);
      setLocked(!r.actions.includes("edit"));
    }).catch(e => { if (active) setError(ncrErrorMessage(e, errors)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [reportId, errors]);

  const set = (field: keyof Text, value: string) => setV(old => ({ ...old, [field]: value }));
  const setItem = (i: number, field: keyof Item, value: string) => setItems(old => old.map((item, n) => (n === i ? { ...item, [field]: value } : item)));
  const supplier = SUPPLIER_SOURCES.includes(source);
  const moneyOk = [...COSTS, "claim_amount" as const].every(k => !v[k].trim() || MONEY.test(v[k].trim()));
  const itemsOk = editing || items.every(i => (!i.item_name.trim() && !i.issue_description.trim())
    || (i.item_name.trim() && i.issue_description.trim() && (!i.quantity_affected.trim() || DECIMAL.test(i.quantity_affected.trim()))));
  const valid = Boolean(v.report_date && v.title.trim() && v.description.trim()) && moneyOk && itemsOk;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!valid || busy || locked) return;
    setBusy(true); setError("");
    const header = { ...Object.fromEntries(Object.entries(v).map(([k, value]) => [k, blank(value)])), report_date: v.report_date, title: v.title.trim(),
      description: v.description.trim(), source_type: source, report_type: type, severity, supplier_action: supplierAction, claim_status: claim } as NcrHeader;
    try {
      const saved = reportId ? await updateNcrReport(reportId, header) : await createNcrReport({ ...header,
        items: items.filter(i => i.item_name.trim()).map(i => ({ item_name: i.item_name.trim(), item_reference: blank(i.item_reference),
          quantity_affected: blank(i.quantity_affected), unit: blank(i.unit), issue_description: i.issue_description.trim(),
          disposition: (blank(i.disposition) as NcrItemInput["disposition"]), disposition_notes: blank(i.disposition_notes), notes: null })) });
      router.push(`/non-conformance-reports/${saved.id}`);
    } catch (e) { setError(ncrErrorMessage(e, errors)); setBusy(false); }
  }

  const input = (field: keyof Text, extra: Record<string, unknown> = {}) =>
    <label className={s.field}>{t(`fields.${field}`)}<input value={v[field]} onChange={e => set(field, e.target.value)} {...extra} /></label>;
  const back = reportId ? `/non-conformance-reports/${reportId}` : "/non-conformance-reports";
  const title = editing ? t("editTitle") : t("createTitle");

  return <PageFrame title={title} subtitle={t("formSubtitle")} action={<Link href={back} className={s.button}>{t("back")}</Link>}>
    {loading ? <p className={s.muted}>{messages("loading.default")}</p> : <form onSubmit={submit} aria-label={title}>
      {locked && <p role="status" className={s.error}>{t("lockedHint")}</p>}
      <fieldset disabled={busy || locked} style={{ border: 0, padding: 0, margin: 0 }}>
        <section className={s.panel}>
          <h2 style={{ marginTop: 0 }}>{t("sections.report")}</h2>
          <div className={s.grid}>
            {input("report_date", { type: "date", required: true })}
            <label className={s.field}>{t("fields.source_type")}
              <select value={source} onChange={e => setSource(e.target.value as NcrSourceType)}>{NCR_SOURCES.map(o => <option key={o} value={o}>{t(`sources.${o}`)}</option>)}</select></label>
            <label className={s.field}>{t("fields.report_type")}
              <select value={type} onChange={e => setType(e.target.value as NcrReportType)}>{NCR_TYPES.map(o => <option key={o} value={o}>{t(`types.${o}`)}</option>)}</select></label>
            <label className={s.field}>{t("fields.severity")}
              <select value={severity} onChange={e => setSeverity(e.target.value as NcrSeverity)}>{SEVERITIES.map(o => <option key={o} value={o}>{t(`severities.${o}`)}</option>)}</select></label>
            {input("reference_code", { maxLength: 255, dir: "auto", placeholder: t("placeholders.reference") })}
          </div>
          <p className={s.muted}>{t(`sourceHints.${source}`)}</p>
          {input("title", { required: true, maxLength: 255 })}
          <label className={s.field}>{t("fields.description")}<textarea required maxLength={8000} value={v.description} onChange={e => set("description", e.target.value)} /></label>
        </section>

        <section className={s.panel}>
          <h2 style={{ marginTop: 0 }}>{supplier ? t("sections.supplier") : t("sections.party")}</h2>
          <div className={s.grid}>
            {supplier ? <>
              <label className={s.field}>{t("fields.registered_supplier")}
                <select value={v.supplier_id} onChange={e => set("supplier_id", e.target.value)}>
                  <option value="">{t("placeholders.unregisteredSupplier")}</option>
                  {suppliers.map(o => <option key={o.id} value={o.id}>{o.name} — {o.supplier_code}</option>)}</select></label>
              {!v.supplier_id && input("supplier_name", { maxLength: 255 })}
              {input("supplier_reference", { maxLength: 120, dir: "auto", placeholder: t("placeholders.supplierReference") })}
              <label className={s.field}>{t("fields.supplier_action")}
                <select value={supplierAction} onChange={e => setSupplierAction(e.target.value as (typeof SUPPLIER_ACTIONS)[number])}>
                  {SUPPLIER_ACTIONS.map(o => <option key={o} value={o}>{t(`supplierActions.${o}`)}</option>)}</select></label>
            </> : input("customer_name", { maxLength: 255 })}
            <label className={s.field}>{t("fields.owner")}
              <select value={v.owner_user_id} onChange={e => set("owner_user_id", e.target.value)}>
                <option value="">{t("placeholders.noOwner")}</option>{users.map(u => <option key={u.id} value={u.id}>{u.name}</option>)}</select></label>
            {input("due_date", { type: "date" })}
          </div>
          {supplier && supplierAction !== "none" && <>
            <p className={s.muted}>{t(`supplierActionHints.${supplierAction}`)}</p>
            {editing && <div className={s.grid}>
              <label className={s.field} style={{ gridColumn: "1 / -1" }}>{t("fields.supplier_response")}
                <textarea maxLength={4000} value={v.supplier_response} onChange={e => set("supplier_response", e.target.value)} /></label>
              {input("supplier_responded_at", { type: "date" })}
            </div>}
          </>}
        </section>

        {!editing && <section className={s.panel} aria-label={t("sections.items")}>
          <h2 style={{ marginTop: 0 }}>{t("sections.items")}</h2>
          {items.map((item, i) => <div key={i} className={s.panel} style={{ margin: "0 0 10px", padding: 14 }}>
            <div className={s.actions} style={{ justifyContent: "space-between", marginBottom: 8 }}>
              <strong>{t("itemNo", { no: String(i + 1) })}</strong>
              {items.length > 1 && <button type="button" className={`${s.button} ${s.danger}`} onClick={() => setItems(old => old.filter((_, n) => n !== i))}>{t("remove")}</button>}
            </div>
            <div className={s.grid}>
              <label className={s.field}>{t("itemFields.item_name")}<input maxLength={255} value={item.item_name} onChange={e => setItem(i, "item_name", e.target.value)} /></label>
              <label className={s.field}>{t("itemFields.item_reference")}<input maxLength={255} dir="auto" value={item.item_reference} onChange={e => setItem(i, "item_reference", e.target.value)} /></label>
              <label className={s.field}>{t("itemFields.quantity_affected")}<input inputMode="decimal" dir="ltr" value={item.quantity_affected} onChange={e => setItem(i, "quantity_affected", e.target.value)} /></label>
              <label className={s.field}>{t("itemFields.unit")}<UnitSelect value={item.unit} onChange={u => setItem(i, "unit", u)} ariaLabel={t("itemFields.unit")} placeholder="—" required={false} /></label>
              <label className={s.field}>{t("itemFields.disposition")}
                <select value={item.disposition} onChange={e => setItem(i, "disposition", e.target.value)}>
                  <option value="">{t("placeholders.undecided")}</option>{DISPOSITIONS.map(o => <option key={o} value={o}>{t(`dispositions.${o}`)}</option>)}</select></label>
              <label className={s.field} style={{ gridColumn: "1 / -1" }}>{t("itemFields.issue_description")}
                <textarea maxLength={4000} value={item.issue_description} onChange={e => setItem(i, "issue_description", e.target.value)} /></label>
            </div>
          </div>)}
          <button type="button" className={s.button} onClick={() => setItems(old => [...old, { ...EMPTY_ITEM }])}>{t("addItem")}</button>
          {!itemsOk && <p className={s.muted}>{t("itemsHint")}</p>}
        </section>}

        <section className={s.panel}>
          <h2 style={{ marginTop: 0 }}>{t("sections.costs")}</h2>
          <p className={s.muted} style={{ marginTop: 0 }}>{t("costsHint")}</p>
          <div className={s.grid}>
            {COSTS.map(k => <label key={k} className={s.field}>{t(`fields.${k}`)}<input inputMode="decimal" dir="ltr" value={v[k]} onChange={e => set(k, e.target.value)} /></label>)}
            <label className={s.field}>{t("fields.claim_amount")}<input inputMode="decimal" dir="ltr" value={v.claim_amount} onChange={e => set("claim_amount", e.target.value)} /></label>
            <label className={s.field}>{t("fields.claim_status")}
              <select value={claim} onChange={e => setClaim(e.target.value as (typeof CLAIM_STATUSES)[number])}>{CLAIM_STATUSES.map(o => <option key={o} value={o}>{t(`claims.${o}`)}</option>)}</select></label>
          </div>
          {!moneyOk && <p className={s.error}>{t("moneyHint")}</p>}
        </section>
      </fieldset>
      {error && <p role="alert" className={s.error}>{error}</p>}
      <div className={s.actions}>
        <button type="submit" className={`${s.button} ${s.primary}`} disabled={!valid || busy || locked}>{editing ? t("save") : t("create")}</button>
        <Link href={back} className={s.button}>{t("cancel")}</Link>
      </div>
    </form>}
  </PageFrame>;
}
