"use client";
import {Combobox} from "@/components/ui/Combobox";
import {RecordCombobox} from "@/components/ui/RecordCombobox";

import { localName } from "@/lib/local-name";
import { ListCreateDialog } from "./ListCreateDialog";
import row from "@/components/forms/control-row.module.css";
import { useLocale, useTranslations } from "next-intl";
import { useState, type CSSProperties } from "react";

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
  const listNames=useTranslations("masterdata");
  const locale = useLocale();
  const canManage = usePermission(MD.LISTS_UPDATE);
  const all = useListItems(list);
  const [creating,setCreating]=useState(false);
  const name = (i: ListItem) => localName(i, locale);

  const choices = (all??[]).filter(i => i.active && (!parent || !i.parent_key || i.parent_key === parent));
  const current = value && !choices.some(i => i.key === value) ? all?.find(i => i.key === value) : undefined;
  return <span className={row.row}>
    {all===null?<Combobox hideLabel label={ariaLabel??t("loading")} ariaLabel={ariaLabel??t("loading")} id={id} disabled value="" options={[]} onChange={()=>{}} loading/>:all.length===0?
      <input id={id} className={className} style={style} aria-label={ariaLabel} required={required} disabled={disabled} maxLength={120} value={value} onChange={e=>onChange(e.target.value)}/>:
    <RecordCombobox id={id} className={className} style={style} aria-label={ariaLabel??listNames(`lists.names.${list}`)} required={required} disabled={disabled} value={value}
      onChange={e => onChange(e, all.find(i => i.key === e))}>
      <option value="">{t("chooseItem")}</option>
      {choices.map(i => <option key={i.key} value={i.key}>{name(i)}</option>)}
      {value && !choices.some(i => i.key === value)
        ? <option value={value}>{current ? t("inactive", { name: name(current) }) : t("legacy", { value })}</option> : null}
    </RecordCombobox>}
    {canManage&&<button type="button" className={row.manage} disabled={disabled||all===null} onClick={()=>setCreating(true)} aria-label={t("addItemTo",{label:ariaLabel??listNames(`lists.names.${list}`)})}>{t("addItem")}</button>}
    {creating&&<ListCreateDialog list={list} parent={parent} onClose={()=>setCreating(false)} onCreated={item=>onChange(item.key,item)}/>}
  </span>;
}
