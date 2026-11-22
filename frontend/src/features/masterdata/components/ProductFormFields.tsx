"use client";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { RecordDialog } from "@/components/ui/RecordDialog";
import { UnitSelect } from "@/components/forms/UnitSelect";
import { usePermission } from "@/features/auth/permission-hooks";
import { MD } from "@/lib/masterdata-permissions";
import s from "@/features/production-demands/demands.module.css";
import { createProduct, getProduct, updateProduct } from "../api";
import { refreshCatalog } from "../catalog";
import { masterdataErrorMessage } from "../masterdata-errors";
import { PRODUCT_KINDS, PROPERTY_KINDS, type Product, type ProductInput, type ProductKind, type ProductProperty } from "../types";
const KEY = /^[a-z][a-z0-9_]{1,59}$/;
const keyFrom = (text: string) => text.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 60);
const emptyProperty = (): ProductProperty => ({ key: "", name_ar: "", name_en: "", kind: "number", unit: null, required: false, options: null });

// A product: its names, key (fixed once saved), kind, default unit and specification template.
export function useProductEditor({ productId, initialName, initialKey, kind }: { productId?: string; initialName?: string; initialKey?: string; kind?: ProductKind }) {
  const t = useTranslations("masterdata");
  const errors = useTranslations("masterdata.errors");
  const messages = useTranslations("messages");
  const canEdit = usePermission(productId ? MD.PRODUCTS_UPDATE : MD.PRODUCTS_CREATE);
  const [v, setV] = useState<ProductInput>({ key: initialKey ?? "", name_ar: initialName ?? "", name_en: "", kind: kind ?? "finished", default_unit: null,
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

  async function save() {
    if (!valid || busy) return null;
    setBusy(true); setError("");
    const properties = props.map(p => ({ ...p, unit: p.kind === "number" ? p.unit || null : null, options: p.kind === "choice" ? p.options : null }));
    try {
      const result = productId
        ? await updateProduct(productId, { name_ar: v.name_ar.trim(), name_en: v.name_en.trim(), kind: v.kind, default_unit: v.default_unit, active: v.active,
          notes: v.notes?.trim() || null, properties })
        : await createProduct({ ...v, key, name_ar: v.name_ar.trim(), name_en: v.name_en.trim(), notes: v.notes?.trim() || null, properties });
      await refreshCatalog();
      setSaved(result); setBusy(false); return result;
    } catch (e) { setError(masterdataErrorMessage(e, errors)); setBusy(false); return null; }
  }
  return { t, messages, productId, canEdit, v, setV, saved, loading, busy, error, key, props, setProp, move, valid, save, fixedKind: kind };
}

export function ProductFormFields({ editor }: { editor: ReturnType<typeof useProductEditor> }) {
  const { t, productId, canEdit, v, setV, busy, key, props, setProp, move, fixedKind } = editor;
  return (<fieldset disabled={busy || !canEdit} style={{ border: 0, padding: 0, margin: 0 }}>
        <section className={s.panel}>
          <div className={s.grid}>
            <label className={s.field}>{t("fields.name_ar")}<input required dir="rtl" maxLength={255} value={v.name_ar} onChange={e => setV({ ...v, name_ar: e.target.value })} /></label>
            <label className={s.field}>{t("fields.name_en")}<input required dir="ltr" maxLength={255} value={v.name_en} onChange={e => setV({ ...v, name_en: e.target.value })} /></label>
            <label className={s.field}>{t("fields.key")}{productId ? <input dir="ltr" value={key} readOnly aria-readonly="true" />
              : <input dir="ltr" maxLength={60} value={v.key ?? ""} placeholder={keyFrom(v.name_en) || "pp_strap"} onChange={e => setV({ ...v, key: e.target.value })} />}
              <span className={s.muted}>{productId ? t("products.keyFixed") : t("products.keyHint", { key: key || "—" })}</span></label>
            <label className={s.field}>{t("fields.kind")}
              <select disabled={Boolean(fixedKind)} value={v.kind} onChange={e => setV({ ...v, kind: e.target.value as ProductInput["kind"] })}>
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
                <select value={p.kind} onChange={e => setProp(i, { kind: e.target.value as ProductProperty["kind"], allows_range: e.target.value === "number" && Boolean(p.allows_range) })}>
                  {PROPERTY_KINDS.map(k => <option key={k} value={k}>{t(`propertyKinds.${k}`)}</option>)}</select></label>
              {p.kind === "number" && <label className={s.field}><span>{t("template.allowsRange")}</span>
                <input type="checkbox" checked={Boolean(p.allows_range)} onChange={e => setProp(i, { allows_range: e.target.checked })} /></label>}
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
      </fieldset>);
}
export function ProductCreateDialog({ kind, onCreated, onClose }: { kind?: ProductKind; onCreated: (product: Product) => void; onClose: () => void }) {
  const editor = useProductEditor({kind});
  return <RecordDialog title={editor.t("products.createTitle")} error={editor.error} disabled={!editor.valid || !editor.canEdit} onClose={onClose}
    onSave={async()=>{const product=await editor.save(); if(!product)return false; onCreated(product);return true;}}>
    <div style={{gridColumn:"1 / -1",minWidth:0}}><ProductFormFields editor={editor}/></div>
  </RecordDialog>;
}
