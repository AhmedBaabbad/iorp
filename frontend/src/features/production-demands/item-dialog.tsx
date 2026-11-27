"use client";
import {useState} from "react";
import {useTranslations} from "next-intl";
import {RecordDialog} from "@/components/ui/RecordDialog";
import {UnitSelect} from "@/components/forms/UnitSelect";
import {SpecEditor} from "@/components/forms/SpecEditor";
import {ProductSelect,useProducts} from "@/features/masterdata";
import {normalizeSpecDraft} from "@/lib/spec-rows";
import {demandsApi,type Item} from "./api";
import {errorKey} from "./shared";
import s from "./demands.module.css";

export function DemandItemDialog({demandId,item,salesOrder,onClose,onSaved}:{demandId:string;item?:Item;salesOrder:boolean;onClose:()=>void;onSaved:()=>Promise<void>}){
  const t=useTranslations("production.demands"),products=useProducts();
  const [product,setProduct]=useState(item?.product_type??""),[quantity,setQuantity]=useState(item?.required_quantity??""),[unit,setUnit]=useState(item?.unit??""),[notes,setNotes]=useState(item?.notes??"");
  const [specText,setSpecText]=useState(()=>JSON.stringify(item?.target_spec_json??{})),[error,setError]=useState("");
  const properties=products?.find(p=>p.key===product)?.properties??[];
  return <RecordDialog title={t(item?"editItem":"addItem")} onClose={onClose} error={error?t(`errors.${t.has(`errors.${error}`)?error:"request_failed"}`):undefined} onSave={async()=>{
    setError("");try{
      if(salesOrder&&item?.id)await demandsApi.setItemQuantity(demandId,item.id,quantity,notes||null);
      else{const spec=JSON.parse(specText||"{}");const values={product_type:product,target_spec_json:normalizeSpecDraft(spec,properties),required_quantity:quantity,unit,notes:notes||null};await demandsApi.saveItem(demandId,values,item?.id);}
      await onSaved();return true;
    }catch(e){setError(errorKey(e));return false;}
  }}>
    <label className={s.field}>{t("productType")}<ProductSelect ariaLabel={t("productType")} value={product} disabled={salesOrder} onChange={(key,row)=>{setProduct(key);if(row?.default_unit)setUnit(row.default_unit);}}/></label>
    <label className={s.field}>{t("quantity")}<input required type="number" min="0.001" step="0.001" value={quantity} onChange={e=>setQuantity(e.target.value)}/></label>
    <label className={s.field}>{t("unit")}<UnitSelect ariaLabel={t("unit")} value={unit} disabled={salesOrder} onChange={setUnit}/></label>
    <SpecEditor value={specText} onChange={setSpecText} disabled={salesOrder} template={properties}/>
    <label className={s.field}>{t("itemNotes")}<textarea value={notes} onChange={e=>setNotes(e.target.value)}/></label>
  </RecordDialog>;
}
