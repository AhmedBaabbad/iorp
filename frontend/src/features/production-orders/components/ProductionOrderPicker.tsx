"use client";
import {useEffect,useState} from "react";
import {useTranslations} from "next-intl";
import {Combobox} from "@/components/ui/Combobox";
import {lookupProductionOrders} from "../api/production-orders-api";
import type {ProductionOrderListItem} from "../types";

export function ProductionOrderPicker({value,onChange,statuses=[],disabled,required,emptyLabel,ariaLabel,className}:{
  value:string;onChange:(id:string,order?:ProductionOrderListItem)=>void;statuses?:string[];disabled?:boolean;required?:boolean;
  emptyLabel?:string;ariaLabel?:string;className?:string;
}){
  const t=useTranslations("production.productionOrders.picker"),wanted=statuses.join(",");
  const [query,setQuery]=useState(""),[rows,setRows]=useState<ProductionOrderListItem[]>([]),[chosen,setChosen]=useState<ProductionOrderListItem|null>(null);
  const [loading,setLoading]=useState(false),[error,setError]=useState("");
  useEffect(()=>{
    let live=true;setLoading(true);
    const timer=setTimeout(()=>{lookupProductionOrders({search:query,statuses:wanted?wanted.split(","):[]}).then(data=>{if(live){setRows(data);setError("");}})
      .catch(()=>{if(live)setError(t("loadFailed"));}).finally(()=>{if(live)setLoading(false);});},250);
    return()=>{live=false;clearTimeout(timer);};
  },[query,wanted,t]);
  useEffect(()=>{
    if(!value){setChosen(null);return;}
    if(chosen?.id===value)return;
    const found=rows.find(row=>row.id===value);if(found){setChosen(found);return;}
    let live=true;lookupProductionOrders({ids:[value]}).then(data=>{if(live)setChosen(data[0]??null);}).catch(()=>{if(live)setError(t("loadFailed"));});
    return()=>{live=false;};
  },[value,rows,chosen?.id,t]);
  const shown=chosen&&!rows.some(row=>row.id===chosen.id)?[chosen,...rows]:rows;
  return <Combobox hideLabel label={ariaLabel??t("choose")} ariaLabel={ariaLabel??t("choose")} placeholder={emptyLabel??t("search")} value={value}
    options={shown.map(record=>({id:record.id,name:record.production_order_number,detail:record.product_type,record}))} onSearch={setQuery}
    onChange={(id,option)=>{setChosen(option?.record??null);onChange(id,option?.record);}}
    disabled={disabled} required={required} loading={loading} error={error} className={className}/>;
}
