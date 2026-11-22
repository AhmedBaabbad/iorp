"use client";
import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { apiClient } from "@/lib/api-client";
import { usePermission } from "@/features/auth/permission-hooks";
import { DirectorySelect, type Option } from "./RecordSelect";
import { QuickDriverDialog } from "./QuickDriverDialog";
import s from "@/features/production-demands/demands.module.css";
export { DirectorySelect, type Option } from "./RecordSelect";
export type TransportValues={driver_id?:string|null;vehicle_id?:string|null;carrier_id?:string|null;driver_affiliation?:string|null};
export type TransportKind="driver"|"vehicle"|"carrier";
export function DriverAffiliation({value}:{value?:string|null}){
  const t=useTranslations("directory");return <span>{t(value==="internal"?"internalDriver":value==="external"?"externalDriver":"unclassified")}</span>;
}
export function TransportSelection({value,onChange,carrier=false,onRecord}:{
  value:TransportValues;onChange:(value:TransportValues)=>void;carrier?:boolean;onRecord?:(kind:TransportKind,row?:Option)=>void;
}){
  const t=useTranslations("directory"),canRead=usePermission("shipping:directory:read");
  const canCreateShipment=usePermission("shipping:shipments:create"),canUpdateShipment=usePermission("shipping:shipments:update");
  const canCreateReceipt=usePermission("procurement:receipts:create"),canUpdateReceipt=usePermission("procurement:receipts:update");
  const [quick,setQuick]=useState(false),[selected,setSelected]=useState<Option|null>(null);
  const current=useRef(value);current.current=value;
  useEffect(()=>{let live=true;if(!value.driver_id){setSelected(null);return;}
    apiClient<Option[]>(`/shipping/directory/drivers/options?selected_id=${encodeURIComponent(value.driver_id)}`)
      .then(rows=>{if(live)setSelected(rows.find(row=>row.id===value.driver_id)??null);}).catch(()=>{});
    return()=>{live=false;};},[value.driver_id]);
  async function choose(row:Option){
    if(row.id===value.driver_id){setSelected(row);setQuick(false);return;}
    setSelected(row);setQuick(false);onRecord?.("driver",row);
    const vehicle=value.vehicle_id||row.default_vehicle_id||null;
    onChange({...value,driver_id:row.id,driver_affiliation:row.affiliation??"external",vehicle_id:vehicle});
    if(!value.vehicle_id&&vehicle){
      try{
        const options=await apiClient<Option[]>(`/shipping/directory/vehicles/options?selected_id=${encodeURIComponent(vehicle)}`);
        let found=options.find(item=>item.id===vehicle);
        if(canRead&&found){
          const data=await apiClient<{items:Option[]}>(`/shipping/directory/vehicles?page=1&page_size=100&search=${encodeURIComponent(found.plate??found.name)}`);
          found=data.items?.find(item=>item.id===vehicle)??found;
        }
        if(found&&current.current.vehicle_id===vehicle)onRecord?.("vehicle",found);
      }catch{/* The server still resolves the selected default vehicle at save time. */}
    }
  }
  const now=new Date(),today=`${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,"0")}-${String(now.getDate()).padStart(2,"0")}`;
  return <div className={s.grid}>
    {carrier?<DirectorySelect manual path="/shipping/directory/carriers/options" label={t("savedCarrier")} value={value.carrier_id}
      onChange={(id,row)=>{if((id||null)===(value.carrier_id??null))return;onRecord?.("carrier",row);onChange({...value,carrier_id:id||null});}}/>:<>
      <DirectorySelect manual path="/shipping/directory/drivers/options" label={t("savedDriver")} value={value.driver_id}
        onChange={(id,row)=>{if(row)void choose(row);else{setSelected(null);onRecord?.("driver");onChange({...value,driver_id:id||null});}}}/>
      {(canCreateShipment||canUpdateShipment||canCreateReceipt||canUpdateReceipt)&&<div><button className={s.button} type="button" onClick={()=>setQuick(true)}>{t("addDriver")}</button></div>}
      {selected?.license_expiry&&selected.license_expiry<today&&<p role="status" className={s.error}>{t("licenseExpired")}</p>}
      {quick&&<QuickDriverDialog onClose={()=>setQuick(false)} onSelect={row=>void choose(row)}/>}
      {!value.driver_id&&<label className={s.field}>{t("driverAffiliation")}<select value={value.driver_affiliation??""} onChange={event=>onChange({...value,driver_affiliation:event.target.value||null})}>
        <option value="">{t("chooseAffiliation")}</option><option value="internal">{t("internal")}</option><option value="external">{t("external")}</option>
      </select></label>}
    </>}
    <DirectorySelect manual path="/shipping/directory/vehicles/options" label={t("savedVehicle")} value={value.vehicle_id}
      onChange={(id,row)=>{if((id||null)===(value.vehicle_id??null))return;onRecord?.("vehicle",row);onChange({...value,vehicle_id:id||null});}}/>
    {!canRead&&value.driver_id&&onRecord&&<p className={s.muted}>{t("transportLimited")}</p>}
  </div>;
}
