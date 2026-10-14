"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import { UnitSelect } from "@/components/forms/UnitSelect";
import { PageFrame } from "@/components/layout/page-frame";
import { useHasAnyPermission, usePermission } from "@/features/auth/permission-hooks";
import s from "@/features/production-demands/demands.module.css";
import { MD } from "@/lib/masterdata-permissions";
import { createProduct, getLegacyValues, getProduct, getProducts, mapLegacyValue, updateProduct } from "../api";
import { refreshCatalog } from "../catalog";
import { masterdataErrorMessage } from "../masterdata-errors";
import { PRODUCT_KINDS, PROPERTY_KINDS, type LegacyValue, type Product, type ProductInput, type ProductProperty } from "../types";

import { joinList } from "@/lib/utils";
const KEY = /^[a-z][a-z0-9_]{1,59}$/;
const keyFrom = (text: string) => text.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 60);

// «المنتجات»: what the organization makes or buys, named on every document; each with its specification template.
export function ProductsList() {
  const t = useTranslations("masterdata");
  const errors = useTranslations("masterdata.errors");
  const messages = useTranslations("messages");
  const units = useTranslations("common.units.units");
  const locale = useLocale();
  const canCreate = usePermission(MD.PRODUCTS_CREATE);
  const canLegacy = useHasAnyPermission([MD.PRODUCTS_CREATE, MD.PRODUCTS_MAP_LEGACY]);
  const [search, setSearch] = useState("");
  const [rows, setRows] = useState<Product[] | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    setError("");
    try { setRows(await getProducts({ search })); } catch (e) { setError(masterdataErrorMessage(e, errors)); }
  }, [search, errors]);
  useEffect(() => { const timer = setTimeout(() => void load(), 200); return () => clearTimeout(timer); }, [load]);

  return <PageFrame title={t("products.title")} subtitle={t("products.subtitle")}
    action={canCreate ? <Link href="/master-data/products/new" className={`${s.button} ${s.primary}`}>{t("products.new")}</Link> : undefined}>
    <section className={s.toolbar} aria-label={t("products.title")}>
      <label className={s.field}>{t("search")}<input type="search" value={search} placeholder={t("products.searchPlaceholder")} onChange={e => setSearch(e.target.value)} /></label>
    </section>
    {error && <p role="alert" className={s.error}>{error}</p>}
    {rows === null && !error && <p className={s.muted}>{messages("loading.default")}</p>}
    {rows?.length === 0 && <section className={s.panel}><h2 style={{ marginTop: 0 }}>{t("products.empty")}</h2><p className={s.muted} style={{ margin: 0 }}>{t("products.emptyHint")}</p></section>}
    {rows && rows.length > 0 && <section className={s.panel}><div className={s.tableWrap}><table className={s.table} aria-label={t("products.title")}>
      <thead><tr>{["code", "name", "key", "kind", "unit", "properties"].map(c => <th key={c}>{t(`fields.${c}`)}</th>)}</tr></thead>
      <tbody>{rows.map(p => <tr key={p.id} style={p.active ? undefined : { opacity: 0.6 }}>
        <td><Link href={`/master-data/products/${p.id}`}><bdi>{p.code}</bdi></Link></td>
        <td>{locale === "ar" ? p.name_ar : p.name_en}<div className={s.muted}>{locale === "ar" ? p.name_en : p.name_ar}</div>
          {!p.active && <div className={s.muted}>{t("products.inactive")}</div>}</td>
        <td><bdi dir="ltr">{p.key}</bdi></td>
        <td>{t(`kinds.${p.kind}`)}</td>
        <td>{p.default_unit ? (units.has(p.default_unit) ? units(p.default_unit) : p.default_unit) : "—"}</td>
        <td>{p.properties.length ? joinList(p.properties.map(q => (locale === "ar" ? q.name_ar : q.name_en)), locale) : "—"}</td>
      </tr>)}</tbody>
    </table></div></section>}
    {canLegacy && rows && <LegacyValues products={rows} onMapped={() => { refreshCatalog(); void load(); }} />}
  </PageFrame>;
}

// Product types written as free text before the list: map each one to a product (each module rewrites its own records).
function LegacyValues({ products, onMapped }: { products: Product[]; onMapped: () => void }) {
  const t = useTranslations("masterdata.legacy");
  const errors = useTranslations("masterdata.errors");
  const locale = useLocale();
  const canMap = usePermission(MD.PRODUCTS_MAP_LEGACY);
  const canCreate = usePermission(MD.PRODUCTS_CREATE);
  const [rows, setRows] = useState<LegacyValue[] | null>(null);
  const [chosen, setChosen] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const load = useCallback(() => getLegacyValues().then(setRows).catch(() => setRows([])), []);
  useEffect(() => { void load(); }, [load, products]);
  if (!rows || rows.length === 0) return null;

  async function map(value: string) {
    if (!chosen[value]) return;
    setBusy(value); setMessage("");
    try {
      const result = await mapLegacyValue(value, chosen[value]);
      setMessage(t("mapped", { value, count: String(Object.values(result.changed).reduce((a, b) => a + b, 0)) }));
      onMapped(); await load();
    } catch (e) { setMessage(masterdataErrorMessage(e, errors)); } finally { setBusy(null); }
  }
  return <section className={s.panel} aria-label={t("title")}>
    <h2 style={{ marginTop: 0 }}>{t("title")}</h2>
    <p className={s.muted} style={{ marginTop: 0 }}>{t("hint")}</p>
    {message && <p role="status" className={s.muted}>{message}</p>}
    <div className={s.tableWrap}><table className={s.table}>
      <thead><tr><th>{t("value")}</th><th>{t("usedIn")}</th><th>{t("mapTo")}</th><th /></tr></thead>
      <tbody>{rows.map(r => <tr key={r.value}>
        <td><bdi>«{r.value}»</bdi></td>
        <td>{Object.entries(r.uses).map(([module, count]) => t("use", { module: t(`modules.${module}`), count: String(count) })).join(" · ")}</td>
        <td>{canMap ? <select aria-label={t("mapTo")} value={chosen[r.value] ?? ""} onChange={e => setChosen(old => ({ ...old, [r.value]: e.target.value }))}>
          <option value="">—</option>{products.filter(p => p.active).map(p => <option key={p.id} value={p.id}>{locale === "ar" ? p.name_ar : p.name_en}</option>)}
        </select> : "—"}</td>
        <td><span className={s.actions}>
          {canMap && <button type="button" className={`${s.button} ${s.primary}`} disabled={!chosen[r.value] || busy !== null} onClick={() => void map(r.value)}>{t("map")}</button>}
          {canCreate && <Link className={s.button} href={`/master-data/products/new?name=${encodeURIComponent(r.value.trim())}&key=${encodeURIComponent(r.suggested_key)}`}>
            {t("create")}</Link>}
        </span></td>
      </tr>)}</tbody>
    </table></div>
  </section>;
}

const emptyProperty = (): ProductProperty => ({ key: "", name_ar: "", name_en: "", kind: "number", unit: null, required: false, options: null });

// A product: its names, key (fixed once saved), kind, default unit and specification template.
export function ProductForm({ productId, initialName, initialKey }: { productId?: string; initialName?: string; initialKey?: string }) {
  const t = useTranslations("masterdata");
  const errors = useTranslations("masterdata.errors");
  const messages = useTranslations("messages");
  const router = useRouter();
  const canEdit = usePermission(productId ? MD.PRODUCTS_UPDATE : MD.PRODUCTS_CREATE);
  const [v, setV] = useState<ProductInput>({ key: initialKey ?? "", name_ar: initialName ?? "", name_en: "", kind: "finished", default_unit: null,
    active: true, notes: null, properties: [] });
  const [saved, setSaved] = useState<Product | null>(null);
  const [loading, setLoading] = useState(Boolean(productId));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!productId) return;
    getProduct(productId).then(p => { setSaved(p); setV({ name_ar: p.name_ar, name_en: p.name_en, kind: p.kind, default_unit: p.default_unit, active: p.active,
      notes: p.notes, properties: p.properties }); })
      .catch(e => setError(masterdataErrorMessage(e, errors))).finally(() => setLoading(false));
  }, [productId, errors]);

  const key = productId ? saved?.key ?? "" : (v.key?.trim() || keyFrom(v.name_en));
  const props = v.properties;
  const setProp = (i: number, change: Partial<ProductProperty>) => setV(old => ({ ...old, properties: old.properties.map((p, n) => (n === i ? { ...p, ...change } : p)) }));
  const move = (i: number, by: number) => setV(old => { const next = [...old.properties]; const [p] = next.splice(i, 1); next.splice(i + by, 0, p); return { ...old, properties: next }; });
  const propsOk = props.every(p => KEY.test(p.key) && p.name_ar.trim() && p.name_en.trim()
    && (p.kind !== "choice" || ((p.options ?? []).length > 0 && (p.options ?? []).every(o => o.value && o.label_ar.trim() && o.label_en.trim()))))
    && new Set(props.map(p => p.key)).size === props.length;
  const valid = Boolean(v.name_ar.trim() && v.name_en.trim()) && (productId || KEY.test(key)) && propsOk;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!valid || busy) return;
    setBusy(true); setError("");
    const properties = props.map(p => ({ ...p, unit: p.kind === "number" ? p.unit || null : null, options: p.kind === "choice" ? p.options : null }));
    try {
      const result = productId
        ? await updateProduct(productId, { name_ar: v.name_ar.trim(), name_en: v.name_en.trim(), kind: v.kind, default_unit: v.default_unit, active: v.active,
          notes: v.notes?.trim() || null, properties })
        : await createProduct({ ...v, key, name_ar: v.name_ar.trim(), name_en: v.name_en.trim(), notes: v.notes?.trim() || null, properties });
      refreshCatalog();
      router.push(`/master-data/products/${result.id}`);
      if (productId) { setSaved(result); setBusy(false); setError(""); }
    } catch (e) { setError(masterdataErrorMessage(e, errors)); setBusy(false); }
  }
  const title = productId ? (saved ? `${saved.code} — ${saved.name_ar}` : t("products.editTitle")) : t("products.createTitle");
  const back = <Link href="/master-data/products" className={s.button}>{t("products.back")}</Link>;
  if (loading) return <PageFrame title={title} action={back}><p className={s.muted}>{messages("loading.default")}</p></PageFrame>;

  return <PageFrame title={title} subtitle={t("products.formSubtitle")} action={back}>
    <form onSubmit={submit} aria-label={title}>
      <fieldset disabled={busy || !canEdit} style={{ border: 0, padding: 0, margin: 0 }}>
        <section className={s.panel}>
          <div className={s.grid}>
            <label className={s.field}>{t("fields.name_ar")}<input required dir="rtl" maxLength={255} value={v.name_ar} onChange={e => setV({ ...v, name_ar: e.target.value })} /></label>
            <label className={s.field}>{t("fields.name_en")}<input required dir="ltr" maxLength={255} value={v.name_en} onChange={e => setV({ ...v, name_en: e.target.value })} /></label>
            <label className={s.field}>{t("fields.key")}{productId ? <input dir="ltr" value={key} readOnly aria-readonly="true" />
              : <input dir="ltr" maxLength={60} value={v.key ?? ""} placeholder={keyFrom(v.name_en) || "pp_strap"} onChange={e => setV({ ...v, key: e.target.value })} />}
              <span className={s.muted}>{productId ? t("products.keyFixed") : t("products.keyHint", { key: key || "—" })}</span></label>
            <label className={s.field}>{t("fields.kind")}
              <select value={v.kind} onChange={e => setV({ ...v, kind: e.target.value as ProductInput["kind"] })}>
                {PRODUCT_KINDS.map(k => <option key={k} value={k}>{t(`kinds.${k}`)}</option>)}</select></label>
            <label className={s.field}>{t("fields.unit")}<UnitSelect value={v.default_unit ?? ""} onChange={u => setV({ ...v, default_unit: u || null })}
              ariaLabel={t("fields.unit")} placeholder="—" required={false} /></label>
          </div>
          {productId && <label><input type="checkbox" checked={v.active} onChange={e => setV({ ...v, active: e.target.checked })} /> {t("products.active")}</label>}
          <label className={s.field}>{t("fields.notes")}<textarea maxLength={2000} value={v.notes ?? ""} onChange={e => setV({ ...v, notes: e.target.value })} /></label>
        </section>

        <section className={s.panel} aria-label={t("template.title")}>
          <h2 style={{ marginTop: 0 }}>{t("template.title")}</h2>
          <p className={s.muted} style={{ marginTop: 0 }}>{t("template.hint")}</p>
          {props.length === 0 && <p className={s.muted}>{t("template.empty")}</p>}
          {props.map((p, i) => <fieldset key={i} className={s.panel} style={{ margin: "0 0 10px", padding: 14 }}>
            <legend style={{ fontWeight: 600 }}>{i + 1}. {(p.name_ar || p.name_en) || t("template.newProperty")}</legend>
            <div className={s.grid}>
              <label className={s.field}>{t("template.name_ar")}<input required dir="rtl" maxLength={120} value={p.name_ar} onChange={e => setProp(i, { name_ar: e.target.value })} /></label>
              <label className={s.field}>{t("template.name_en")}<input required dir="ltr" maxLength={120} value={p.name_en}
                onChange={e => setProp(i, { name_en: e.target.value })} onBlur={() => { if (!p.key && p.name_en) setProp(i, { key: keyFrom(p.name_en) }); }} /></label>
              <label className={s.field}>{t("template.key")}<input required dir="ltr" maxLength={60} value={p.key} placeholder="width_mm"
                onChange={e => setProp(i, { key: e.target.value })} /></label>
              <label className={s.field}>{t("template.kind")}
                <select value={p.kind} onChange={e => setProp(i, { kind: e.target.value as ProductProperty["kind"] })}>
                  {PROPERTY_KINDS.map(k => <option key={k} value={k}>{t(`propertyKinds.${k}`)}</option>)}</select></label>
              {p.kind === "number" && <label className={s.field}>{t("template.unit")}<UnitSelect value={p.unit ?? ""} onChange={u => setProp(i, { unit: u || null })}
                ariaLabel={t("template.unit")} placeholder="—" required={false} /></label>}
            </div>
            {p.key && !KEY.test(p.key) && <p className={s.error} style={{ margin: 0 }}>{t("template.keyInvalid")}</p>}
            {p.kind === "choice" && <div style={{ display: "grid", gap: 6 }} aria-label={t("template.options")}>
              <strong>{t("template.options")}</strong>
              {(p.options ?? []).map((o, n) => <div key={n} className={s.actions}>
                <input aria-label={t("template.label_ar")} placeholder={t("template.label_ar")} dir="rtl" maxLength={120} value={o.label_ar}
                  onChange={e => setProp(i, { options: (p.options ?? []).map((x, m) => (m === n ? { ...x, label_ar: e.target.value } : x)) })} />
                <input aria-label={t("template.label_en")} placeholder={t("template.label_en")} dir="ltr" maxLength={120} value={o.label_en}
                  onChange={e => setProp(i, { options: (p.options ?? []).map((x, m) => (m === n ? { ...x, label_en: e.target.value, value: x.value || keyFrom(e.target.value) } : x)) })} />
                <button type="button" className={s.button} aria-label={t("template.removeOption")}
                  onClick={() => setProp(i, { options: (p.options ?? []).filter((_, m) => m !== n) })}>×</button>
              </div>)}
              <div><button type="button" className={s.button} onClick={() => setProp(i, { options: [...(p.options ?? []), { value: "", label_ar: "", label_en: "" }] })}>
                {t("template.addOption")}</button></div>
            </div>}
            <div className={s.actions}>
              <label><input type="checkbox" checked={p.required} onChange={e => setProp(i, { required: e.target.checked })} /> {t("template.required")}</label>
              <button type="button" className={s.button} disabled={i === 0} aria-label={t("template.moveUp")} onClick={() => move(i, -1)}>↑</button>
              <button type="button" className={s.button} disabled={i === props.length - 1} aria-label={t("template.moveDown")} onClick={() => move(i, 1)}>↓</button>
              <button type="button" className={`${s.button} ${s.danger}`} onClick={() => setV(old => ({ ...old, properties: old.properties.filter((_, n) => n !== i) }))}>
                {t("template.remove")}</button>
            </div>
          </fieldset>)}
          <button type="button" className={s.button} onClick={() => setV(old => ({ ...old, properties: [...old.properties, emptyProperty()] }))}>{t("template.add")}</button>
        </section>
      </fieldset>
      {error && <p role="alert" className={s.error}>{error}</p>}
      {canEdit && <div className={s.actions}>
        <button type="submit" className={`${s.button} ${s.primary}`} disabled={!valid || busy}>{t("save")}</button>
        <Link href="/master-data/products" className={s.button}>{t("cancel")}</Link>
      </div>}
    </form>
  </PageFrame>;
}
