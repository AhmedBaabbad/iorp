"use client";
import {useEffect,useState} from "react";
import {useLocale,useTranslations} from "next-intl";
import {Pagination} from "@/components/pagination/Pagination";
import {apiClient} from "@/lib/api-client";
import {formatSpecValue,isSpecRange} from "@/lib/spec-value";
import {useFormatter} from "@/hooks/useFormatter";
import {useProducts} from "@/features/masterdata";
import s from "@/features/production-demands/demands.module.css";

type Change={field:string;old:unknown;new:unknown};
type Entry={id:string;action:string;actor_name:string|null;created_at:string;details:{schema_version?:number;changes?:Change[];reason?:string;related?:Record<string,unknown>;from_status?:string;to_status?:string;old_start?:string;new_start?:string;old_end?:string;new_end?:string}|null};
type HistoryPage={items:Entry[];total:number;pages:number};

export function RecordHistory({entityType,entityId,revision=0}:{entityType:string;entityId:string;revision?:number}){
  const t=useTranslations("production.recordHistory"),all=useTranslations(),locale=useLocale(),fmt=useFormatter(),products=useProducts();
  const [page,setPage]=useState(1),[size,setSize]=useState(50),[data,setData]=useState<HistoryPage|null>(null),[error,setError]=useState(false);
  useEffect(()=>{setPage(1);},[entityType,entityId]);
  useEffect(()=>{let live=true;setError(false);setData(null);
    apiClient<HistoryPage>(`/record-history/${encodeURIComponent(entityType)}/${encodeURIComponent(entityId)}?page=${page}&page_size=${size}`,{notify:false})
      .then(next=>{if(!Array.isArray(next.items))throw new Error("Invalid history page");if(live)setData(next);}).catch(()=>{if(live)setError(true);});return()=>{live=false;};
  },[entityType,entityId,page,size,revision]);
  function property(field:string){const key=field.split(".").slice(1).join(".");return products?.flatMap(p=>p.properties??[]).find(p=>p.key===key);}
  function label(field:string){const prop=property(field),key=field.split(".").slice(1).join(".");return prop?(locale==="ar"?prop.name_ar:prop.name_en):t.has(`fields.${field}`)?t(`fields.${field}`):key&&all.has(`production.planning.specColumns.${key}`)?all(`production.planning.specColumns.${key}`):t("field");}
  function value(field:string,raw:unknown):string{
    if(raw==null||raw==="")return "—";
    if(field==="unit")return all.has(`common.units.units.${raw}`)?all(`common.units.units.${raw}`):formatSpecValue(raw);
    if(field==="allocation_status")return all.has(`production.allocation.statuses.${raw}`)?all(`production.allocation.statuses.${raw}`):formatSpecValue(raw);
    if(field==="priority")return all.has(`production.demands.priorities.${raw}`)?all(`production.demands.priorities.${raw}`):formatSpecValue(raw);
    if(field==="status"){
      const key=entityType==="production_demand"?`production.demands.statuses.${raw}`:`enums.productionOrder.status.${raw}`;
      return all.has(key)?all(key):formatSpecValue(raw);
    }
    const prop=property(field),option=prop?.options?.find(o=>o.value===raw);
    if(option)return locale==="ar"?option.label_ar:option.label_en;
    if(field==="lines"&&Array.isArray(raw))return raw.map(line=>Object.entries(line as Record<string,unknown>).map(([key,item])=>`${label(key)}: ${value(key,item)}`).join(" · ")).join("\n");
    return formatSpecValue(raw);
  }
  return <section className={s.panel} aria-label={t("title")}>
    <h2>{t("title")}</h2>{error?<p role="alert" className={s.error}>{t("loadFailed")}</p>:!data?<p role="status">{t("loading")}</p>:<>
      {!data.items.length&&<p>{t("empty")}</p>}
      <ol className={s.timeline}>{data.items.map(entry=>{
        const details=entry.details??{},changes=details.changes??(details.from_status?[{field:"status",old:details.from_status,new:details.to_status}]:details.old_start?[{field:"planned_start_date",old:details.old_start,new:details.new_start},{field:"planned_end_date",old:details.old_end,new:details.new_end}]:[]);
        const eventKey=entry.action.replaceAll(".","_");
        return <li key={entry.id}><strong>{t.has(`events.${eventKey}`)?t(`events.${eventKey}`):t("event")}</strong>
          <span>{entry.actor_name??t("system")} · {fmt.dateTime(entry.created_at)}</span>
          {details.related?.production_order_number!=null&&<span>{t("order")}: <bdi>{formatSpecValue(details.related.production_order_number)}</bdi></span>}
          {!!changes.length&&<div className={s.tableWrap}><table className={s.table}><thead><tr><th>{t("field")}</th><th>{t("old")}</th><th>{t("new")}</th></tr></thead><tbody>{changes.map((change,index)=><tr key={`${change.field}-${index}`}><th>{label(change.field)}</th><td style={{whiteSpace:"pre-wrap",overflowWrap:"anywhere"}}><bdi dir={isSpecRange(change.old)?"ltr":"auto"}>{value(change.field,change.old)}</bdi></td><td style={{whiteSpace:"pre-wrap",overflowWrap:"anywhere"}}><bdi dir={isSpecRange(change.new)?"ltr":"auto"}>{value(change.field,change.new)}</bdi></td></tr>)}</tbody></table></div>}
          {details.reason&&<p style={{whiteSpace:"pre-wrap"}}>{t("reason")}: {details.reason}</p>}
        </li>;
      })}</ol>
      <Pagination page={page} pageSize={size} total={data.total} pages={data.pages} onPage={setPage} onPageSize={next=>{setSize(next);setPage(1);}}/>
    </>}
  </section>;
}
