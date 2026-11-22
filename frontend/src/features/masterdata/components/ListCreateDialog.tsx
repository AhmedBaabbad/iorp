"use client";
import Link from "next/link";
import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { RecordDialog } from "@/components/ui/RecordDialog";
import { localName } from "@/lib/local-name";
import { createListItem } from "../api";
import { refreshCatalog, useListItems } from "../catalog";
import { masterdataErrorMessage } from "../masterdata-errors";
import type { ListItem, ListName } from "../types";

export function ListCreateDialog({list,parent,onCreated,onClose}:{list:ListName;parent?:string|null;onCreated:(item:ListItem)=>void;onClose:()=>void}) {
  const t=useTranslations("masterdata"),errors=useTranslations("masterdata.errors"),locale=useLocale();
  const countries=useListItems("country");
  const [nameAr,setNameAr]=useState(""),[nameEn,setNameEn]=useState(""),[parentKey,setParentKey]=useState(parent??"");
  const [error,setError]=useState("");
  return <RecordDialog title={t("select.newItem")} onClose={onClose} error={error}
    disabled={!nameAr.trim()||!nameEn.trim()||(list==="city"&&!parentKey)} onSave={async()=>{
      setError("");
      try { const item=await createListItem(list,{name_ar:nameAr.trim(),name_en:nameEn.trim(),parent_key:list==="city"?parentKey:null});
        await refreshCatalog();onCreated(item);return true;
      } catch(e){setError(masterdataErrorMessage(e,errors));return false;}
    }}>
    <label>{t("fields.name_ar")}<input required dir="rtl" maxLength={120} value={nameAr} onChange={e=>setNameAr(e.target.value)}/></label>
    <label>{t("fields.name_en")}<input required dir="ltr" maxLength={120} value={nameEn} onChange={e=>setNameEn(e.target.value)}/></label>
    {list==="city"&&<label>{t("select.parentCountry")}<select required value={parentKey} onChange={e=>setParentKey(e.target.value)}>
      <option value="">{t("select.chooseItem")}</option>
      {countries?.filter(item=>item.active||item.key===parentKey).map(item=><option key={item.id} value={item.key}>{localName(item,locale)}</option>)}
      {parentKey&&!countries?.some(item=>item.key===parentKey)&&<option value={parentKey}>{parentKey}</option>}
    </select></label>}
    <Link href={`/master-data/lists?list=${list}`} target="_blank" rel="noopener noreferrer">{t("select.manageInNewTab")}</Link>
  </RecordDialog>;
}
