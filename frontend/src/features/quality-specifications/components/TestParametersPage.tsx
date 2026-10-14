"use client";
import { ReferenceTextSelect } from "@/features/reference-directory/ReferenceTextSelect";


import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { usePermission } from "@/features/auth/permission-hooks";
import s from "@/features/production-demands/demands.module.css";
import { qualityErrorMessage } from "@/features/quality-checks/components/quality-errors";
import { Q } from "@/lib/quality-permissions";
import { addStandardParameters, createParameter, getParameters, updateParameter } from "../api";
import type { ParameterKind, TestParameter } from "../types";

type Draft = { code: string; name_ar: string; name_en: string; kind: ParameterKind; unit: string; method: string };
const EMPTY: Draft = { code: "", name_ar: "", name_en: "", kind: "numeric", unit: "", method: "" };

// "خصائص الفحص": what the factory measures (numeric, in a unit) or checks visually (conforming / not).
export function TestParametersPage() {
  const t = useTranslations("quality.parameters");
  const errors = useTranslations("quality.errors");
  const messages = useTranslations("messages");
  const canCreate = usePermission(Q.SPECS_CREATE);
  const canUpdate = usePermission(Q.SPECS_UPDATE);
  const [rows, setRows] = useState<TestParameter[] | null>(null);
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [editing, setEditing] = useState<TestParameter | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try { setRows(await getParameters()); } catch (e) { setError(qualityErrorMessage(e, errors)); }
  }, [errors]);
  useEffect(() => { void load(); }, [load]);

  async function run(action: () => Promise<unknown>) {
    setBusy(true); setError("");
    try { await action(); await load(); return true; } catch (e) { setError(qualityErrorMessage(e, errors)); return false; } finally { setBusy(false); }
  }
  async function add(event: FormEvent) {
    event.preventDefault();
    const ok = await run(() => createParameter({ ...draft, unit: draft.kind === "numeric" ? draft.unit || null : null, method: draft.method || null,
      sort_order: (rows?.length ?? 0) * 10 + 10 }));
    if (ok) setDraft(EMPTY);
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    if (!editing) return;
    const ok = await run(() => updateParameter(editing.id, { name_ar: editing.name_ar, name_en: editing.name_en, unit: editing.unit || null,
      method: editing.method || null, is_active: editing.is_active }));
    if (ok) setEditing(null);
  }
  const set = (field: keyof Draft, value: string) => setDraft(old => ({ ...old, [field]: value }));

  return <PageFrame title={t("title")} subtitle={t("subtitle")}
    action={<Link href="/quality-specifications" className={s.button}>{t("toSpecifications")}</Link>}>
    {error && <p role="alert" className={s.error}>{error}</p>}
    {rows === null && !error && <p className={s.muted}>{messages("loading.default")}</p>}
    {rows !== null && rows.length === 0 && <section className={s.panel}>
      <h2 style={{ marginTop: 0 }}>{t("empty")}</h2>
      <p className={s.muted}>{t("emptyHint")}</p>
      {canCreate && <button type="button" className={`${s.button} ${s.primary}`} disabled={busy} onClick={() => void run(addStandardParameters)}>{t("addStandard")}</button>}
    </section>}
    {rows !== null && rows.length > 0 && <section className={s.panel}>
      <div className={s.tableWrap}><table className={s.table} aria-label={t("title")}>
        <thead><tr>{["code", "nameAr", "nameEn", "kind", "unit", "method", "status", ""].map(c => <th key={c}>{c && t(`fields.${c}`)}</th>)}</tr></thead>
        <tbody>{rows.map(p => editing?.id === p.id
          ? <tr key={p.id}>
            <td><bdi>{p.code}</bdi></td>
            <td><input aria-label={t("fields.nameAr")} value={editing.name_ar} onChange={e => setEditing({ ...editing, name_ar: e.target.value })} /></td>
            <td><input aria-label={t("fields.nameEn")} dir="ltr" value={editing.name_en} onChange={e => setEditing({ ...editing, name_en: e.target.value })} /></td>
            <td>{t(`kinds.${p.kind}`)}</td>
            <td>{p.kind === "numeric" ? <input aria-label={t("fields.unit")} dir="ltr" style={{ width: 70 }} value={editing.unit ?? ""}
              onChange={e => setEditing({ ...editing, unit: e.target.value })} /> : "—"}</td>
            <td><ReferenceTextSelect list="test_method" ariaLabel={t("fields.method")} value={editing.method??""} onChange={v=>setEditing({...editing,method:v})}/></td>
            <td><label><input type="checkbox" checked={editing.is_active} onChange={e => setEditing({ ...editing, is_active: e.target.checked })} /> {t("active")}</label></td>
            <td><form onSubmit={save} className={s.actions}>
              <button type="submit" className={`${s.button} ${s.primary}`} disabled={busy}>{t("save")}</button>
              <button type="button" className={s.button} disabled={busy} onClick={() => setEditing(null)}>{t("cancel")}</button>
            </form></td>
          </tr>
          : <tr key={p.id} style={p.is_active ? undefined : { opacity: 0.6 }}>
            <td><bdi>{p.code}</bdi></td><td>{p.name_ar}</td><td dir="ltr">{p.name_en}</td><td>{t(`kinds.${p.kind}`)}</td>
            <td>{p.unit ?? "—"}</td><td dir="ltr">{p.method ?? "—"}</td>
            <td><span className={`${s.badge} ${p.is_active ? s.green : ""}`}>{p.is_active ? t("active") : t("inactive")}</span></td>
            <td>{canUpdate && <button type="button" className={s.button} disabled={busy} onClick={() => setEditing(p)}>{t("edit")}</button>}</td>
          </tr>)}</tbody>
      </table></div>
      {canCreate && <div className={s.actions} style={{ marginTop: 12 }}>
        <button type="button" className={s.button} disabled={busy} onClick={() => void run(addStandardParameters)}>{t("addStandard")}</button>
        <span className={s.muted}>{t("standardHint")}</span>
      </div>}
    </section>}
    {canCreate && rows !== null && <form className={s.panel} onSubmit={add} aria-label={t("newTitle")}>
      <h2 style={{ marginTop: 0 }}>{t("newTitle")}</h2>
      <div className={s.grid}>
        <label className={s.field}>{t("fields.code")}<input required maxLength={40} pattern="[A-Za-z0-9_\-]+" dir="ltr" value={draft.code} onChange={e => set("code", e.target.value)} /></label>
        <label className={s.field}>{t("fields.nameAr")}<input required maxLength={120} value={draft.name_ar} onChange={e => set("name_ar", e.target.value)} /></label>
        <label className={s.field}>{t("fields.nameEn")}<input required maxLength={120} dir="ltr" value={draft.name_en} onChange={e => set("name_en", e.target.value)} /></label>
        <label className={s.field}>{t("fields.kind")}
          <select value={draft.kind} onChange={e => set("kind", e.target.value)}>
            <option value="numeric">{t("kinds.numeric")}</option><option value="attribute">{t("kinds.attribute")}</option>
          </select>
        </label>
        {draft.kind === "numeric" && <label className={s.field}>{t("fields.unit")}<input maxLength={16} dir="ltr" value={draft.unit} onChange={e => set("unit", e.target.value)} /></label>}
        <label className={s.field}>{t("fields.method")}<ReferenceTextSelect list="test_method" value={draft.method} onChange={v=>set("method",v)}/></label>
      </div>
      <p className={s.muted}>{t("kindHint")}</p>
      <button type="submit" className={`${s.button} ${s.primary}`} disabled={busy}>{t("add")}</button>
    </form>}
  </PageFrame>;
}
