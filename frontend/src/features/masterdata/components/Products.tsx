"use client";
import {useListPage} from "@/hooks/useListPage";
import {Pagination,ListToolbar} from "@/components/pagination";
import {RecordCombobox} from "@/components/ui/RecordCombobox";

import { localName } from "@/lib/local-name";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { ProductFormFields, useProductEditor } from "./ProductFormFields";
import { PageFrame } from "@/components/layout/page-frame";
import { useHasAnyPermission, usePermission } from "@/features/auth/permission-hooks";
import s from "@/features/production-demands/demands.module.css";
import { MD } from "@/lib/masterdata-permissions";
import { getLegacyValues, getProducts, mapLegacyValue } from "../api";
import { refreshCatalog } from "../catalog";
import { masterdataErrorMessage } from "../masterdata-errors";
import { type LegacyValue, type Product } from "../types";

import { joinList } from "@/lib/utils";

// «المنتجات»: what the organization makes or buys, named on every document; each with its specification template.
export function ProductsList() {
  const t = useTranslations("masterdata");
  const errors = useTranslations("masterdata.errors");
  const messages = useTranslations("messages");
  const units = useTranslations("common.units.units");
  const locale = useLocale();
  const canCreate = usePermission(MD.PRODUCTS_CREATE);
  const canLegacy = useHasAnyPermission([MD.PRODUCTS_CREATE, MD.PRODUCTS_MAP_LEGACY]);
  const page=useListPage<Product>({search:"",kind:""});
  const {params,accept}=page;
  const [rows, setRows] = useState<Product[] | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    setError("");
    try { accept(await getProducts(params),setRows); } catch (e) { setError(masterdataErrorMessage(e, errors)); }
  }, [params,accept,errors]);
  useEffect(() => { const timer = setTimeout(() => void load(), 200); return () => clearTimeout(timer); }, [load]);

  return <PageFrame title={t("products.title")} subtitle={t("products.subtitle")}
    action={canCreate ? <Link href="/master-data/products/new" className={`${s.button} ${s.primary}`}>{t("products.new")}</Link> : undefined}>
    <ListToolbar search={page.filters.search} onSearch={value=>page.set("search",value)} searchHint={t("products.searchPlaceholder")} onClear={page.clear}
      status={page.filters.kind} onStatus={value=>page.set("kind",value)} statusLabel={t("fields.kind")} statuses={["finished","material"].map(value=>({value,label:t(`kinds.${value}`)}))}/>
    {error && <p role="alert" className={s.error}>{error}</p>}
    {rows === null && !error && <p className={s.muted}>{messages("loading.default")}</p>}
    {rows?.length === 0 && <section className={s.panel}><h2 style={{ marginTop: 0 }}>{t("products.empty")}</h2><p className={s.muted} style={{ margin: 0 }}>{t("products.emptyHint")}</p></section>}
    {rows && rows.length > 0 && <section className={s.panel}><div className={s.tableWrap}><table className={s.table} aria-label={t("products.title")}>
      <thead><tr>{["code", "name", "key", "kind", "unit", "properties"].map(c => <th key={c}>{t(`fields.${c}`)}</th>)}</tr></thead>
      <tbody>{rows.map(p => <tr key={p.id} style={p.active ? undefined : { opacity: 0.6 }}>
        <td><Link href={`/master-data/products/${p.id}`}><bdi>{p.code}</bdi></Link></td>
        <td>{localName(p, locale)}<div className={s.muted}>{locale === "ar" ? p.name_en : p.name_ar}</div>
          {!p.active && <div className={s.muted}>{t("products.inactive")}</div>}</td>
        <td><bdi dir="ltr">{p.key}</bdi></td>
        <td>{t(`kinds.${p.kind}`)}</td>
        <td>{p.default_unit ? (units.has(p.default_unit) ? units(p.default_unit) : p.default_unit) : "—"}</td>
        <td>{p.properties.length ? joinList(p.properties.map(q => localName(q, locale)), locale) : "—"}</td>
      </tr>)}</tbody>
    </table></div></section>}
    {canLegacy && rows && <LegacyValues products={rows} onMapped={() => { refreshCatalog(); void load(); }} />}
    <Pagination {...page.pagination} disabled={rows===null||page.pending}/>
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
  const [options,setOptions]=useState(products),[mappingSearch,setMappingSearch]=useState<string|null>(null);
  useEffect(()=>{if(mappingSearch===null)setOptions(products);},[products,mappingSearch]);
  useEffect(()=>{if(mappingSearch===null)return;let active=true;const timer=setTimeout(()=>{getProducts({search:mappingSearch,active_only:true,page:1,page_size:50}).then(found=>{if(active)setOptions(found.items);}).catch(()=>{if(active)setOptions([]);});},250);return()=>{active=false;clearTimeout(timer);};},[mappingSearch]);
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
        <td>{canMap ? <RecordCombobox aria-label={t("mapTo")} onSearch={setMappingSearch} value={chosen[r.value] ?? ""} onChange={e => setChosen(old => ({ ...old, [r.value]: e }))}>
          <option value="">—</option>{options.filter(p => p.active).map(p => <option key={p.id} value={p.id}>{localName(p, locale)}</option>)}
        </RecordCombobox> : "—"}</td>
        <td><span className={s.actions}>
          {canMap && <button type="button" className={`${s.button} ${s.primary}`} disabled={!chosen[r.value] || busy !== null} onClick={() => void map(r.value)}>{t("map")}</button>}
          {canCreate && <Link className={s.button} href={`/master-data/products/new?name=${encodeURIComponent(r.value.trim())}&key=${encodeURIComponent(r.suggested_key)}`}>
            {t("create")}</Link>}
        </span></td>
      </tr>)}</tbody>
    </table></div>
  </section>;
}

export function ProductForm(props: { productId?: string; initialName?: string; initialKey?: string }) {
  const editor = useProductEditor(props), router = useRouter();
  const t=useTranslations("masterdata");
  const { messages, saved, loading, busy, error, canEdit, valid } = editor;
  const title = props.productId ? (saved ? `${saved.code} — ${saved.name_ar}` : t("products.editTitle")) : t("products.createTitle");
  const back = <Link href="/master-data/products" className={s.button}>{t("products.back")}</Link>;
  return <PageFrame title={title} subtitle={t("products.formSubtitle")} action={back}>
    {loading ? <p className={s.muted}>{messages("loading.default")}</p> : <form aria-label={title} onSubmit={async event=>{event.preventDefault();const result=await editor.save();if(result)router.push(`/master-data/products/${result.id}`);}}>
      <ProductFormFields editor={editor}/>
      {error && <p role="alert" className={s.error}>{error}</p>}
      {canEdit && <div className={s.actions}><button type="submit" className={`${s.button} ${s.primary}`} disabled={!valid || busy}>{t("save")}</button><Link href="/master-data/products" className={s.button}>{t("cancel")}</Link></div>}
    </form>}
  </PageFrame>;
}
