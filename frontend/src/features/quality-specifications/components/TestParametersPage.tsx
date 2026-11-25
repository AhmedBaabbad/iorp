"use client";
import {bilingualText} from "@/lib/bilingual-text";
import {useListPage} from "@/hooks/useListPage";
import {Pagination,ListToolbar} from "@/components/pagination";


import Link from "next/link";
import {ParameterFormFields,EMPTY_PARAMETER,type ParameterDraft} from "./ParameterFormFields";
import { useTranslations,useLocale } from "next-intl";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { usePermission } from "@/features/auth/permission-hooks";
import s from "@/features/production-demands/demands.module.css";
import { qualityErrorMessage } from "@/features/quality-checks/components/quality-errors";
import { Q } from "@/lib/quality-permissions";
import { addStandardParameters, createParameter, getParameters, updateParameter } from "../api";
import type { TestParameter } from "../types";



// "خصائص الفحص": what the factory measures (numeric, in a unit) or checks visually (conforming / not).
export function TestParametersPage() {
  const locale=useLocale();
  const t = useTranslations("quality.parameters");
  const common=useTranslations("common");
  const page=useListPage<TestParameter>({search:"",status:""});
  const {params,accept}=page;
  const errors = useTranslations("quality.errors");
  const messages = useTranslations("messages");
  const canCreate = usePermission(Q.SPECS_CREATE);
  const canUpdate = usePermission(Q.SPECS_UPDATE);
  const [rows, setRows] = useState<TestParameter[] | null>(null);
  const [draft, setDraft] = useState<ParameterDraft>(EMPTY_PARAMETER);
  const [editing, setEditing] = useState<TestParameter | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try { accept(await getParameters(false,params),setRows); } catch (e) { setError(qualityErrorMessage(e, errors)); }
  }, [params,accept,errors]);
  useEffect(() => { void load(); }, [load]);

  async function run(action: () => Promise<unknown>) {
    setBusy(true); setError("");
    try { await action(); await load(); return true; } catch (e) { setError(qualityErrorMessage(e, errors)); return false; } finally { setBusy(false); }
  }
  async function add(event: FormEvent) {
    event.preventDefault();
    const ok = await run(() => createParameter({ ...draft, unit: draft.kind === "numeric" ? draft.unit || null : null, method_ar: draft.method_ar || null,method_en:draft.method_en||null,
      sort_order: (page.meta?.total ?? 0) * 10 + 10 }));
    if (ok) setDraft(EMPTY_PARAMETER);
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    if (!editing) return;
    const ok = await run(() => updateParameter(editing.id, { name_ar: editing.name_ar, name_en: editing.name_en, unit: editing.unit || null,
      method_ar: editing.method_ar || null,method_en:editing.method_en||null, is_active: editing.is_active }));
    if (ok) setEditing(null);
  }
  const set = (field: keyof ParameterDraft, value: string) => setDraft(old => ({ ...old, [field]: value }));

  return <PageFrame title={t("title")} subtitle={t("subtitle")}
    action={<Link href="/quality-specifications" className={s.button}>{t("toSpecifications")}</Link>}>
    <ListToolbar search={page.filters.search} onSearch={value=>page.set("search",value)} searchHint={common("listFilters.search")} onClear={page.clear}
      status={page.filters.status} onStatus={value=>page.set("status",value)} statusLabel={common("listFilters.status")} statuses={["active","inactive"].map(value=>({value,label:common(`listFilters.${value}`)}))}/>
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
            <td><div className={s.grid}>{(["ar","en"] as const).map(lang=><label key={lang}>{t(`fields.method_${lang}`)}<input maxLength={255} dir={lang==="ar"?"rtl":"ltr"} value={editing[`method_${lang}`]??""} onChange={e=>setEditing({...editing,[`method_${lang}`]:e.target.value})}/></label>)}</div></td>
            <td><label><input type="checkbox" checked={editing.is_active} onChange={e => setEditing({ ...editing, is_active: e.target.checked })} /> {t("active")}</label></td>
            <td><form onSubmit={save} className={s.actions}>
              <button type="submit" className={`${s.button} ${s.primary}`} disabled={busy}>{t("save")}</button>
              <button type="button" className={s.button} disabled={busy} onClick={() => setEditing(null)}>{t("cancel")}</button>
            </form></td>
          </tr>
          : <tr key={p.id} style={p.is_active ? undefined : { opacity: 0.6 }}>
            <td><bdi>{p.code}</bdi></td><td>{p.name_ar}</td><td dir="ltr">{p.name_en}</td><td>{t(`kinds.${p.kind}`)}</td>
            <td>{p.unit ?? "—"}</td><td dir="ltr">{bilingualText(p,"method",locale)||"—"}</td>
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
      <ParameterFormFields draft={draft} set={set}/>
      <button type="submit" className={`${s.button} ${s.primary}`} disabled={busy}>{t("add")}</button>
    </form>}
    <Pagination {...page.pagination} disabled={rows===null||page.pending}/>
  </PageFrame>;
}
