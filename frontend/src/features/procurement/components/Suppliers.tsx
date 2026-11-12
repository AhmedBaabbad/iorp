"use client";

import Link from "next/link";
import { cityLabel } from "@/components/forms/CountryCityFields";
import { useRouter } from "next/navigation";
import { useTranslations, useLocale } from "next-intl";
import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";

import { FormSection } from "@/components/forms/FormSection";
import { DirectoryPanel } from "@/features/reference-directory/DirectoryPanel";
import { PageFrame } from "@/components/layout/page-frame";
import { usePermission } from "@/features/auth/permission-hooks";
import s from "@/features/production-demands/demands.module.css";
import { useFormatter } from "@/hooks/useFormatter";
import { PR } from "@/lib/procurement-permissions";
import { Q } from "@/lib/quality-permissions";
import { createSupplier, getSupplier, getSuppliers, setSupplierStatus, updateSupplier, type SupplierFilters } from "../api";
import { procurementErrorMessage } from "../procurement-errors";
import { SUPPLIER_CATEGORIES, SUPPLIER_STATUSES, type Evaluation, type Supplier, type SupplierInput, type SupplierStatus } from "../types";
import { ListSelect, useListChoices, useListName } from "@/features/masterdata";

import { joinList } from "@/lib/utils";
import { Signatures } from "@/components/Signatures";
const STATUS_CLASS: Record<SupplierStatus, string> = { pending: s.high, approved: s.green, conditional: s.overdue, blocked: s.cancelled };

const GRADE_CLASS: Record<string, string> = { A: s.green, B: s.blue, C: s.overdue, D: s.cancelled };

export function GradeBadge({ evaluation }: { evaluation: Evaluation | null }) {
  const t = useTranslations("procurement.evaluation");
  if (!evaluation?.grade) return <span className={s.muted}>{t("notScored")}</span>;
  return <span className={`${s.badge} ${GRADE_CLASS[evaluation.grade]}`}>{evaluation.grade} · {Number(evaluation.score)}</span>;
}

export function SupplierStatusBadge({ status }: { status: SupplierStatus }) {
  const t = useTranslations("procurement.supplierStatuses");
  return <span className={`${s.badge} ${STATUS_CLASS[status]}`}>{t(status)}</span>;
}

function Item({ label, children }: { label: string; children: ReactNode }) {
  return <div><dt className={s.muted}>{label}</dt><dd style={{ margin: "4px 0 0", overflowWrap: "anywhere", whiteSpace: "pre-wrap" }}>{children}</dd></div>;
}

// "الموردون": the approved supplier list — who supplies what, its standing, and how it performs.
export function SuppliersList() {
  const t = useTranslations("procurement");
  const supplierCategory = useListName("supplier_category", (k) => (t.has(`supplierCategories.${k}`) ? t(`supplierCategories.${k}`) : undefined));
  const errors = useTranslations("procurement.errors");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const canCreate = usePermission(PR.SUPPLIERS_CREATE);
  const [filters, setFilters] = useState<Required<SupplierFilters>>({ status: "", category: "", search: "" });
  const categoryChoices = useListChoices("supplier_category", SUPPLIER_CATEGORIES, supplierCategory, filters.category);
  const [rows, setRows] = useState<Supplier[] | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    setError("");
    try { setRows(await getSuppliers(filters)); } catch (e) { setError(procurementErrorMessage(e, errors)); }
  }, [filters, errors]);
  useEffect(() => { const timer = setTimeout(() => void load(), 200); return () => clearTimeout(timer); }, [load]);
  const set = (field: keyof SupplierFilters, value: string) => setFilters(old => ({ ...old, [field]: value }));

  return <PageFrame title={t("suppliers.title")} subtitle={t("suppliers.subtitle")}
    action={canCreate ? <Link href="/suppliers/new" className={`${s.button} ${s.primary}`}>{t("suppliers.new")}</Link> : undefined}>
    <section className={s.toolbar} aria-label={t("filtersAria")}>
      <label className={s.field}>{t("search")}<input type="search" value={filters.search} placeholder={t("suppliers.searchPlaceholder")}
        onChange={e => set("search", e.target.value)} /></label>
      <label className={s.field}>{t("fields.status")}
        <select value={filters.status} onChange={e => set("status", e.target.value)}>
          <option value="">{t("all")}</option>{SUPPLIER_STATUSES.map(v => <option key={v} value={v}>{t(`supplierStatuses.${v}`)}</option>)}</select></label>
      <label className={s.field}>{t("fields.category")}
        <select value={filters.category} onChange={e => set("category", e.target.value)}>
          <option value="">{t("all")}</option>{categoryChoices.map(c => <option key={c.key} value={c.key}>{c.label}</option>)}</select></label>
    </section>
    {error && <p role="alert" className={s.error}>{error}</p>}
    {rows === null && !error && <p className={s.muted}>{messages("loading.default")}</p>}
    {rows?.length === 0 && <section className={s.panel}><h2 style={{ marginTop: 0 }}>{t("suppliers.empty")}</h2><p className={s.muted} style={{ margin: 0 }}>{t("suppliers.emptyHint")}</p></section>}
    {rows && rows.length > 0 && <section className={s.panel}><div className={s.tableWrap}><table className={s.table} aria-label={t("suppliers.title")}>
      <thead><tr>{["code", "name", "category", "supplies", "receipts", "ncr", "grade", "status"].map(c => <th key={c}>{t(`fields.${c}`)}</th>)}</tr></thead>
      <tbody>{rows.map(r => <tr key={r.id}>
        <td><Link href={`/suppliers/${r.id}`}><bdi>{r.supplier_code}</bdi></Link></td>
        <td>{r.name}{r.contact_name && <div className={s.muted}>{r.contact_name}</div>}</td>
        <td>{supplierCategory(r.category)}</td>
        <td>{r.supplies ?? "—"}</td>
        <td>{r.receipts_count}{r.last_receipt_date && <div className={s.muted}>{fmt.date(r.last_receipt_date)}</div>}</td>
        <td className={r.open_ncr_count ? s.error : undefined}>{r.ncr_count}{r.open_ncr_count > 0 && <div>{t("openNcr", { count: String(r.open_ncr_count) })}</div>}</td>
        <td><GradeBadge evaluation={r.evaluation} /></td>
        <td><SupplierStatusBadge status={r.status} /></td>
      </tr>)}</tbody>
    </table></div></section>}
  </PageFrame>;
}

type Text = { [K in keyof Omit<SupplierInput, "category">]-?: string };
const EMPTY: Text = { name: "", supplies: "", contact_name: "", phone: "", email: "", address: "", city: "", city_other: "", country: "sa", vat_number: "", cr_number: "", notes: "" };

// A supplier: register one (pending evaluation), or edit its details.
export function SupplierForm({ supplierId }: { supplierId?: string }) {
  const location = useTranslations("common.location");
  const t = useTranslations("procurement");
  const supplierCategory = useListName("supplier_category", (k) => (t.has(`supplierCategories.${k}`) ? t(`supplierCategories.${k}`) : undefined));
  const errors = useTranslations("procurement.errors");
  const messages = useTranslations("messages");
  const router = useRouter();
  const [v, setV] = useState<Text>(EMPTY);
  const [category, setCategory] = useState<SupplierInput["category"]>("raw_material");
  const categoryChoices = useListChoices("supplier_category", SUPPLIER_CATEGORIES, supplierCategory, category);
  const [loading, setLoading] = useState(Boolean(supplierId));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!supplierId) return;
    let active = true;
    getSupplier(supplierId).then(x => {
      if (!active) return;
      setV(Object.fromEntries(Object.keys(EMPTY).map(k => [k, (x[k as keyof Text] as string | null) ?? ""])) as Text);
      setCategory(x.category);
    }).catch(e => { if (active) setError(procurementErrorMessage(e, errors)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [supplierId, errors]);
  const set = (field: keyof Text, value: string) => setV(old => ({ ...old, [field]: value }));
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!v.name.trim() || busy) return;
    setBusy(true); setError("");
    const body = { ...Object.fromEntries(Object.entries(v).map(([k, value]) => [k, value.trim() || null])), name: v.name.trim(), category } as SupplierInput;
    try {
      const saved = supplierId ? await updateSupplier(supplierId, body) : await createSupplier(body);
      router.push(`/suppliers/${saved.id}`);
    } catch (e) { setError(procurementErrorMessage(e, errors)); setBusy(false); }
  }
  const input = (field: keyof Text, extra: Record<string, unknown> = {}) =>
    <label className={s.field}>{t(`fields.${field}`)}<input value={v[field]} onChange={e => set(field, e.target.value)} {...extra} /></label>;
  const title = supplierId ? t("suppliers.editTitle") : t("suppliers.createTitle");
  const back = supplierId ? `/suppliers/${supplierId}` : "/suppliers";
  return <PageFrame title={title} subtitle={t("suppliers.formSubtitle")} action={<Link href={back} className={s.button}>{t("back")}</Link>}>
    {loading ? <p className={s.muted}>{messages("loading.default")}</p> : <form onSubmit={submit} aria-label={title}>
      <fieldset disabled={busy} style={{ border: 0, padding: 0, margin: 0 }}>
        <FormSection title={t("suppliers.detailsSection")}>
          {input("name", { required: true, maxLength: 255 })}
          <label className={s.field}>{t("fields.category")}
            <select value={category} onChange={e => setCategory(e.target.value)}>
              {categoryChoices.map(c => <option key={c.key} value={c.key}>{c.label}</option>)}</select></label>
          {input("supplies", { maxLength: 500, placeholder: t("suppliers.suppliesPlaceholder") })}
          {input("contact_name", { maxLength: 200 })}
          {input("phone", { maxLength: 30, dir: "ltr", inputMode: "tel", placeholder: "05xxxxxxxx" })}
          {input("email", { maxLength: 255, dir: "ltr", type: "email" })}
          <label className={s.field}>{t("fields.country")}<ListSelect list="country" ariaLabel={t("fields.country")} value={v.country}
            onChange={country => setV(old => ({...old, country, city: "", city_other: ""}))} /></label>
          <label className={s.field}>{t("fields.city")}<ListSelect list="city" ariaLabel={t("fields.city")} value={v.city} parent={v.country || null}
            disabled={!v.country} onChange={city => setV(old => ({...old, city, city_other: ""}))} /></label>
          {v.city.endsWith("_other") && <label className={s.field}>{location("cityName")}<input required maxLength={120} value={v.city_other}
            onChange={e => set("city_other", e.target.value)} /></label>}
          {input("vat_number", { maxLength: 40, dir: "ltr" })}
          {input("cr_number", { maxLength: 40, dir: "ltr" })}
          <label className={s.field}>{t("fields.address")}<textarea maxLength={1000} value={v.address} onChange={e => set("address", e.target.value)} /></label>
          <label className={s.field}>{t("fields.notes")}<textarea maxLength={4000} value={v.notes} onChange={e => set("notes", e.target.value)} /></label>
        </FormSection>
      </fieldset>
      {error && <p role="alert" className={s.error}>{error}</p>}
      <div className={s.actions}>
        <button type="submit" className={`${s.button} ${s.primary}`} disabled={busy || !v.name.trim()}>{t("save")}</button>
        <Link href={back} className={s.button}>{t("cancel")}</Link>
      </div>
    </form>}
  </PageFrame>;
}

// One supplier: details, standing on the approved list, receipts and the non-conformance reports raised about it.
export function SupplierDetail({ supplierId }: { supplierId: string }) {
  const t = useTranslations("procurement");
  const supplierCategory = useListName("supplier_category", (k) => (t.has(`supplierCategories.${k}`) ? t(`supplierCategories.${k}`) : undefined));
  const ncr = useTranslations("ncr.statuses");
  const errors = useTranslations("procurement.errors");
  const messages = useTranslations("messages");
  const locale = useLocale();
  const cityName = useListName("city");  // MD-002: names, not keys
  const countryName = useListName("country");
  const fmt = useFormatter();
  const canReceive = usePermission(PR.RECEIPTS_CREATE);
  const canOrder = usePermission(PR.PO_CREATE);
  const canNcr = usePermission(Q.NCR_CREATE);
  const [x, setX] = useState<Supplier | null>(null);
  const [loading, setLoading] = useState(true);
  const [dialog, setDialog] = useState(false);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    try { setX(await getSupplier(supplierId)); } catch (e) { setError(procurementErrorMessage(e, errors)); } finally { setLoading(false); }
  }, [supplierId, errors]);
  useEffect(() => { void load(); }, [load]);
  const back = <Link href="/suppliers" className={s.button}>{t("suppliers.back")}</Link>;
  if (loading) return <PageFrame title={t("suppliers.detailTitle")} action={back}><p className={s.muted}>{messages("loading.default")}</p></PageFrame>;
  if (!x) return <PageFrame title={t("suppliers.detailTitle")} action={back}><p role="alert" className={s.error}>{error || t("suppliers.notFound")}</p></PageFrame>;

  return <PageFrame title={x.name} subtitle={`${x.supplier_code} — ${supplierCategory(x.category)}`} action={back}>
    <DirectoryPanel kind="contacts" path={`/procurement/suppliers/${x.id}/contacts`} writePermission="procurement:suppliers:update"/>
    {error && <p role="alert" className={s.error}>{error}</p>}
    {x.status === "blocked" && <p role="status" className={s.error}>{t("suppliers.blockedHint", { reason: x.status_reason ?? "" })}</p>}
    <section className={s.panel}>
      <div className={s.actions} style={{ justifyContent: "space-between", marginBottom: 12 }}>
        <SupplierStatusBadge status={x.status} />
        <span className={s.actions}>
          {x.actions.includes("edit") && <Link href={`/suppliers/${x.id}/edit`} className={s.button}>{t("edit")}</Link>}
          {x.actions.includes("set_status") && <button type="button" className={s.button} onClick={() => setDialog(true)}>{t("suppliers.setStatus")}</button>}
          {canOrder && x.status !== "blocked" && <Link href={`/purchase-orders/new?supplier=${x.id}`} className={`${s.button} ${s.primary}`}>{t("orders.new")}</Link>}
          {canReceive && x.status !== "blocked" && <Link href={`/goods-receipts/new?supplier=${x.id}`} className={`${s.button} ${s.primary}`}>{t("receipts.new")}</Link>}
          {canNcr && <Link href={`/non-conformance-reports/new?supplier=${x.id}`} className={s.button}>{t("suppliers.newNcr")}</Link>}
        </span>
      </div>
      <dl className={s.grid} style={{ margin: 0 }}>
        <Item label={t("fields.supplies")}>{x.supplies ?? "—"}</Item>
        <Item label={t("fields.contact_name")}>{x.contact_name ?? "—"}</Item>
        <Item label={t("fields.phone")}><bdi dir="ltr">{x.phone ?? "—"}</bdi></Item>
        <Item label={t("fields.email")}><bdi dir="ltr">{x.email ?? "—"}</bdi></Item>
        <Item label={t("fields.city")}>{joinList([x.city ? cityLabel(x.city, x.city_other, cityName) : null, x.country ? countryName(x.country) : null], locale) || "—"}</Item>
        <Item label={t("fields.vat_number")}><bdi dir="ltr">{x.vat_number ?? "—"}</bdi></Item>
        <Item label={t("fields.cr_number")}><bdi dir="ltr">{x.cr_number ?? "—"}</bdi></Item>
        {x.status_changed_at && <Item label={t("suppliers.standing")}>{x.status_changed_by_name} · {fmt.dateTime(x.status_changed_at)}
          {x.status_reason && <div>{x.status_reason}</div>}</Item>}
      </dl>
      {x.address && <p style={{ whiteSpace: "pre-wrap" }}>{x.address}</p>}
    </section>
    <section className={s.panel} aria-label={t("suppliers.performance")}>
      <h2 style={{ marginTop: 0 }}>{t("suppliers.performance")}</h2>
      <dl className={s.grid} style={{ margin: 0 }}>
        <Item label={t("suppliers.receiptsCount")}>{x.receipts_count}</Item>
        <Item label={t("suppliers.lastReceipt")}>{x.last_receipt_date ? fmt.date(x.last_receipt_date) : "—"}</Item>
        <Item label={t("suppliers.ncrCount")}>{x.ncr_count}</Item>
        <Item label={t("suppliers.openNcrCount")}><span className={x.open_ncr_count ? s.error : undefined}>{x.open_ncr_count}</span></Item>
      </dl>
    </section>
    {x.evaluation && <EvaluationPanel value={x.evaluation} status={x.status} />}
    {x.recent_receipts.length > 0 && <section className={s.panel} aria-label={t("receipts.title")}>
      <h2 style={{ marginTop: 0 }}>{t("receipts.title")}</h2>
      <ul style={{ margin: 0, paddingInlineStart: 18, display: "grid", gap: 4 }}>{x.recent_receipts.map(r => <li key={r.id}>
        <Link href={`/goods-receipts/${r.id}`}><bdi>{r.receipt_no}</bdi></Link> · {fmt.date(r.receipt_date)} · {t(`receiptStatuses.${r.status}`)}</li>)}</ul>
    </section>}
    {x.non_conformances.length > 0 && <section className={s.panel} aria-label={t("suppliers.ncrTitle")}>
      <h2 style={{ marginTop: 0 }}>{t("suppliers.ncrTitle")}</h2>
      <ul style={{ margin: 0, paddingInlineStart: 18, display: "grid", gap: 4 }}>{x.non_conformances.map(n => <li key={n.id}>
        <Link href={`/non-conformance-reports/${n.id}`}><bdi>{n.report_number}</bdi></Link> · {n.title} · {ncr.has(n.status) ? ncr(n.status) : n.status}</li>)}</ul>
    </section>}
    {x.notes && <section className={s.panel}><p style={{ margin: 0, whiteSpace: "pre-wrap" }}>{x.notes}</p></section>}
    <Signatures resourceType="supplier" id={x.id} version={x.status} />
    <section className={s.panel} aria-label={t("historyTitle")}>
      <h2 style={{ marginTop: 0 }}>{t("historyTitle")}</h2>
      <ol className={s.timeline}>{x.history.map((e, i) => <li key={`${e.at}-${i}`}>
        <strong>{e.action === "status" && e.to_status ? t(`supplierStatuses.${e.to_status}`) : t.has(`events.${e.action}`) ? t(`events.${e.action}`) : e.action}</strong>
        <span className={s.muted}>{e.actor_name ?? "—"} · {fmt.dateTime(e.at)}</span>
        {e.reason && <span style={{ whiteSpace: "pre-wrap" }}>{e.reason}</span>}
      </li>)}</ol>
    </section>
    {dialog && <StatusDialog current={x.status} onClose={() => setDialog(false)} onConfirm={async (status, reason) => {
      try { setX(await setSupplierStatus(x.id, status, reason)); setDialog(false); } catch (e) { setError(procurementErrorMessage(e, errors)); setDialog(false); }
    }} />}
  </PageFrame>;
}

function StatusDialog({ current, onClose, onConfirm }: { current: SupplierStatus; onClose: () => void;
  onConfirm: (status: Exclude<SupplierStatus, "pending">, reason: string | null) => Promise<void> }) {
  const t = useTranslations("procurement");
  const [status, setStatus] = useState<Exclude<SupplierStatus, "pending">>(current === "approved" ? "conditional" : "approved");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const needsReason = status !== "approved";
  const ok = status !== current && (!needsReason || Boolean(reason.trim()));
  return <div className={s.overlay} onKeyDown={e => { if (e.key === "Escape" && !busy) onClose(); }}>
    <form role="dialog" aria-modal="true" aria-label={t("suppliers.setStatus")} className={`${s.panel} ${s.dialog}`}
      onSubmit={async e => { e.preventDefault(); if (!ok || busy) return; setBusy(true); await onConfirm(status, reason.trim() || null); setBusy(false); }}>
      <h2 style={{ margin: 0 }}>{t("suppliers.setStatus")}</h2>
      <div className={s.actions} role="radiogroup" aria-label={t("fields.status")}>
        {(["approved", "conditional", "blocked"] as const).map(v => <label key={v}>
          <input type="radio" checked={status === v} disabled={busy || v === current} onChange={() => setStatus(v)} /> {t(`supplierStatuses.${v}`)}</label>)}
      </div>
      <p className={s.muted} style={{ margin: 0 }}>{t(`statusHints.${status}`)}</p>
      <label className={s.field}>{needsReason ? t("reasonRequired") : t("reasonOptional")}
        <textarea maxLength={2000} required={needsReason} value={reason} disabled={busy} onChange={e => setReason(e.target.value)} /></label>
      <div className={s.actions}>
        <button type="button" className={s.button} disabled={busy} onClick={onClose}>{t("cancel")}</button>
        <button type="submit" className={`${s.button} ${status === "blocked" ? s.danger : s.primary}`} disabled={busy || !ok}>{t("confirm")}</button>
      </div>
    </form>
  </div>;
}

// The supplier's score: lots released in full, less points for its non-conformance reports and their cost (PROC-002).
function EvaluationPanel({ value, status }: { value: Evaluation; status: SupplierStatus }) {
  const t = useTranslations("procurement.evaluation");
  const statuses = useTranslations("procurement.supplierStatuses");
  const fmt = useFormatter();
  const differs = value.suggested_status && value.suggested_status !== status;
  return <section className={s.panel} aria-label={t("title")}>
    <div className={s.actions} style={{ justifyContent: "space-between" }}>
      <h2 style={{ margin: 0 }}>{t("title")}</h2>
      <GradeBadge evaluation={value} />
    </div>
    <p className={s.muted}>{t("period", { months: String(value.months), since: fmt.date(value.since) })}</p>
    {value.score === null ? <p className={s.muted} style={{ margin: 0 }}>{t("noLots")}</p> : <dl className={s.grid} style={{ margin: 0 }}>
      <div><dt className={s.muted}>{t("lots")}</dt><dd style={{ margin: "4px 0 0" }}>{t("lotsValue", { released: String(value.lots_released),
        inspected: String(value.lots_inspected), pct: String(Number(value.acceptance_pct)) })}</dd></div>
      <div><dt className={s.muted}>{t("ncr")}</dt><dd style={{ margin: "4px 0 0" }}>{t("ncrValue", { count: String(value.ncr_count), points: String(value.ncr_penalty) })}</dd></div>
      <div><dt className={s.muted}>{t("cost")}</dt><dd style={{ margin: "4px 0 0" }}><bdi>{fmt.number(value.ncr_cost)}</bdi> — {t("points", { points: String(value.cost_penalty) })}</dd></div>
      <div><dt className={s.muted}>{t("score")}</dt><dd style={{ margin: "4px 0 0" }}><strong>{Number(value.score)} / 100</strong></dd></div>
    </dl>}
    {differs && <p role="status" className={s.error} style={{ marginBottom: 0 }}>{t("suggestion", { status: statuses(value.suggested_status!) })}</p>}
    <p className={s.muted} style={{ marginBottom: 0 }}>{t("formula")}</p>
  </section>;
}
