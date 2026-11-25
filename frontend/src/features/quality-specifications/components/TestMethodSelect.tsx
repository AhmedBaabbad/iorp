"use client";
import {useEffect,useState} from "react";
import {useLocale,useTranslations} from "next-intl";
import {Combobox} from "@/components/ui/Combobox";
import {apiClient} from "@/lib/api-client";
import {bilingualText} from "@/lib/bilingual-text";
import {localName} from "@/lib/local-name";
import type {ListItem} from "@/features/masterdata/types";
import s from "@/features/production-demands/demands.module.css";

type Method={method_ar:string;method_en:string};
export function TestMethodSelect({method_ar,method_en,onChange,label,labelAr,labelEn,disabled=false}:{
  method_ar:string|null;method_en:string|null;onChange:(value:Method)=>void;
  label:string;labelAr:string;labelEn:string;disabled?:boolean;
}){
  const locale=useLocale(),t=useTranslations("quality.methods");
  const [rows,setRows]=useState<ListItem[]|null>(null),[error,setError]=useState(false),[attempt,setAttempt]=useState(0);
  useEffect(()=>{let live=true;setError(false);setRows(null);
    apiClient<ListItem[]>("/masterdata/lists?list=test_method").then(items=>{
      if(!Array.isArray(items))throw new Error("Invalid list response");
      if(live)setRows(items);
    }).catch(()=>{if(live)setError(true);});return()=>{live=false;};
  },[attempt]);
  if(error)return <div role="alert">{t("loadFailed")} <button type="button" disabled={disabled} onClick={()=>setAttempt(value=>value+1)}>{t("retry")}</button></div>;
  if(rows===null)return <Combobox label={label} value={null} options={[]} onChange={()=>{}} disabled loading/>;
  if(!rows.length)return <div className={s.grid} style={{gridColumn:"1 / -1"}}>
    <label className={s.field}>{labelAr}<input maxLength={255} dir="rtl" disabled={disabled} value={method_ar??""} onChange={event=>onChange({method_ar:event.target.value,method_en:method_en??""})}/></label>
    <label className={s.field}>{labelEn}<input maxLength={255} dir="ltr" disabled={disabled} value={method_en??""} onChange={event=>onChange({method_ar:method_ar??"",method_en:event.target.value})}/></label>
  </div>;
  const selected=rows.find(row=>method_en?row.name_en===method_en:Boolean(method_ar)&&row.name_ar===method_ar);
  const legacy=!selected&&Boolean(method_en||method_ar);
  const options=rows.filter(row=>row.active||row===selected).map(row=>({id:row.id,name:localName(row,locale),row}));
  return <Combobox label={label} value={selected?.id??(legacy?"legacy-method":null)} disabled={disabled}
    options={[...options,...(legacy?[{id:"legacy-method",name:bilingualText({method_ar,method_en},"method",locale),detail:t("legacyValue"),row:undefined}]:[])]}
    onChange={id=>{if(id==="legacy-method")return;const row=rows.find(item=>item.id===id);
      onChange({method_en:row?.name_en??"",method_ar:row?.name_ar??""});}}/>;
}
