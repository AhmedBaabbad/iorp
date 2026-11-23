"use client";
import {useLocale,useTranslations} from "next-intl";
import {useEffect,useState,type CSSProperties} from "react";
import {Combobox} from "@/components/ui/Combobox";
import {customerDisplayName} from "@/lib/customer-name";
import type {CustomerOption} from "@/types/customers";
import {customersByIds,lookupCustomers} from "./customer-api";

/** Server search and selected-record hydration share one input; edits never show an unlabelled id. */
export function CustomerPicker({value,onChange,disabled,required=true,style,ariaLabel}:{
  value:string;onChange:(id:string,customer?:CustomerOption)=>void;disabled?:boolean;required?:boolean;style?:CSSProperties;ariaLabel?:string;
}){
  const locale=useLocale(),t=useTranslations("commercial.customers.picker");
  const [query,setQuery]=useState(""),[rows,setRows]=useState<CustomerOption[]>([]),[chosen,setChosen]=useState<CustomerOption|null>(null);
  const [loading,setLoading]=useState(false),[error,setError]=useState("");
  useEffect(()=>{
    let live=true;setLoading(true);
    const timer=setTimeout(()=>{lookupCustomers(query).then(data=>{if(live){setRows(data);setError("");}})
      .catch(()=>{if(live)setError(t("loadFailed"));}).finally(()=>{if(live)setLoading(false);});},250);
    return()=>{live=false;clearTimeout(timer);};
  },[query,t]);
  useEffect(()=>{
    if(!value){setChosen(null);return;}
    if(chosen?.id===value)return;
    const found=rows.find(row=>row.id===value);if(found){setChosen(found);return;}
    let live=true;customersByIds([value]).then(data=>{if(live)setChosen(data[0]??null);}).catch(()=>{if(live)setError(t("loadFailed"));});
    return()=>{live=false;};
  },[value,rows,chosen?.id,t]);
  const shown=chosen&&!rows.some(row=>row.id===chosen.id)?[chosen,...rows]:rows;
  return <Combobox hideLabel label={ariaLabel??t("choose")} ariaLabel={ariaLabel??t("choose")} placeholder={t("search")}
    value={value} options={shown.map(record=>({id:record.id,name:customerDisplayName(record,locale),detail:record.customer_code,record}))}
    onSearch={setQuery} onChange={(id,option)=>{setChosen(option?.record??null);onChange(id,option?.record);}}
    loading={loading} error={error} disabled={disabled} required={required} style={style}/>;
}
