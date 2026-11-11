"use client";
import { useEffect, useState } from "react";
import { useLocale } from "next-intl";
import { apiClient } from "@/lib/api-client";
import row from "@/components/forms/control-row.module.css";
import s from "@/features/production-demands/demands.module.css";
export type Option = { address?: string|null; city?: string|null; city_other?: string|null; country?: string|null; location_url?: string|null; id: string; name: string; plate?: string; affiliation?: string; active?: boolean; contact_id?: string|null; phone?: string|null; email?: string|null; identity_no?: string|null; worker_type?: string; default_vehicle_id?: string|null; license_expiry?: string|null };

export function DirectorySelect({ path, value, label, onChange }: { path: string; value?: string | null; label: string; onChange: (id: string, row?: Option) => void }) {
  const ar=useLocale()==="ar";
  const [query,setQuery]=useState("");
  const [rows,setRows]=useState<Option[]>([]);
  const [error,setError]=useState(false);
  useEffect(()=>{let live=true; const timer=setTimeout(()=>{
    apiClient<Option[]>(`${path}?search=${encodeURIComponent(query)}${path.endsWith("/options") && value ? `&selected_id=${encodeURIComponent(value)}` : ""}`).then(found=>{if(live){setRows(old=>[...found.filter(r=>r.active!==false),...old.filter(r=>r.id===value&&!found.some(n=>n.id===r.id))]);setError(false);}}).catch(()=>{if(live)setError(true);});
  },200);return()=>{live=false;clearTimeout(timer);};},[path,query,value]);
  return <div className={s.field}><span>{label}</span>
    <div className={row.directoryRow}><input aria-label={`${label} — ${ar?"بحث":"Search"}`} value={query} onChange={e=>setQuery(e.target.value)} placeholder={ar?"ابحث في السجلات المحفوظة":"Search saved records"}/>
    <select aria-label={label} value={value??""} onChange={e=>onChange(e.target.value,rows.find(r=>r.id===e.target.value))}>
      <option value="">{ar?"إدخال لهذه العملية فقط":"Enter for this transaction only"}</option>
      {value&&!rows.some(r=>r.id===value)&&<option value={value}>{ar?"الاختيار المحفوظ في المستند":"Selection saved in document"}</option>}
      {rows.map(r=><option key={r.id} value={r.id}>{r.name}{r.plate?` — ${r.plate}`:""}{r.affiliation?` — ${r.affiliation==="internal"?(ar?"داخلي":"Internal"):(ar?"خارجي":"External")}`:""}</option>)}
    </select></div>{error&&<span role="alert">{ar?"تعذر تحميل السجلات. حاول مجددًا.":"Could not load records. Try again."}</span>}
  </div>;
}

