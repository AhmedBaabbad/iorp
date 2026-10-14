"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import { UnitSelect } from "@/components/forms/UnitSelect";
import { PageFrame } from "@/components/layout/page-frame";
import { usePermission } from "@/features/auth/permission-hooks";
import { ProductSelect, useListChoices, useListName, useProductName } from "@/features/masterdata";
import s from "@/features/production-demands/demands.module.css";
import { PR } from "@/lib/procurement-permissions";
import { createMaterial, getMaterials, updateMaterial } from "../api";
import { procurementErrorMessage } from "../procurement-errors";
import { MATERIAL_CATEGORIES, type Material, type MaterialInput } from "../types";

// "المواد": what is bought, its default unit, and whether each lot is inspected on arrival.
export function MaterialsList() {
  const t = useTranslations("procurement");
  const materialCategory = useListName("material_category", (k) => (t.has(`materialCategories.${k}`) ? t(`materialCategories.${k}`) : undefined));
  const errors = useTranslations("procurement.errors");
  const messages = useTranslations("messages");
  const units = useTranslations("common.units.units");
  const canCreate = usePermission(PR.MATERIALS_CREATE);
  const canUpdate = usePermission(PR.MATERIALS_UPDATE);
  const productName = useProductName();
  const [search, setSearch] = useState("");
  const [rows, setRows] = useState<Material[] | null>(null);
  const [editing, setEditing] = useState<Material | "new" | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    setError("");
    try { setRows(await getMaterials({ search })); } catch (e) { setError(procurementErrorMessage(e, errors)); }
  }, [search, errors]);
  useEffect(() => { const timer = setTimeout(() => void load(), 200); return () => clearTimeout(timer); }, [load]);

  return <PageFrame title={t("materials.title")} subtitle={t("materials.subtitle")}
    action={canCreate ? <button type="button" className={`${s.button} ${s.primary}`} onClick={() => setEditing("new")}>{t("materials.new")}</button> : undefined}>
    <section className={s.toolbar} aria-label={t("filtersAria")}>
      <label className={s.field}>{t("search")}<input type="search" value={search} onChange={e => setSearch(e.target.value)} /></label>
    </section>
    {error && <p role="alert" className={s.error}>{error}</p>}
    {rows === null && !error && <p className={s.muted}>{messages("loading.default")}</p>}
    {rows?.length === 0 && <section className={s.panel}><h2 style={{ marginTop: 0 }}>{t("materials.empty")}</h2><p className={s.muted} style={{ margin: 0 }}>{t("materials.emptyHint")}</p></section>}
    {rows && rows.length > 0 && <section className={s.panel}><div className={s.tableWrap}><table className={s.table} aria-label={t("materials.title")}>
      <thead><tr>{["code", "name", "category", "unit", "inspection_required", "spec_product_type"].map(c => <th key={c}>{t(`fields.${c}`)}</th>)}<th /></tr></thead>
      <tbody>{rows.map(m => <tr key={m.id} style={m.active ? undefined : { opacity: 0.6 }}>
        <td><bdi>{m.material_code}</bdi></td>
        <td>{m.name}{!m.active && <div className={s.muted}>{t("materials.inactive")}</div>}</td>
        <td>{materialCategory(m.category)}</td>
        <td>{units.has(m.unit) ? units(m.unit) : m.unit}</td>
        <td>{m.inspection_required ? t("yes") : t("no")}</td>
        <td>{m.spec_product_type ? productName(m.spec_product_type) : "—"}</td>
        <td>{canUpdate && <button type="button" className={s.button} onClick={() => setEditing(m)}>{t("edit")}</button>}</td>
      </tr>)}</tbody>
    </table></div></section>}
    {editing && <MaterialDialog value={editing === "new" ? null : editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); void load(); }} />}
  </PageFrame>;
}

function MaterialDialog({ value, onClose, onSaved }: { value: Material | null; onClose: () => void; onSaved: () => void }) {
  const t = useTranslations("procurement");
  const materialCategory = useListName("material_category", (k) => (t.has(`materialCategories.${k}`) ? t(`materialCategories.${k}`) : undefined));
  const errors = useTranslations("procurement.errors");
  const [v, setV] = useState<MaterialInput>(value ? { name: value.name, category: value.category, unit: value.unit, inspection_required: value.inspection_required,
    spec_product_type: value.spec_product_type, active: value.active, notes: value.notes }
    : { name: "", category: "resin", unit: "kg", inspection_required: true, spec_product_type: null, active: true, notes: null });
  const categoryChoices = useListChoices("material_category", MATERIAL_CATEGORIES, materialCategory, v.category);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const title = value ? t("materials.editTitle") : t("materials.createTitle");
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!v.name.trim() || busy) return;
    setBusy(true); setError("");
    const body = { ...v, name: v.name.trim(), spec_product_type: v.spec_product_type?.trim() || null, notes: v.notes?.trim() || null };
    try { await (value ? updateMaterial(value.id, body) : createMaterial(body)); onSaved(); }
    catch (e) { setError(procurementErrorMessage(e, errors)); setBusy(false); }
  }
  return <div className={s.overlay} onKeyDown={e => { if (e.key === "Escape" && !busy) onClose(); }}>
    <form role="dialog" aria-modal="true" aria-label={title} className={`${s.panel} ${s.dialog}`} onSubmit={submit}>
      <h2 style={{ margin: 0 }}>{title}</h2>
      <div className={s.grid}>
        <label className={s.field}>{t("fields.name")}<input required autoFocus maxLength={255} value={v.name} disabled={busy} onChange={e => setV({ ...v, name: e.target.value })} /></label>
        <label className={s.field}>{t("fields.category")}
          <select value={v.category} disabled={busy} onChange={e => setV({ ...v, category: e.target.value })}>
            {categoryChoices.map(c => <option key={c.key} value={c.key}>{c.label}</option>)}</select></label>
        <label className={s.field}>{t("fields.unit")}<UnitSelect value={v.unit} onChange={u => setV({ ...v, unit: u })} ariaLabel={t("fields.unit")} /></label>
        <label className={s.field}>{t("fields.spec_product_type")}<ProductSelect ariaLabel={t("fields.spec_product_type")} kind="material" required={false}
          value={v.spec_product_type ?? ""} disabled={busy} onChange={key => setV({ ...v, spec_product_type: key })} /></label>
      </div>
      <label><input type="checkbox" checked={v.inspection_required} disabled={busy} onChange={e => setV({ ...v, inspection_required: e.target.checked })} /> {t("materials.inspectionHint")}</label>
      {value && <label><input type="checkbox" checked={v.active} disabled={busy} onChange={e => setV({ ...v, active: e.target.checked })} /> {t("materials.active")}</label>}
      <label className={s.field}>{t("fields.notes")}<textarea maxLength={2000} value={v.notes ?? ""} disabled={busy} onChange={e => setV({ ...v, notes: e.target.value })} /></label>
      {error && <p role="alert" className={s.error}>{error}</p>}
      <div className={s.actions}>
        <button type="button" className={s.button} disabled={busy} onClick={onClose}>{t("cancel")}</button>
        <button type="submit" className={`${s.button} ${s.primary}`} disabled={busy || !v.name.trim()}>{t("save")}</button>
      </div>
    </form>
  </div>;
}
