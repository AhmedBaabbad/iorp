"use client";
import { useEffect, useState } from "react";
import { useLocale } from "next-intl";
import { apiClient } from "@/lib/api-client";
import type { ListItem, ListName } from "@/features/masterdata/types";

/** Store the selected canonical text as an operational snapshot, not a live display name. */
export function ReferenceTextSelect({list,value,onChange,disabled,ariaLabel}: {list:ListName;value:string;onChange:(value:string)=>void;disabled?:boolean;ariaLabel?:string}){
  const ar=useLocale()==="ar";
  const [rows,setRows]=useState<ListItem[]|null>(null),[error,setError]=useState(false);
  useEffect(()=>{let live=true;apiClient<ListItem[]>(`/masterdata/lists?list=${list}`).then(v=>{if(live){setRows(v);setError(false);}}).catch(()=>{if(live)setError(true);});return()=>{live=false;};},[list]);
  if(error)return <span role="alert">{ar?"تعذر تحميل القائمة؛ تحقق من صلاحية عرض القوائم المرجعية.":"Could not load list; check reference-list read permission."}</span>;
  if(rows===null)return <select disabled aria-label={ariaLabel}><option>{ar?"جار التحميل":"Loading"}</option></select>;
  if(!rows.length)return <input aria-label={ariaLabel} maxLength={200} value={value} onChange={e=>onChange(e.target.value)} disabled={disabled}/>;
  return <select aria-label={ariaLabel} value={value} onChange={e=>onChange(e.target.value)} disabled={disabled}><option value="">—</option>
    {value&&!rows.some(r=>r.name_en===value)&&<option value={value}>{value}</option>}
    {rows.filter(r=>r.active||r.name_en===value).map(r=><option key={r.id} value={r.name_en}>{ar?r.name_ar:r.name_en}</option>)}
  </select>;
}
