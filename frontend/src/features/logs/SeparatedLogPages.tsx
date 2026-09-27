"use client";
import {useCallback,useEffect,useState} from "react";
import {useLocale,useTranslations} from "next-intl";
import {API_BASE_URL} from "@/lib/api-client";
import {getStoredAccessToken} from "@/lib/auth";
import {getStoredPlatformToken} from "@/lib/platform-auth";
import {useAuth} from "@/features/auth";
import {useOptionalPlatformAuth} from "@/features/platform/platform-auth-context";
import {PageFrame} from "@/components/layout/page-frame";
import css from "@/features/platform/platform-audit.module.css";

type Entry={id:string;event_type?:string;action?:string;actor_email?:string;actor_name?:string;entity_type?:string;entity_name?:string;ip_address?:string;details?:unknown;created_at:string};
type Result={items:Entry[];total:number;page:number;pages:number};
type Props={scope:"platform"|"tenant";kind:"security"|"activity";namespace:"platformSecurity"|"platformActivity"|"tenantSecurity"|"tenantActivity";permission:string};

export function SeparatedLogPage(props:Props){
 const t=useTranslations(props.namespace);const locale=useLocale();const tenant=useAuth();const platform=useOptionalPlatformAuth();
 const token=props.scope==="platform"?(platform?.token??getStoredPlatformToken()):(tenant.token??getStoredAccessToken());
 const allowed=props.scope==="platform"?!!platform?.account?.permissions?.includes(props.permission):tenant.hasPermission(props.permission);
 const [data,setData]=useState<Result>({items:[],total:0,page:1,pages:0});const [page,setPage]=useState(1);const [type,setType]=useState("");const [from,setFrom]=useState("");const [to,setTo]=useState("");const [loading,setLoading]=useState(true);const [error,setError]=useState(false);const [open,setOpen]=useState<string|null>(null);
 const load=useCallback(async()=>{if(!allowed)return;setLoading(true);setError(false);const q=new URLSearchParams({page:String(page),page_size:"25"});if(type)q.set(props.kind==="security"?"event_type":"action",type);if(from)q.set("date_from",`${from}T00:00:00Z`);if(to)q.set("date_to",`${to}T23:59:59Z`);try{const prefix=props.scope==="platform"?"platform":"admin";const r=await fetch(`${API_BASE_URL}/api/v1/${prefix}/${props.kind}-log?${q}`,{headers:{Authorization:`Bearer ${token??""}`}});if(!r.ok)throw new Error();setData(await r.json())}catch{setError(true)}finally{setLoading(false)}},[allowed,from,page,props.kind,props.scope,to,token,type]);useEffect(()=>{void load()},[load]);
 const body=<><form className={`${css.panel} ${css.filters}`} onSubmit={e=>{e.preventDefault();setPage(1);void load()}}><input className={css.input} value={type} onChange={e=>setType(e.target.value)} placeholder={t("filters.searchPlaceholder")}/><input aria-label={t("filters.dateFrom")} className={css.input} type="date" value={from} onChange={e=>setFrom(e.target.value)}/><input aria-label={t("filters.dateTo")} className={css.input} type="date" value={to} onChange={e=>setTo(e.target.value)}/><button className={css.button}>{t("filters.apply")}</button></form><section className={css.panel}>{loading?<div className={css.empty}>{t("loading")}</div>:error?<div className={css.error}>{t("error")}</div>:!data.items.length?<div className={css.empty}>{t("empty")}</div>:data.items.map(item=>{const key=item.event_type??item.action??"";return <article key={item.id} className={css.field}><button className={css.back} onClick={()=>setOpen(open===item.id?null:item.id)}><strong>{t.has(`${props.kind==="security"?"events":"actions"}.${key}`)?t(`${props.kind==="security"?"events":"actions"}.${key}`):key}</strong> · {new Intl.DateTimeFormat(locale,{dateStyle:"medium",timeStyle:"short"}).format(new Date(item.created_at))}</button><p>{item.actor_name??item.actor_email??t("system")}{item.entity_name?` · ${item.entity_name}`:""}{item.ip_address?` · ${item.ip_address}`:""}</p>{open===item.id&&<pre className={css.code}>{item.details?JSON.stringify(item.details,null,2):t("noDetails")}</pre>}</article>})}<div className={css.pagination}><button className={`${css.button} ${css.secondary}`} disabled={page<=1} onClick={()=>setPage(v=>v-1)}>{t("previous")}</button><span>{t("page",{page,pages:Math.max(1,data.pages)})}</span><button className={`${css.button} ${css.secondary}`} disabled={page>=data.pages} onClick={()=>setPage(v=>v+1)}>{t("next")}</button></div></section></>;
 if(props.scope==="tenant")return <PageFrame title={t("title")} subtitle={t("subtitle")}>{allowed?body:<div className={css.error}>{t("accessDenied")}</div>}</PageFrame>;
 return <main className={css.page} dir={locale==="ar"?"rtl":"ltr"}><div className={css.shell}><header className={css.header}><div><h1 className={css.title}>{t("title")}</h1><p className={css.subtitle}>{t("subtitle")}</p></div></header>{allowed?body:<div className={css.error}>{t("accessDenied")}</div>}</div></main>
}
