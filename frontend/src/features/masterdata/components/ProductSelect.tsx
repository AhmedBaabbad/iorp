"use client";
import {Combobox} from "@/components/ui/Combobox";
import {RecordCombobox} from "@/components/ui/RecordCombobox";

import { localName } from "@/lib/local-name";
import { ProductCreateDialog } from "./ProductFormFields";
import row from "@/components/forms/control-row.module.css";
import { useLocale, useTranslations } from "next-intl";
import { useState, type CSSProperties } from "react";

import { usePermission } from "@/features/auth/permission-hooks";
import { MD } from "@/lib/masterdata-permissions";
import { useProducts } from "../catalog";
import type { Product, ProductKind } from "../types";

/**
 * «نوع المنتج» chosen from the organization's products (MD-001); the record stores the product's key. A value the record
 * already holds that is not an active product (a legacy text, or a product since deactivated) stays selectable on it.
 * Until the organization defines its first product, the field stays free text, as before.
 */
type ProductOption = Pick<Product,"key"|"name_ar"|"name_en"|"active">;
type ProductSelectProps = {
  id?: string; value: string; onChange: (key: string, product?: Product) => void; kind?: ProductKind; required?: boolean; disabled?: boolean;
  ariaLabel?: string; className?: string; style?: CSSProperties;
  catalogOptions?: ProductOption[]; allowFreeText?: boolean;
};
export function ProductSelect(props:ProductSelectProps){
  return props.catalogOptions ? <ProductSelectControl {...props} all={props.catalogOptions}/> : <CatalogProductSelect {...props}/>;
}
function CatalogProductSelect(props:ProductSelectProps){
  const all=useProducts();
  return <ProductSelectControl {...props} all={all}/>;
}
function ProductSelectControl({ id, value, onChange, kind, required = true, disabled, ariaLabel, className, style, all, allowFreeText = true }: ProductSelectProps & {all:ProductOption[]|null}) {
  const t = useTranslations("masterdata.select");
  const locale = useLocale();
  const canAdd = usePermission(MD.PRODUCTS_CREATE);
  const [creating,setCreating]=useState(false);
  const name = (p: ProductOption) => localName(p, locale);

  const choices = (all??[]).filter(p => p.active && (!kind || !("kind" in p) || p.kind === kind));
  const current = value && !choices.some(p => p.key === value) ? all?.find(p => p.key === value) : undefined;
  return <span style={{ display: "grid", gap: 4 }}>
    {all===null?<Combobox hideLabel label={ariaLabel??t("loading")} ariaLabel={ariaLabel??t("loading")} id={id} disabled value="" options={[]} onChange={()=>{}} loading/>:all.length===0&&allowFreeText?<>
      <input id={id} className={className} style={style} aria-label={ariaLabel} required={required} disabled={disabled} maxLength={120} value={value} onChange={e=>onChange(e.target.value)}/>
      <small style={{color:"var(--text-muted)"}}>{t("noCatalog")}</small></>:
    <RecordCombobox id={id} className={className} style={style} aria-label={ariaLabel} required={required} disabled={disabled} value={value}
      onChange={e => {const selected=all.find(p=>p.key===e);onChange(e,selected&&"id" in selected?selected as Product:undefined);}}>
      <option value="">{t("choose")}</option>
      {choices.map(p => <option key={p.key} value={p.key}>{name(p)}</option>)}
      {value && !choices.some(p => p.key === value)
        ? <option value={value}>{current ? t("inactive", { name: name(current) }) : t("legacy", { value })}</option> : null}
    </RecordCombobox>}
    {canAdd&&<button type="button" className={row.manage} disabled={disabled||all===null} onClick={()=>setCreating(true)}>{t("add")}</button>}
    {creating&&<ProductCreateDialog kind={kind} onClose={()=>setCreating(false)} onCreated={product=>onChange(product.key,product)}/>}
  </span>;
}
