"use client";
import {usePagedFilters} from "@/lib/pagination";
import {Pagination,ListToolbar} from "@/components/pagination";

import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { API_BASE_URL } from "@/lib/api-client";
import { getStoredPlatformToken } from "@/lib/platform-auth";
import { listPlatformAuditLogs, PlatformAuditEvent } from "./platform-api";
import { usePlatformAuth } from "./platform-auth-context";
import { PlatformProtectedRoute } from "./platform-protected-route";
import css from "./platform-audit.module.css";

function Content() {
  const t = useTranslations("platformAudit"); const locale = useLocale(); const router = useRouter();
  const { account, token } = usePlatformAuth(); const [items,setItems]=useState<PlatformAuditEvent[]>([]);
  const [total,setTotal]=useState(0),[pages,setPages]=useState(0);
  const paging=usePagedFilters({search:"",category:"",outcome:"",severity:"",from:"",to:""});
  const {search,category,outcome,severity,from,to}=paging.filters,page=paging.page,pageSize=paging.pageSize;
  const setSearch=(value:string)=>paging.set("search",value),setCategory=(value:string)=>paging.set("category",value),setOutcome=(value:string)=>paging.set("outcome",value),setSeverity=(value:string)=>paging.set("severity",value),setFrom=(value:string)=>paging.set("from",value),setTo=(value:string)=>paging.set("to",value);
  const [loading,setLoading]=useState(true); const [error,setError]=useState(false);
  const canRead=account?.permissions?.includes("platform:audit:read"); const canExport=account?.permissions?.includes("platform:audit:export");
  const addFilters=useCallback((q:URLSearchParams)=>{if(search)q.set("search",search);if(category)q.set("category",category);if(outcome)q.set("outcome",outcome);if(severity)q.set("severity",severity);if(from)q.set("occurred_from",`${from}T00:00:00Z`);if(to)q.set("occurred_to",`${to}T23:59:59Z`)},[category,from,outcome,search,severity,to]);
  const load=useCallback(async()=>{if(!canRead)return;setLoading(true);setError(false);const q=new URLSearchParams({page:String(page),page_size:String(pageSize)});addFilters(q);try{const data=await listPlatformAuditLogs(q,token);setItems(data.items);setTotal(data.total);setPages(data.pages)}catch{setError(true)}finally{setLoading(false)}},[addFilters,canRead,page,pageSize,token]);
  useEffect(()=>{void load()},[load]);
  function submit(e:FormEvent){e.preventDefault();void load()}
  async function exportCsv(){const q=new URLSearchParams({locale});addFilters(q);const response=await fetch(`${API_BASE_URL.replace(/\/$/,"")}/api/v1/platform/audit-logs/export.csv?${q}`,{headers:{Authorization:`Bearer ${token??getStoredPlatformToken()??""}`},credentials:"include"});if(!response.ok){setError(true);return}const blob=await response.blob();const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download=`platform-audit-${new Date().toISOString().slice(0,10)}.csv`;a.click();URL.revokeObjectURL(url)}
  if(!canRead)return <main className={css.page} dir={locale==="ar"?"rtl":"ltr"}><div className={css.shell}><div className={`${css.panel} ${css.error}`}>{t("accessDenied")}</div></div></main>;
  return <main className={css.page} dir={locale==="ar"?"rtl":"ltr"}><div className={css.shell}>
    <header className={css.header}><div><p className={css.eyebrow}>{t("eyebrow")}</p><h1 className={css.title}>{t("title")}</h1><p className={css.subtitle}>{t("subtitle")}</p></div><Link className={css.back} href="/platform/dashboard">{t("back")}</Link></header>
    <ListToolbar search={search} onSearch={setSearch} searchHint={t("filters.search")} onClear={paging.clear} hasFilters={Object.values(paging.filters).some(Boolean)}/>
    <form className={`${css.panel} ${css.filters}`} onSubmit={submit}><select className={css.select} value={category} onChange={e=>setCategory(e.target.value)}><option value="">{t("filters.allCategories")}</option>{["identity","organization","authentication","authorization","security","configuration","audit"].map(v=><option key={v} value={v}>{t(`categories.${v}`)}</option>)}</select><select className={css.select} value={outcome} onChange={e=>setOutcome(e.target.value)}><option value="">{t("filters.allOutcomes")}</option>{["success","failure","denied"].map(v=><option key={v} value={v}>{t(`outcomes.${v}`)}</option>)}</select><select className={css.select} value={severity} onChange={e=>setSeverity(e.target.value)}><option value="">{t("filters.allSeverities")}</option>{["info","warning","critical"].map(v=><option key={v} value={v}>{t(`severities.${v}`)}</option>)}</select><input aria-label={t("filters.from")} title={t("filters.from")} className={css.input} type="date" value={from} onChange={e=>setFrom(e.target.value)}/><input aria-label={t("filters.to")} title={t("filters.to")} className={css.input} type="date" value={to} onChange={e=>setTo(e.target.value)}/><button className={css.button}>{t("filters.apply")}</button><button type="button" className={`${css.button} ${css.secondary}`} onClick={()=>{paging.clear()}}>{t("filters.clear")}</button></form>
    <section className={css.panel}><div className={css.actions}><strong>{t("count",{count:total})}</strong>{canExport&&<button type="button" className={`${css.button} ${css.secondary}`} onClick={()=>void exportCsv()}>{t("export")}</button>}</div>{loading?<div className={css.empty}>{t("loading")}</div>:error?<div className={css.error}>{t("loadError")} <button className={css.button} onClick={()=>void load()}>{t("retry")}</button></div>:items.length===0?<div className={css.empty}>{t("empty")}</div>:<div className={css.tableWrap}><table className={css.table}><thead><tr>{["time","event","actor","target","organization","outcome","severity"].map(h=><th key={h}>{t(`table.${h}`)}</th>)}</tr></thead><tbody>{items.map(item=><tr className={css.row} key={item.id} onClick={()=>router.push(`/platform/audit-logs/${item.id}`)}><td>{new Intl.DateTimeFormat(locale,{dateStyle:"medium",timeStyle:"short"}).format(new Date(item.occurred_at))}</td><td>{item.event_type}</td><td>{item.actor_email_snapshot??item.actor_name_snapshot??t(`actors.${item.actor_type}`)}</td><td>{item.target_display_snapshot??item.target_id??t("notAvailable")}</td><td>{item.organization_id??t("notAvailable")}</td><td><span className={`${css.badge} ${css[item.outcome]??""}`}>{t(`outcomes.${item.outcome}`)}</span></td><td><span className={`${css.badge} ${css[item.severity]??""}`}>{t(`severities.${item.severity}`)}</span></td></tr>)}</tbody></table></div>}<Pagination page={page} pageSize={pageSize} total={total} pages={pages} onPage={paging.setPage} onPageSize={paging.setPageSize} disabled={loading}/></section>
  </div></main>;
}
export function PlatformAuditPage(){return <PlatformProtectedRoute><Content/></PlatformProtectedRoute>}
