"use client";
import {useState} from "react";
import {useTranslations} from "next-intl";
import {useRouter} from "next/navigation";
import {RecordDialog} from "@/components/ui/RecordDialog";
import {ProductSelect} from "@/features/masterdata";
import {qualityErrorMessage} from "@/features/quality-checks/components/quality-errors";
import {copySpecification} from "../api";
import type {SpecificationListItem} from "../types";
import s from "@/features/production-demands/demands.module.css";

export function CopySpecificationDialog({source,onClose}:{source:SpecificationListItem;onClose:()=>void}){
  const t=useTranslations("quality.specifications"),errors=useTranslations("quality.errors"),router=useRouter();
  const [draft,setDraft]=useState({code:source.code.slice(0,35)+"-COPY",title:source.title.slice(0,180)+t("copySuffix"),product_type:source.product_type,grade:source.grade??""});
  const [error,setError]=useState("");
  async function save(){
    setError("");
    try{const copied=await copySpecification(source.id,{...draft,grade:draft.grade.trim()||null});router.push(`/quality-specifications/${copied.id}/edit`);return true;}
    catch(error){setError(qualityErrorMessage(error,errors));return false;}
  }
  return <RecordDialog title={t("copyTitle")} onClose={onClose} onSave={save} error={error} disabled={!draft.code.trim()||!draft.title.trim()||!draft.product_type}>
    <label className={s.field}>{t("fields.code")}<input required dir="ltr" maxLength={40} pattern="[A-Za-z0-9_\-]+" value={draft.code} onChange={e=>setDraft({...draft,code:e.target.value})}/></label>
    <label className={s.field}>{t("fields.title")}<input required maxLength={200} value={draft.title} onChange={e=>setDraft({...draft,title:e.target.value})}/></label>
    <label className={s.field}>{t("fields.productType")}<ProductSelect ariaLabel={t("fields.productType")} value={draft.product_type} onChange={product_type=>setDraft({...draft,product_type})}/></label>
    <label className={s.field}>{t("fields.grade")}<input maxLength={80} value={draft.grade} onChange={e=>setDraft({...draft,grade:e.target.value})}/></label>
  </RecordDialog>;
}
