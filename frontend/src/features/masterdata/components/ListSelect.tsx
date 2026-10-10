"use client";

import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import type { CSSProperties } from "react";

import { usePermission } from "@/features/auth/permission-hooks";
import { MD } from "@/lib/masterdata-permissions";
import { useListItems } from "../catalog";
import type { ListItem, ListName } from "../types";

/**
 * A sector, opportunity source, country or city chosen from the organization's list (MD-002); the record stores the item's
 * key. A city is offered for the chosen country (`parent`). A value the record already holds that is not an active item
 * stays selectable on it. Until the organization adds the first item to the list, the field stays free text, as before.
 */
export function ListSelect({ id, list, value, onChange, parent, required = false, disabled, ariaLabel, className, style }: {
  id?: string; list: ListName; value: string; onChange: (key: string, item?: ListItem) => void; parent?: string | null; required?: boolean;
  disabled?: boolean; ariaLabel?: string; className?: string; style?: CSSProperties;
}) {
  const t = useTranslations("masterdata.select");
  const locale = useLocale();
  const canManage = usePermission(MD.LISTS_UPDATE);
  const all = useListItems(list);
  const name = (i: ListItem) => (locale === "ar" ? i.name_ar : i.name_en);

  if (all === null) {
    return <select id={id} className={className} style={style} aria-label={ariaLabel} disabled value=""><option value="">{t("loading")}</option></select>;
  }
  if (all.length === 0) {
    return <input id={id} className={className} style={style} aria-label={ariaLabel} required={required} disabled={disabled} maxLength={120} value={value}
      onChange={e => onChange(e.target.value)} />;
  }
  const choices = all.filter(i => i.active && (!parent || !i.parent_key || i.parent_key === parent));
  const current = value && !choices.some(i => i.key === value) ? all.find(i => i.key === value) : undefined;
  return <span style={{ display: "grid", gap: 4 }}>
    <select id={id} className={className} style={style} aria-label={ariaLabel} required={required} disabled={disabled} value={value}
      onChange={e => onChange(e.target.value, all.find(i => i.key === e.target.value))}>
      <option value="">{t("chooseItem")}</option>
      {choices.map(i => <option key={i.key} value={i.key}>{name(i)}</option>)}
      {value && !choices.some(i => i.key === value)
        ? <option value={value}>{current ? t("inactive", { name: name(current) }) : t("legacy", { value })}</option> : null}
    </select>
    {canManage ? <small><Link href={`/master-data/lists?list=${list}`} target="_blank">{t("manageList")}</Link></small> : null}
  </span>;
}
