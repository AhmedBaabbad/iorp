"use client";
import {useState} from "react";
import {useTranslations} from "next-intl";
import {RecordDialog} from "@/components/ui/RecordDialog";
import {qualityErrorMessage} from "@/features/quality-checks/components/quality-errors";
import {createParameter} from "../api";
import type {ParameterKind,TestParameter} from "../types";
import s from "@/features/production-demands/demands.module.css";
export type ParameterDraft={code:string;name_ar:string;name_en:string;kind:ParameterKind;unit:string;method_ar:string;method_en:string};
export const EMPTY_PARAMETER:ParameterDraft={code:"",name_ar:"",name_en:"",kind:"numeric",unit:"",method_ar:"",method_en:""};
export function ParameterFormFields({draft,set}:{draft:ParameterDraft;set:(field:keyof ParameterDraft,value:string)=>void}) {
  const t=useTranslations("quality.parameters");
  return <>      <div className={s.grid}>
        <label className={s.field}>{t("fields.code")}<input required maxLength={40} pattern="[A-Za-z0-9_\-]+" dir="ltr" value={draft.code} onChange={e => set("code", e.target.value)} /></label>
        <label className={s.field}>{t("fields.nameAr")}<input required maxLength={120} value={draft.name_ar} onChange={e => set("name_ar", e.target.value)} /></label>
        <label className={s.field}>{t("fields.nameEn")}<input required maxLength={120} dir="ltr" value={draft.name_en} onChange={e => set("name_en", e.target.value)} /></label>
        <label className={s.field}>{t("fields.kind")}
          <select value={draft.kind} onChange={e => set("kind", e.target.value)}>
            <option value="numeric">{t("kinds.numeric")}</option><option value="attribute">{t("kinds.attribute")}</option>
          </select>
        </label>
        {draft.kind === "numeric" && <label className={s.field}>{t("fields.unit")}<input maxLength={16} dir="ltr" value={draft.unit} onChange={e => set("unit", e.target.value)} /></label>}
        {(["ar","en"] as const).map(lang=><label className={s.field} key={lang}>{t(`fields.method_${lang}`)}<input maxLength={255} dir={lang==="ar"?"rtl":"ltr"} value={draft[`method_${lang}`]} onChange={e=>set(`method_${lang}`,e.target.value)}/></label>)}
      </div>
      <p className={s.muted}>{t("kindHint")}</p></>;
}
export function ParameterCreateDialog({onCreated,onClose}:{onCreated:(parameter:TestParameter)=>void;onClose:()=>void}) {
  const t=useTranslations("quality.parameters"),errors=useTranslations("quality.errors");
  const [draft,setDraft]=useState(EMPTY_PARAMETER),[error,setError]=useState("");
  return <RecordDialog title={t("newTitle")} error={error} onClose={onClose} disabled={!draft.code.trim()||!draft.name_ar.trim()||!draft.name_en.trim()} onSave={async()=>{
    setError("");try{const parameter=await createParameter({...draft,unit:draft.kind==="numeric"?draft.unit||null:null,method_ar:draft.method_ar||null,method_en:draft.method_en||null});onCreated(parameter);return true;}
    catch(e){setError(qualityErrorMessage(e,errors));return false;}
  }}><div style={{gridColumn:"1 / -1"}}><ParameterFormFields draft={draft} set={(field,value)=>setDraft(old=>({...old,[field]:value}))}/></div></RecordDialog>;
}
