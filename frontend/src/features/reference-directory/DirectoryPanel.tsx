"use client";
import { useCallback, useEffect, useState } from "react";
import { useLocale } from "next-intl";
import { apiClient } from "@/lib/api-client";
import { usePermission } from "@/features/auth/permission-hooks";
import { ListSelect, useListName } from "@/features/masterdata";
import { DirectorySelect } from "./DirectorySelect";
import s from "@/features/production-demands/demands.module.css";

type Row={id:string;name:string;active:boolean;version:number;is_default?:boolean;[key:string]:string|number|boolean|null|undefined};
type Kind="drivers"|"vehicles"|"carriers"|"contacts"|"sites";
const labels:Record<string,[string,string]>={name:["الاسم","Name"],phone:["الهاتف","Phone"],email:["البريد الإلكتروني","Email"],role:["المنصب","Role"],plate:["رقم اللوحة","Plate"],vehicle_type:["نوع المركبة","Vehicle type"],identity_no:["رقم الهوية","Identity number"],address:["العنوان","Address"],location_url:["رابط الموقع","Location URL"],drivers:["السائقون","Drivers"],vehicles:["المركبات","Vehicles"],carriers:["شركات النقل","Carriers"],contacts:["جهات الاتصال","Contacts"],sites:["مواقع التسليم","Delivery sites"]};
const fields:Record<Kind,string[]>={drivers:["name","phone","identity_no"],vehicles:["name","plate","vehicle_type"],carriers:["name","phone"],contacts:["name","phone","email","role"],sites:["name","address","location_url"]};

export function DirectoryPanel({path,kind,writePermission,contactPath}: {path:string;kind:Kind;writePermission:string;contactPath?:string}){
  const ar=useLocale()==="ar", canWrite=usePermission(writePermission);
  const label=(k:string)=>labels[k]?.[ar?0:1]??k;
  const vehicleType=useListName("vehicle_type");  // MD-003: chosen from the organization's vehicle types
  const [rows,setRows]=useState<Row[]>([]),[page,setPage]=useState(1),[pages,setPages]=useState(1),[query,setQuery]=useState("");
  const [draft,setDraft]=useState<Partial<Row>|null>(null),[error,setError]=useState(""),[busy,setBusy]=useState(false);
  const load=useCallback(async()=>{try{const result=await apiClient<Row[]|{items:Row[];pages:number}>(`${path}?page=${page}&search=${encodeURIComponent(query)}`);const found=Array.isArray(result)?result:result?.items;if(!Array.isArray(found))throw new Error("Invalid directory response");setRows(found);setPages(Array.isArray(result)?1:result.pages);setError("");}catch{setError(ar?"تعذر تحميل البيانات":"Could not load records");}},[path,page,query,ar]);
  useEffect(()=>{const timer=setTimeout(()=>void load(),200);return()=>clearTimeout(timer);},[load]);
  const set=(key:string,value:string|boolean|null)=>setDraft(old=>({...old,[key]:value}));
  function edit(row?:Row){const next:Partial<Row>={active:true,is_default:false};for(const f of fields[kind])next[f]=row?.[f]??"";
    if(row){next.id=row.id;next.version=row.version;next.active=row.active;next.is_default=row.is_default;}
    for(const f of kind==="drivers"?["affiliation","workforce_member_id","carrier_id"]:kind==="vehicles"?["carrier_id"]:kind==="sites"?["city","contact_id"]:[])next[f]=row?.[f]??(f==="affiliation"?"external":null);
    setDraft(next);setError("");}
  async function save(){if(!draft||busy)return;setBusy(true);setError("");
    const body:Record<string,unknown>={...draft};delete body.id;if(!["contacts","sites"].includes(kind))delete body.is_default;
    for(const key of Object.keys(body))if(body[key]==="")body[key]=null;
    try{await apiClient(`${path}${draft.id?`/${draft.id}`:""}`,{method:draft.id?"PUT":"POST",body});setDraft(null);await load();}
    catch{setError(ar?"تعذر الحفظ. تحقق من الحقول والصلاحية، أو أعد تحميل السجل إذا عدّله مستخدم آخر.":"Could not save. Check fields and permissions, or reload a record changed by another user.");}finally{setBusy(false);}}
  return <section className={s.panel}><div className={s.actions}><h2>{label(kind)}</h2>{canWrite&&<button type="button" className={s.button} onClick={()=>edit()}>{ar?"إضافة":"Add"}</button>}</div>
    <input aria-label={ar?"بحث":"Search"} placeholder={ar?"بحث بالاسم":"Search by name"} value={query} onChange={e=>{setQuery(e.target.value);setPage(1);}}/>
    {error&&<p role="alert" className={s.error}>{error}</p>}
    <div className={s.tableWrap}><table className={s.table}><thead><tr><th>{label("name")}</th><th>{ar?"التفاصيل":"Details"}</th><th>{ar?"الحالة":"Status"}</th><th/></tr></thead><tbody>{rows.map(r=><tr key={r.id}><td>{r.name}</td><td>{[r.affiliation==="internal"?(ar?"داخلي":"Internal"):r.affiliation==="external"?(ar?"خارجي":"External"):null,r.plate,r.vehicle_type?vehicleType(String(r.vehicle_type)):null,r.phone,r.email,r.address].filter(Boolean).join(" — ")}</td><td>{r.active?(ar?"نشط":"Active"):(ar?"معطل":"Inactive")}{r.is_default?` — ${ar?"افتراضي":"Default"}`:""}</td><td>{canWrite&&<button type="button" className={s.button} onClick={()=>edit(r)}>{ar?"تعديل":"Edit"}</button>}</td></tr>)}</tbody></table></div>
    {pages>1&&<div className={s.actions}><button type="button" disabled={page<=1} onClick={()=>setPage(p=>p-1)}>{ar?"السابق":"Previous"}</button><span>{page} / {pages}</span><button type="button" disabled={page>=pages} onClick={()=>setPage(p=>p+1)}>{ar?"التالي":"Next"}</button></div>}
    {draft&&<fieldset disabled={busy} className={s.panel}><legend>{ar?"بيانات السجل":"Record details"}</legend><div className={s.grid}>
      {kind==="drivers"&&<><label className={s.field}>{ar?"صفة السائق":"Driver affiliation"}<select value={String(draft.affiliation)} onChange={e=>{set("affiliation",e.target.value);set("workforce_member_id",null);}}><option value="internal">{ar?"داخلي — يعمل لدينا":"Internal — employee"}</option><option value="external">{ar?"خارجي":"External"}</option></select></label>{draft.affiliation==="internal"&&<DirectorySelect path="/shipping/directory/workers" value={draft.workforce_member_id as string} label={ar?"الموظف (لا يشترط حساب دخول)":"Employee (no login required)"} onChange={(id,row)=>{set("workforce_member_id",id||null);set("name",row?.name??"");}}/>}</>}
      {fields[kind].map(f=>f==="vehicle_type"?<label className={s.field} key={f}>{label(f)}<ListSelect list="vehicle_type" value={String(draft[f]??"")} onChange={v=>set(f,v||null)} ariaLabel={label(f)}/></label>:<label className={s.field} key={f}>{label(f)}<input type={f==="email"?"email":"text"} value={String(draft[f]??"")} disabled={kind==="drivers"&&draft.affiliation==="internal"&&["name","phone"].includes(f)} onChange={e=>set(f,e.target.value)} maxLength={f==="address"?1000:f==="location_url"?500:f==="phone"?30:200}/></label>)}
      {kind==="sites"&&<><ListSelect list="city" value={String(draft.city??"")} onChange={v=>set("city",v||null)} ariaLabel={ar?"المدينة":"City"}/>{contactPath&&<DirectorySelect path={contactPath} value={draft.contact_id as string} label={ar?"جهة الاتصال بالموقع":"Site contact"} onChange={id=>set("contact_id",id||null)}/>}</>}
      {["drivers","vehicles"].includes(kind)&&<DirectorySelect path="/shipping/directory/carriers/options" value={draft.carrier_id as string} label={ar?"شركة النقل (اختياري)":"Carrier (optional)"} onChange={id=>set("carrier_id",id||null)}/>}
      <label><input type="checkbox" checked={!!draft.active} onChange={e=>{set("active",e.target.checked);if(!e.target.checked)set("is_default",false);}}/>{ar?"نشط":"Active"}</label>
      {["contacts","sites"].includes(kind)&&<label><input type="checkbox" checked={!!draft.is_default} disabled={!draft.active} onChange={e=>set("is_default",e.target.checked)}/>{ar?"افتراضي":"Default"}</label>}
    </div><div className={s.actions}><button type="button" className={`${s.button} ${s.primary}`} onClick={()=>void save()} disabled={!String(draft.name??"").trim()}>{ar?"حفظ":"Save"}</button><button type="button" className={s.button} onClick={()=>setDraft(null)}>{ar?"إلغاء":"Cancel"}</button></div></fieldset>}
  </section>;
}

export function CustomerDirectory({id}:{id:string}){const base=`/commercial/customers/${id}/directory`;return <><DirectoryPanel path={`${base}/contacts`} kind="contacts" writePermission="commercial:customers:update"/><DirectoryPanel path={`${base}/sites`} contactPath={`${base}/contacts`} kind="sites" writePermission="commercial:customers:update"/></>;}
