"use client";
import { useEffect, useState } from "react";
import { useLocale } from "next-intl";
import { apiClient } from "@/lib/api-client";
import s from "@/features/production-demands/demands.module.css";
export type Option = { id: string; name: string; plate?: string; affiliation?: string; active?: boolean; contact_id?: string|null };

export function DirectorySelect({ path, value, label, onChange }: { path: string; value?: string | null; label: string; onChange: (id: string, row?: Option) => void }) {
  const ar=useLocale()==="ar";
  const [query,setQuery]=useState("");
  const [rows,setRows]=useState<Option[]>([]);
  const [error,setError]=useState(false);
  useEffect(()=>{let live=true; const timer=setTimeout(()=>{
    apiClient<Option[]>(`${path}?search=${encodeURIComponent(query)}`).then(found=>{if(live){setRows(old=>[...found.filter(r=>r.active!==false),...old.filter(r=>r.id===value&&!found.some(n=>n.id===r.id))]);setError(false);}}).catch(()=>{if(live)setError(true);});
  },200);return()=>{live=false;clearTimeout(timer);};},[path,query,value]);
  return <div className={s.field}><span>{label}</span>
    <input aria-label={`${label} — ${ar?"بحث":"Search"}`} value={query} onChange={e=>setQuery(e.target.value)} placeholder={ar?"ابحث في السجلات المحفوظة":"Search saved records"}/>
    <select aria-label={label} value={value??""} onChange={e=>onChange(e.target.value,rows.find(r=>r.id===e.target.value))}>
      <option value="">{ar?"إدخال لهذه العملية فقط":"Enter for this transaction only"}</option>
      {value&&!rows.some(r=>r.id===value)&&<option value={value}>{ar?"الاختيار المحفوظ في المستند":"Selection saved in document"}</option>}
      {rows.map(r=><option key={r.id} value={r.id}>{r.name}{r.plate?` — ${r.plate}`:""}{r.affiliation?` — ${r.affiliation==="internal"?(ar?"داخلي":"Internal"):(ar?"خارجي":"External")}`:""}</option>)}
    </select>{error&&<span role="alert">{ar?"تعذر تحميل السجلات. حاول مجددًا.":"Could not load records. Try again."}</span>}
  </div>;
}

export type TransportValues={driver_id?:string|null;vehicle_id?:string|null;carrier_id?:string|null;driver_affiliation?:string|null};
export function DriverAffiliation({value}:{value?:string|null}){const ar=useLocale()==="ar";return <span>{value==="internal"?(ar?"سائق داخلي":"Internal driver"):value==="external"?(ar?"سائق خارجي":"External driver"):(ar?"تصنيف غير محدد — سجل قديم":"Unclassified — legacy record")}</span>;}
export function TransportSelection({value,onChange,carrier=false}: {value:TransportValues;onChange:(v:TransportValues)=>void;carrier?:boolean}){
  const ar=useLocale()==="ar";
  return <div className={s.grid}>
    {carrier?<DirectorySelect path="/shipping/directory/carriers/options" label={ar?"شركة النقل المحفوظة":"Saved carrier"} value={value.carrier_id} onChange={id=>onChange({...value,carrier_id:id||null})}/>:<>
      <DirectorySelect path="/shipping/directory/drivers/options" label={ar?"السائق المحفوظ":"Saved driver"} value={value.driver_id} onChange={(id,row)=>onChange({...value,driver_id:id||null,driver_affiliation:row?.affiliation??value.driver_affiliation})}/>
      <label className={s.field}>{ar?"صفة السائق":"Driver affiliation"}<select value={value.driver_affiliation??""} disabled={!!value.driver_id} onChange={e=>onChange({...value,driver_affiliation:e.target.value||null})}>
        <option value="">{ar?"اختر الصفة":"Choose affiliation"}</option><option value="internal">{ar?"يعمل لدينا — داخلي":"Company employee — internal"}</option><option value="external">{ar?"خارجي":"External"}</option>
      </select></label>
    </>}
    <DirectorySelect path="/shipping/directory/vehicles/options" label={ar?"المركبة المحفوظة":"Saved vehicle"} value={value.vehicle_id} onChange={id=>onChange({...value,vehicle_id:id||null})}/>
    <p className={s.muted}>{ar?"تُنسخ بيانات الاختيار عند الحفظ. الإدخال لهذه العملية لا يضيف سجلًا للدليل، ولا يتطلب السائق حساب دخول.":"Selected details are copied when saved. One-off entry creates no directory record; drivers do not need a login."}</p>
  </div>;
}
