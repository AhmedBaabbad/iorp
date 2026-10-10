"use client";

import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import type { CSSProperties } from "react";

import { usePermission } from "@/features/auth/permission-hooks";
import { MD } from "@/lib/masterdata-permissions";
import { useProducts } from "../catalog";
import type { Product, ProductKind } from "../types";

/**
 * «نوع المنتج» chosen from the organization's products (MD-001); the record stores the product's key. A value the record
 * already holds that is not an active product (a legacy text, or a product since deactivated) stays selectable on it.
 * Until the organization defines its first product, the field stays free text, as before.
 */
export function ProductSelect({ id, value, onChange, kind, required = true, disabled, ariaLabel, className, style }: {
  id?: string; value: string; onChange: (key: string, product?: Product) => void; kind?: ProductKind; required?: boolean; disabled?: boolean;
  ariaLabel?: string; className?: string; style?: CSSProperties;
}) {
  const t = useTranslations("masterdata.select");
  const locale = useLocale();
  const canAdd = usePermission(MD.PRODUCTS_CREATE);
  const all = useProducts();
  const name = (p: Product) => (locale === "ar" ? p.name_ar : p.name_en);

  if (all === null) {
    return <select id={id} className={className} style={style} aria-label={ariaLabel} disabled value=""><option value="">{t("loading")}</option></select>;
  }
  if (all.length === 0) {
    return <span style={{ display: "grid", gap: 4 }}>
      <input id={id} className={className} style={style} aria-label={ariaLabel} required={required} disabled={disabled} maxLength={120} value={value}
        onChange={e => onChange(e.target.value)} />
      <small style={{ color: "var(--text-muted)" }}>{t("noCatalog")}{canAdd ? <> <Link href="/master-data/products/new">{t("define")}</Link></> : null}</small>
    </span>;
  }
  const choices = all.filter(p => p.active && (!kind || p.kind === kind));
  const current = value && !choices.some(p => p.key === value) ? all.find(p => p.key === value) : undefined;
  return <span style={{ display: "grid", gap: 4 }}>
    <select id={id} className={className} style={style} aria-label={ariaLabel} required={required} disabled={disabled} value={value}
      onChange={e => onChange(e.target.value, all.find(p => p.key === e.target.value))}>
      <option value="">{t("choose")}</option>
      {choices.map(p => <option key={p.key} value={p.key}>{name(p)}</option>)}
      {value && !choices.some(p => p.key === value)
        ? <option value={value}>{current ? t("inactive", { name: name(current) }) : t("legacy", { value })}</option> : null}
    </select>
    {canAdd ? <small><Link href="/master-data/products/new" target="_blank">{t("add")}</Link></small> : null}
  </span>;
}
