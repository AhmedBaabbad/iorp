"use client";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { apiClient } from "@/lib/api-client";
import { usePermission } from "@/features/auth/permission-hooks";
import { Combobox } from "@/components/ui/Combobox";
import css from "@/components/ui/records.module.css";
export type Option = { id: string; name: string; detail?: string; is_default?: boolean; active?: boolean;
  address?: string|null; city?: string|null; city_other?: string|null; country?: string|null; location_url?: string|null;
  plate?: string; vehicle_type?: string|null; affiliation?: string; contact_id?: string|null; role?: string|null;
  phone?: string|null; email?: string|null; identity_no?: string|null; worker_type?: string; default_vehicle_id?: string|null; license_expiry?: string|null };

export function DirectorySelect({ path, value, label, onChange, manual = false }: {
  path: string; value?: string|null; label: string; onChange: (id: string, row?: Option) => void; manual?: boolean;
}) {
  const t=useTranslations("directory"), canRead=usePermission("shipping:directory:read");
  const [query,setQuery]=useState(""), [rows,setRows]=useState<Option[]>([]);
  const [loading,setLoading]=useState(false), [error,setError]=useState("");
  useEffect(()=>{
    let live=true;
    const timer=setTimeout(async()=>{
      setLoading(true);
      try {
        const found=await apiClient<Option[]>(`${path}?search=${encodeURIComponent(query)}${path.endsWith("/options")&&value?`&selected_id=${encodeURIComponent(value)}`:""}`);
        let full:Option[]=[];
        if(canRead && /^\/shipping\/directory\/(drivers|vehicles)\/options$/.test(path)) {
          try {
            const details=await apiClient<{items:Option[]}>(`${path.replace("/options","")}?page=1&page_size=100&search=${encodeURIComponent(query)}`);
            full=details.items??[];
          } catch { /* The base options remain usable without directory-read access. */ }
        }
        if(live){
          const next=found.filter(row=>row.active!==false).map(row=>({...row,...full.find(item=>item.id===row.id)}));
          setRows(old=>[...next,...old.filter(row=>row.id===value&&!next.some(item=>item.id===row.id))]);setError("");
        }
      }catch{if(live)setError(t("loadFailed"));}
      finally{if(live)setLoading(false);}
    },200);
    return()=>{live=false;clearTimeout(timer);};
  },[path,query,value,canRead,t]);
  const options=rows.map(row=>({...row,detail:[row.role,row.phone,row.plate,row.affiliation?t(row.affiliation==="internal"?"internal":"external"):null].filter(Boolean).join(" · ")}));
  return <div>
    <Combobox label={label} value={value} options={options} onChange={onChange} onSearch={setQuery} loading={loading} error={error}/>
    {manual&&value&&<button className={css.manual} type="button" aria-label={`${t("manual")} — ${label}`} onClick={()=>onChange("")}>{t("manual")}</button>}
  </div>;
}
