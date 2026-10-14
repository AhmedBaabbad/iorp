"use client";

import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { usePermission } from "@/features/auth/permission-hooks";
import s from "@/features/production-demands/demands.module.css";
import { MD } from "@/lib/masterdata-permissions";
import { addStandardItems, createListItem, deleteListItem, getListItems, getListLegacy, mapListLegacy, updateListItem } from "../api";
import { refreshCatalog } from "../catalog";
import { masterdataErrorMessage } from "../masterdata-errors";
import { LIST_GROUPS, LIST_NAMES, type LegacyValue, type ListItem, type ListName } from "../types";

// Lists whose records keep the item's key (their old free texts can be mapped to an item).
const KEY_LISTS: ListName[] = ["sector", "opportunity_source", "country", "city", "supplier_category", "material_category", "defect_category",
  "rejection_reason", "complaint_category", "interaction_type", "vehicle_type"];

const PARENT: Partial<Record<ListName, ListName>> = { city: "country" };

// «القوائم المرجعية»: sectors, opportunity sources, countries and cities, chosen on customers, suppliers and shipments.
export function ReferenceLists({ initialList }: { initialList?: string }) {
  const t = useTranslations("masterdata.lists");
  const errors = useTranslations("masterdata.errors");
  const messages = useTranslations("messages");
  const locale = useLocale();
  const canManage = usePermission(MD.LISTS_UPDATE);
  const canMapLegacy = usePermission(MD.LISTS_MAP_LEGACY);  // RBAC-002: rewriting old texts in every module
  const [list, setList] = useState<ListName>(LIST_NAMES.includes(initialList as ListName) ? (initialList as ListName) : "sector");
  const [rows, setRows] = useState<ListItem[] | null>(null);
  const [parents, setParents] = useState<ListItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const parentList = PARENT[list];
  const name = (i: ListItem) => (locale === "ar" ? i.name_ar : i.name_en);

  const load = useCallback(async () => {
    setError("");
    try {
      setRows(await getListItems(list));
      setParents(parentList ? await getListItems(parentList) : []);
    } catch (e) { setError(masterdataErrorMessage(e, errors)); }
  }, [list, parentList, errors]);
  useEffect(() => { setRows(null); void load(); }, [load]);
  const changed = () => { refreshCatalog(); void load(); };

  async function standard() {
    setBusy(true); setMessage(""); setError("");
    try { const added = await addStandardItems(list); setMessage(t("standardAdded", { count: String(added.length) })); changed(); }
    catch (e) { setError(masterdataErrorMessage(e, errors)); } finally { setBusy(false); }
  }

  return <PageFrame title={t("title")} subtitle={t("subtitle")}>
    <nav aria-label={t("title")} style={{ display: "grid", gap: 8, marginBottom: 12 }}>
      {LIST_GROUPS.map(({ group, lists }) => <div key={group} className={s.actions} style={{ alignItems: "center" }}>
        <strong style={{ minWidth: 110, color: "var(--text-muted)" }}>{t(`groups.${group}`)}</strong>
        {lists.map(l => <button key={l} type="button" className={`${s.button} ${l === list ? s.primary : ""}`} aria-pressed={l === list}
          onClick={() => { setList(l); setMessage(""); }}>{t(`names.${l}`)}</button>)}
      </div>)}
    </nav>
    <section className={s.panel} aria-label={t(`names.${list}`)}>
      <div className={s.actions} style={{ justifyContent: "space-between" }}>
        <h2 style={{ margin: 0 }}>{t(`names.${list}`)}</h2>
        {canManage && <button type="button" className={s.button} disabled={busy} onClick={() => void standard()}>{t("addStandard")}</button>}
      </div>
      <p className={s.muted}>{t(`hints.${list}`)}</p>
      {message && <p role="status" className={s.muted}>{message}</p>}
      {error && <p role="alert" className={s.error}>{error}</p>}
      {rows === null && !error && <p className={s.muted}>{messages("loading.default")}</p>}
      {canManage && <AddItem list={list} parents={parents} onAdded={changed} />}
      {rows?.length === 0 && <p className={s.muted}>{t("empty")}</p>}
      {rows && rows.length > 0 && <div className={s.tableWrap}><table className={s.table} aria-label={t(`names.${list}`)}>
        <thead><tr><th>{t("fields.name_ar")}</th><th>{t("fields.name_en")}</th><th>{t("fields.key")}</th>{parentList && <th>{t(`names.${parentList}`)}</th>}
          <th>{t("fields.uses")}</th><th>{t("fields.active")}</th>{canManage && <th />}</tr></thead>
        <tbody>{rows.map(r => <Row key={r.id} item={r} parents={parents} canManage={canManage} onSaved={changed} onDeleted={(text) => { setMessage(text); changed(); }}
          parentName={(key) => { const p = parents.find(x => x.key === key); return p ? name(p) : key ?? "—"; }} />)}</tbody>
      </table></div>}
    </section>
    {canMapLegacy && rows && KEY_LISTS.includes(list) && <Legacy list={list} items={rows} onMapped={changed} />}
  </PageFrame>;
}

function AddItem({ list, parents, onAdded }: { list: ListName; parents: ListItem[]; onAdded: () => void }) {
  const t = useTranslations("masterdata.lists");
  const errors = useTranslations("masterdata.errors");
  const locale = useLocale();
  const [v, setV] = useState({ name_ar: "", name_en: "", parent_key: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const needsParent = Boolean(PARENT[list]);
  const valid = Boolean(v.name_ar.trim() && v.name_en.trim()) && (!needsParent || Boolean(v.parent_key));
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!valid || busy) return;
    setBusy(true); setError("");
    try {
      await createListItem(list, { name_ar: v.name_ar.trim(), name_en: v.name_en.trim(), parent_key: needsParent ? v.parent_key : null });
      setV({ name_ar: "", name_en: "", parent_key: v.parent_key }); onAdded();
    } catch (e) { setError(masterdataErrorMessage(e, errors)); } finally { setBusy(false); }
  }
  return <form className={s.toolbar} onSubmit={submit} aria-label={t("add")}>
    <label className={s.field}>{t("fields.name_ar")}<input dir="rtl" maxLength={200} value={v.name_ar} onChange={e => setV({ ...v, name_ar: e.target.value })} /></label>
    <label className={s.field}>{t("fields.name_en")}<input dir="ltr" maxLength={200} value={v.name_en} onChange={e => setV({ ...v, name_en: e.target.value })} /></label>
    {needsParent && <label className={s.field}>{t(`names.${PARENT[list]}`)}
      <select value={v.parent_key} onChange={e => setV({ ...v, parent_key: e.target.value })}><option value="">—</option>
        {parents.filter(p => p.active).map(p => <option key={p.key} value={p.key}>{locale === "ar" ? p.name_ar : p.name_en}</option>)}</select></label>}
    <button type="submit" className={`${s.button} ${s.primary}`} disabled={!valid || busy}>{t("add")}</button>
    {needsParent && parents.length === 0 && <span className={s.muted}>{t("parentFirst")}</span>}
    {error && <span role="alert" className={s.error}>{error}</span>}
  </form>;
}

function Row({ item, parents, canManage, onSaved, onDeleted, parentName }: { item: ListItem; parents: ListItem[]; canManage: boolean; onSaved: () => void;
  onDeleted: (message: string) => void; parentName: (key: string | null) => string }) {
  const t = useTranslations("masterdata.lists");
  const errors = useTranslations("masterdata.errors");
  const locale = useLocale();
  const [editing, setEditing] = useState(false);
  const [v, setV] = useState({ name_ar: item.name_ar, name_en: item.name_en, parent_key: item.parent_key ?? "", active: item.active });
  const [error, setError] = useState("");
  const hasParent = Boolean(PARENT[item.list]);
  async function save(change?: Partial<typeof v>) {
    const next = { ...v, ...change };
    setError("");
    try {
      await updateListItem(item.id, { name_ar: next.name_ar.trim(), name_en: next.name_en.trim(), active: next.active,
        ...(hasParent ? { parent_key: next.parent_key || null } : {}) });
      setEditing(false); onSaved();
    } catch (e) { setError(masterdataErrorMessage(e, errors)); }
  }
  // MD-003: an item nothing uses is deleted; one in use is only deactivated (its records keep showing its name).
  const uses = item.uses ?? 0;
  const deletable = uses === 0 && !item.protected;
  async function remove() {
    if (!window.confirm(t("confirmDelete", { name: locale === "ar" ? item.name_ar : item.name_en }))) return;
    setError("");
    try { await deleteListItem(item.id); onDeleted(t("deleted")); }
    catch (e) { setError(masterdataErrorMessage(e, errors)); }
  }
  return <tr style={item.active ? undefined : { opacity: 0.6 }}>
    <td>{editing ? <input aria-label={t("fields.name_ar")} dir="rtl" value={v.name_ar} onChange={e => setV({ ...v, name_ar: e.target.value })} /> : item.name_ar}</td>
    <td>{editing ? <input aria-label={t("fields.name_en")} dir="ltr" value={v.name_en} onChange={e => setV({ ...v, name_en: e.target.value })} /> : item.name_en}</td>
    <td><bdi dir="ltr">{item.key}</bdi></td>
    {hasParent && <td>{editing ? <select aria-label={t(`names.${PARENT[item.list]}`)} value={v.parent_key} onChange={e => setV({ ...v, parent_key: e.target.value })}>
      {parents.map(p => <option key={p.key} value={p.key}>{locale === "ar" ? p.name_ar : p.name_en}</option>)}</select> : parentName(item.parent_key)}</td>}
    <td>{uses}</td>
    <td>{canManage ? <input type="checkbox" aria-label={t("fields.active")} checked={item.active} onChange={e => void save({ active: e.target.checked })} />
      : item.active ? t("yes") : t("no")}</td>
    {canManage && <td><span className={s.actions}>
      {editing ? <><button type="button" className={`${s.button} ${s.primary}`} onClick={() => void save()}>{t("save")}</button>
        <button type="button" className={s.button} onClick={() => setEditing(false)}>{t("cancel")}</button></>
        : <button type="button" className={s.button} onClick={() => setEditing(true)}>{t("edit")}</button>}
      {!editing && <button type="button" className={s.button} disabled={!deletable} onClick={() => void remove()}
        title={item.protected ? t("protectedHint") : uses > 0 ? t("inUse", { count: uses }) : undefined}>{t("delete")}</button>}
      {!editing && !deletable && <small className={s.muted}>{item.protected ? t("protectedHint") : t("inUse", { count: uses })}</small>}
      {error && <span role="alert" className={s.error}>{error}</span>}
    </span></td>}
  </tr>;
}

// Texts written before the list: map each one to an item (each module rewrites its own records).
function Legacy({ list, items, onMapped }: { list: ListName; items: ListItem[]; onMapped: () => void }) {
  const t = useTranslations("masterdata.legacy");
  const lt = useTranslations("masterdata.lists");
  const errors = useTranslations("masterdata.errors");
  const locale = useLocale();
  const [rows, setRows] = useState<LegacyValue[] | null>(null);
  const [chosen, setChosen] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const load = useCallback(() => getListLegacy(list).then(setRows).catch(() => setRows([])), [list]);
  useEffect(() => { void load(); }, [load, items]);
  if (!rows || rows.length === 0) return null;
  async function map(value: string) {
    setBusy(true); setMessage("");
    try {
      const result = await mapListLegacy(list, value, chosen[value]);
      setMessage(t("mapped", { value, count: String(Object.values(result.changed).reduce((a, b) => a + b, 0)) }));
      onMapped(); await load();
    } catch (e) { setMessage(masterdataErrorMessage(e, errors)); } finally { setBusy(false); }
  }
  return <section className={s.panel} aria-label={lt("legacyTitle")}>
    <h2 style={{ marginTop: 0 }}>{lt("legacyTitle")}</h2>
    <p className={s.muted} style={{ marginTop: 0 }}>{lt("legacyHint")}</p>
    {message && <p role="status" className={s.muted}>{message}</p>}
    <div className={s.tableWrap}><table className={s.table}>
      <thead><tr><th>{t("value")}</th><th>{t("usedIn")}</th><th>{t("mapTo")}</th><th /></tr></thead>
      <tbody>{rows.map(r => <tr key={r.value}>
        <td><bdi>«{r.value}»</bdi></td>
        <td>{Object.entries(r.uses).map(([module, count]) => t("use", { module: lt(`modules.${module}`), count: String(count) })).join(" · ")}</td>
        <td><select aria-label={t("mapTo")} value={chosen[r.value] ?? ""} onChange={e => setChosen(old => ({ ...old, [r.value]: e.target.value }))}>
          <option value="">—</option>{items.filter(i => i.active).map(i => <option key={i.id} value={i.id}>{locale === "ar" ? i.name_ar : i.name_en}</option>)}
        </select></td>
        <td><button type="button" className={`${s.button} ${s.primary}`} disabled={!chosen[r.value] || busy} onClick={() => void map(r.value)}>{t("map")}</button></td>
      </tr>)}</tbody>
    </table></div>
  </section>;
}
