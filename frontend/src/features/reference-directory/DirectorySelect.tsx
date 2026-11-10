"use client";
import { useEffect, useState } from "react";
import { useLocale } from "next-intl";
import { apiClient } from "@/lib/api-client";
import { usePermission } from "@/features/auth/permission-hooks";
import { DirectorySelect, type Option } from "./RecordSelect";
import { QuickDriverDialog } from "./QuickDriverDialog";
import s from "@/features/production-demands/demands.module.css";
export { DirectorySelect, type Option } from "./RecordSelect";
export type TransportValues={driver_id?:string|null;vehicle_id?:string|null;carrier_id?:string|null;driver_affiliation?:string|null};
export function DriverAffiliation({value}:{value?:string|null}){const ar=useLocale()==="ar";return <span>{value==="internal"?(ar?"سائق داخلي":"Internal driver"):value==="external"?(ar?"سائق خارجي":"External driver"):(ar?"تصنيف غير محدد — سجل قديم":"Unclassified — legacy record")}</span>;}
export function TransportSelection({value,onChange,carrier=false}: {value:TransportValues;onChange:(v:TransportValues)=>void;carrier?:boolean}){
  const ar=useLocale()==="ar";
  const canCreateShipment=usePermission("shipping:shipments:create"), canUpdateShipment=usePermission("shipping:shipments:update");
  const canCreateReceipt=usePermission("procurement:receipts:create"), canUpdateReceipt=usePermission("procurement:receipts:update");
  const [quick,setQuick]=useState(false), [selected,setSelected]=useState<Option|null>(null);
  useEffect(()=>{let live=true;if(!value.driver_id){setSelected(null);return;}
    apiClient<Option[]>(`/shipping/directory/drivers/options?selected_id=${encodeURIComponent(value.driver_id)}`)
      .then(rows=>{if(live)setSelected(rows.find(row=>row.id===value.driver_id)??null);}).catch(()=>{});
    return()=>{live=false;};},[value.driver_id]);
  function choose(row:Option){setSelected(row);setQuick(false);onChange({...value,driver_id:row.id,driver_affiliation:row.affiliation??"external",
    vehicle_id:value.vehicle_id||row.default_vehicle_id||null});}
  const now=new Date(), today=`${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,"0")}-${String(now.getDate()).padStart(2,"0")}`;
  return <div className={s.grid}>
    {carrier?<DirectorySelect path="/shipping/directory/carriers/options" label={ar?"شركة النقل المحفوظة":"Saved carrier"} value={value.carrier_id} onChange={id=>onChange({...value,carrier_id:id||null})}/>:<>
      <DirectorySelect path="/shipping/directory/drivers/options" label={ar?"السائق المحفوظ":"Saved driver"} value={value.driver_id} onChange={(id,row)=>{if(row)choose(row);else{setSelected(null);onChange({...value,driver_id:id||null});}}}/>
      {(canCreateShipment||canUpdateShipment||canCreateReceipt||canUpdateReceipt)&&<div><button type="button" className={s.button} onClick={()=>setQuick(true)}>{ar?"+ سائق جديد":"+ New driver"}</button></div>}
      {selected?.license_expiry&&selected.license_expiry<today&&<p role="status" className={s.error}>{ar?"رخصة السائق منتهية":"Driver license expired"}</p>}
      {quick&&<QuickDriverDialog onClose={()=>setQuick(false)} onSelect={choose}/>}
      <label className={s.field}>{ar?"صفة السائق":"Driver affiliation"}<select value={value.driver_affiliation??""} disabled={!!value.driver_id} onChange={e=>onChange({...value,driver_affiliation:e.target.value||null})}>
        <option value="">{ar?"اختر الصفة":"Choose affiliation"}</option><option value="internal">{ar?"يعمل لدينا — داخلي":"Company employee — internal"}</option><option value="external">{ar?"خارجي":"External"}</option>
      </select></label>
    </>}
    <DirectorySelect path="/shipping/directory/vehicles/options" label={ar?"المركبة المحفوظة":"Saved vehicle"} value={value.vehicle_id} onChange={id=>onChange({...value,vehicle_id:id||null})}/>
    <p className={s.muted}>{ar?"تُنسخ بيانات الاختيار عند الحفظ. للإضافة إلى الدليل استخدم زر + سائق جديد؛ الإدخال لهذه العملية لا يضيف سجلًا، ولا يتطلب السائق حساب دخول.":"Selected details are copied when saved. Use + New driver to add a directory record. One-off entry creates no record; drivers do not need a login."}</p>
  </div>;
}
