"use client";
import {useListPage} from "@/hooks/useListPage";
import {Pagination,ListToolbar} from "@/components/pagination";
import type {Page} from "@/lib/pagination";
import {queryString} from "@/lib/page-response";
import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { RecordDialog } from "@/components/ui/RecordDialog";
import { MapLink } from "@/components/MapLink";
import { CountryCityFields, cityLabel } from "@/components/forms/CountryCityFields";
import { apiErrorCode, getApiErrorMessage } from "@/lib/api-error-handler";
import { apiClient } from "@/lib/api-client";
import { usePermission } from "@/features/auth/permission-hooks";
import { ListSelect, useListName } from "@/features/masterdata";
import { DirectorySelect } from "./RecordSelect";
import { DriverFields, type DriverDraft } from "./DriverFields";
import s from "@/features/production-demands/demands.module.css";

type Row={id:string;name:string;active:boolean;version:number;is_default?:boolean;[key:string]:string|number|boolean|null|undefined};
export type DirectoryKind="drivers"|"vehicles"|"carriers"|"contacts"|"sites";
const fields:Record<DirectoryKind,string[]>={drivers:["name","phone","email","identity_no","license_no","license_expiry","vehicle_type","notes"],vehicles:["name","plate","vehicle_type"],carriers:["name","phone"],contacts:["name","role","phone","email"],sites:["name","address","location_url"]};
const columns:Record<DirectoryKind,string[]>={
  drivers:["name","affiliation","phone","identity_no","license_no","license_expiry","default_vehicle_id","carrier_id","status"],
  vehicles:["name","plate","vehicle_type","carrier_id","status"],carriers:["name","phone","status"],
  contacts:["name","role","phone","email","is_default","status"],sites:["name","city","address","contact_name","map","is_default","status"],
};

export function DirectoryPanel({path,kind,writePermission,contactPath}:{path:string;kind:DirectoryKind;writePermission:string;contactPath?:string}){
  const t=useTranslations("directory"),messages=useTranslations("messages"),canWrite=usePermission(writePermission);
  const cityName=useListName("city",key=>key),countryName=useListName("country"),vehicleType=useListName("vehicle_type");
  const [rows,setRows]=useState<Row[]>([]);
  const paging=useListPage<Row>({search:""},{},path);
  const {params,accept}=paging;
  const [draft,setDraft]=useState<Partial<Row>|null>(null),[error,setError]=useState(""),[busy,setBusy]=useState(false);
  const [errorCode,setErrorCode]=useState(""),[identityRequired,setIdentityRequired]=useState(true);
  const [names,setNames]=useState<Record<string,string>>({});
  const load=useCallback(async()=>{
    try{
      const result=await apiClient<Row[]|Page<Row>>(`${path}${queryString(params)}`);
      accept(result,setRows);setError("");
    }catch{setError(t("loadFailed"));}
  },[path,params,accept,t]);
  useEffect(()=>{const timer=setTimeout(()=>void load(),200);return()=>clearTimeout(timer);},[load]);
  useEffect(()=>{
    let live=true,request=0;
    async function readNames(){
      const current=++request;
      const result:Record<string,string>={};
      for(const resource of kind==="drivers"?["vehicles","carriers"]:kind==="vehicles"?["carriers"]:[]){
        let page=1,pages=1;
        do{
          const data=await apiClient<Row[]|{items:Row[];pages:number}>(`/shipping/directory/${resource}?page=${page}&page_size=100`);
          for(const row of Array.isArray(data)?data:data.items)result[row.id]=row.plate?`${row.name} — ${row.plate}`:row.name;
          pages=Array.isArray(data)?1:data.pages;page++;
        }while(page<=pages);
      }
      if(live&&current===request)setNames(result);
    }
    const refresh=()=>{void readNames().catch(()=>{});};
    refresh();window.addEventListener("shipping-directory:saved",refresh);
    return()=>{live=false;window.removeEventListener("shipping-directory:saved",refresh);};
  },[kind]);
  const label=(key:string)=>t(`fields.${key}`);
  const set=(key:string,value:string|boolean|null)=>setDraft(old=>({...old,[key]:value}));
  function edit(row?:Row){
    setIdentityRequired(!row||row.affiliation!=="external"||!!row.identity_no);
    const next:Partial<Row>={active:true,is_default:false};for(const field of fields[kind])next[field]=row?.[field]??"";
    if(row)Object.assign(next,{id:row.id,version:row.version,active:row.active,is_default:row.is_default});
    for(const field of kind==="drivers"?["affiliation","workforce_member_id","carrier_id","default_vehicle_id"]:kind==="vehicles"?["carrier_id"]:kind==="sites"?["country","city","city_other","contact_id"]:[])next[field]=row?.[field]??(field==="affiliation"?"external":null);
    if(kind==="sites"&&!row)next.country="sa";
    setDraft(next);setError("");setErrorCode("");
  }
  async function save(){
    if(!draft||busy)return false;setBusy(true);setError("");
    const body:Record<string,unknown>={...draft};delete body.id;if(!["contacts","sites"].includes(kind))delete body.is_default;
    for(const key of Object.keys(body))if(body[key]==="")body[key]=null;
    try{await apiClient(`${path}${draft.id?`/${draft.id}`:""}`,{method:draft.id?"PUT":"POST",body});if(path.startsWith("/shipping/directory/"))window.dispatchEvent(new Event("shipping-directory:saved"));await load();return true;}
    catch(e){const code=apiErrorCode(e);setErrorCode(code??"");setError(code&&t.has(`errors.${code}`)?t(`errors.${code}`):getApiErrorMessage(e,messages));return false;}
    finally{setBusy(false);}
  }
  async function reload(){
    try{
      const result=await apiClient<Row[]|Page<Row>>(`${path}${queryString(params)}`);
      const found=Array.isArray(result)?result:result.items;accept(result,setRows);
      const current=found.find(row=>row.id===draft?.id);if(current)edit(current);else{setDraft(null);await load();}
    }catch(e){setError(getApiErrorMessage(e,messages));}
  }
  const textInput=(field:string)=> <label className={s.field} key={field}>{label(field)}<input
    type={field==="email"?"email":field==="phone"?"tel":"text"} value={String(draft?.[field]??"")}
    onChange={event=>set(field,event.target.value)} required={field==="name"||field==="address"||field==="plate"}
    maxLength={field==="address"?1000:field==="location_url"?500:field==="phone"?30:field==="email"?255:200}/></label>;
  const today=new Date().toLocaleDateString("sv-SE");
  function cell(row:Row,key:string){
    if(key==="status")return t(row.active?"active":"inactive");
    if(key==="is_default")return row.is_default?t("default"):"—";
    if(key==="affiliation")return t(row.affiliation==="internal"?"internal":"external");
    if(key==="vehicle_type")return row.vehicle_type?vehicleType(String(row.vehicle_type)):"—";
    if(key==="carrier_id"||key==="default_vehicle_id")return row[key]?names[String(row[key])]??"—":"—";
    if(key==="city")return cityLabel(String(row.city??""),row.city_other as string|null,cityName);
    if(key==="map")return <MapLink locationUrl={row.location_url as string|null} address={row.address as string|null}
      city={cityLabel(String(row.city??""),row.city_other as string|null,cityName)} country={row.country?countryName(String(row.country)):null}/>;
    if(key==="license_expiry")return <span className={row.license_expiry&&String(row.license_expiry)<today?s.error:undefined}>{row[key]??"—"}</span>;
    return row[key]??"—";
  }
  const invalid=!String(draft?.name??"").trim()||(kind==="sites"&&String(draft?.city??"").endsWith("_other")&&!String(draft?.city_other??"").trim())||(kind==="drivers"&&draft?.affiliation==="external"&&identityRequired&&!String(draft?.identity_no??"").trim());
  return <section className={s.panel} style={{minWidth:0,maxWidth:"100%"}}>
    <div className={s.actions}><h2>{label(kind)}</h2>{canWrite&&<button className={s.button} type="button" onClick={()=>edit()}>{t("add")}</button>}</div>
    <ListToolbar search={paging.filters.search} onSearch={value=>paging.set("search",value)} searchHint={t("searchHint")} onClear={paging.clear}/>
    {error&&!draft&&<p role="alert" className={s.error}>{error}</p>}
    <div className={s.tableWrap}><table className={s.table}><thead><tr>{columns[kind].map(key=><th key={key}>{label(key)}</th>)}<th/></tr></thead>
      <tbody>{rows.map(row=><tr key={row.id}>{columns[kind].map(key=><td key={key} style={{overflowWrap:"anywhere"}}>{cell(row,key)}</td>)}
        <td>{canWrite&&<button className={s.button} type="button" onClick={()=>edit(row)}>{t("edit")}</button>}</td></tr>)}</tbody></table></div>
    <Pagination {...paging.pagination} disabled={paging.pending||busy}/>
    {draft&&<RecordDialog title={`${t(draft.id?"edit":"add")} — ${label(kind)}`} onClose={()=>setDraft(null)} onSave={save} disabled={invalid}
      error={error} errorAction={errorCode==="DIRECTORY_CHANGED"?<button className={s.button} type="button" disabled={busy} onClick={()=>void reload()}>{t("reload")}</button>:undefined}>
      {kind==="drivers"?<>
        <label className={s.field}>{t("driverAffiliation")}<select value={String(draft.affiliation)} onChange={event=>{setIdentityRequired(true);setDraft(old=>({...old,affiliation:event.target.value,workforce_member_id:null,name:"",phone:"",email:"",identity_no:""}));}}>
          <option value="internal">{t("internal")}</option><option value="external">{t("external")}</option></select></label>
        {draft.affiliation==="internal"&&<DirectorySelect path="/shipping/directory/workers" value={draft.workforce_member_id as string} label={t("employee")}
          onChange={(id,row)=>setDraft(old=>({...old,workforce_member_id:id||null,name:row?.name??"",phone:row?.phone??"",email:row?.email??"",identity_no:row?.identity_no??""}))}/>}
        <DriverFields value={draft as DriverDraft} internal={draft.affiliation==="internal"} requireIdentity={identityRequired} onChange={set}/>
      </>:kind==="sites"?<>
        {textInput("name")}
        <div style={{gridColumn:"1 / -1"}}><CountryCityFields value={{country:String(draft.country??""),city:String(draft.city??""),city_other:String(draft.city_other??"")}} onChange={patch=>setDraft(old=>({...old,...patch}))}/></div>
        {textInput("address")}{textInput("location_url")}
        {contactPath&&<DirectorySelect path={contactPath} value={draft.contact_id as string} label={label("contact_id")} onChange={id=>set("contact_id",id||null)}/>}
      </>:fields[kind].map(field=>field==="vehicle_type"?<label key={field} className={s.field}>{label(field)}<ListSelect list="vehicle_type" value={String(draft[field]??"")} onChange={value=>set(field,value||null)} ariaLabel={label(field)}/></label>:textInput(field))}
      {kind==="vehicles"&&<DirectorySelect path="/shipping/directory/carriers/options" value={draft.carrier_id as string} label={label("carrier_id")} onChange={id=>set("carrier_id",id||null)}/>}
      <label><input type="checkbox" checked={!!draft.active} onChange={event=>{set("active",event.target.checked);if(!event.target.checked)set("is_default",false);}}/>{t("active")}</label>
      {["contacts","sites"].includes(kind)&&<label><input type="checkbox" checked={!!draft.is_default} disabled={!draft.active} onChange={event=>set("is_default",event.target.checked)}/>{t("default")}</label>}
    </RecordDialog>}
  </section>;
}

export function CustomerDirectory({id,kind}:{id:string;kind?:"contacts"|"sites"}){
  const base=`/commercial/customers/${id}/directory`;
  return <>{(!kind||kind==="contacts")&&<DirectoryPanel path={`${base}/contacts`} kind="contacts" writePermission="commercial:customers:update"/>}
    {(!kind||kind==="sites")&&<DirectoryPanel path={`${base}/sites`} contactPath={`${base}/contacts`} kind="sites" writePermission="commercial:customers:update"/>}</>;
}
