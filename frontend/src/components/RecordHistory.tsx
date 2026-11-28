"use client";
import {useEffect,useState} from "react";
import {useLocale,useTranslations} from "next-intl";
import {Pagination} from "@/components/pagination/Pagination";
import {apiClient} from "@/lib/api-client";
import {formatSpecValue,isSpecRange} from "@/lib/spec-value";
import {useFormatter} from "@/hooks/useFormatter";
import {useProducts} from "@/features/masterdata";
import s from "./RecordHistory.module.css";

type Change={field:string;old:unknown;new:unknown;line?:number;line_change?:"added"|"removed"|"changed"};
type Related=Record<string,unknown>&{subject_kind?:string;subject_name?:unknown;production_order_number?:unknown};
type Entry={id:string;action:string;actor_name:string|null;created_at:string;details:{schema_version?:number;changes?:Change[];reason?:string;related?:Related;from_status?:string;to_status?:string;old_start?:string;new_start?:string;old_end?:string;new_end?:string}|null};
type HistoryPage={items:Entry[];total:number;pages:number};

/** Enumerated values by the record (or the child record an entry is about) and field: shown in the reader's language. */
const ENUMS:Record<string,string>={
  "production_demand.status":"production.demands.statuses","production_order.status":"enums.productionOrder.status",
  "production_demand.priority":"production.demands.priorities","production_order.priority":"production.demands.priorities",
  "allocation_status":"production.allocation.statuses",
  "customer.status":"sharedEnums.commercial.customerStatus","customer.relationship_stage":"sharedEnums.commercial.customerRelationshipStage",
  "customer.priority_level":"sharedEnums.commercial.customerPriorityLevel",
  "interaction.interaction_type":"sharedEnums.commercial.interactionInteractionType","interaction.outcome":"sharedEnums.commercial.interactionOutcome",
  "follow_up.status":"sharedEnums.commercial.followUpStatus","follow_up.priority":"sharedEnums.commercial.followUpPriority",
  "quote.status":"sharedEnums.commercial.quoteStatus","sales_order.status":"sharedEnums.commercial.commercialOrderStatus",
  "sample.status":"sharedEnums.commercial.sampleStatus","sample.sample_decision":"sharedEnums.commercial.sampleDecision",
  "evaluation.status":"sharedEnums.commercial.sampleStatus","evaluation.result_status":"sharedEnums.commercial.sampleEvaluationResultStatus",
  "evaluation.next_action":"sharedEnums.commercial.sampleEvaluationNextAction",
};
const ISO_DATE=/^\d{4}-\d{2}-\d{2}(T[\d:.]+(Z|[+-]\d{2}:?\d{2})?)?$/;

/** The "السجل" tab of any record that registered its history (docs/architecture/record-history.md).
 *  namespace: where the module words its events, fields and child records (`<namespace>.events|fields|subjects`). */
export function RecordHistory({entityType,entityId,revision=0,namespace}:{entityType:string;entityId:string;revision?:number;namespace?:string}){
  const ns=namespace??(entityType.startsWith("production_")?"production.recordHistory":"commercial.recordHistory");
  const t=useTranslations("common.recordHistory"),words=useTranslations(ns),all=useTranslations(),locale=useLocale(),fmt=useFormatter(),products=useProducts();
  const [page,setPage]=useState(1),[size,setSize]=useState(50),[data,setData]=useState<HistoryPage|null>(null),[error,setError]=useState(false);
  useEffect(()=>{setPage(1);},[entityType,entityId]);
  useEffect(()=>{let live=true;setError(false);setData(null);
    apiClient<HistoryPage>(`/record-history/${encodeURIComponent(entityType)}/${encodeURIComponent(entityId)}?page=${page}&page_size=${size}`,{notify:false})
      .then(next=>{if(!Array.isArray(next.items))throw new Error("Invalid history page");if(live)setData(next);}).catch(()=>{if(live)setError(true);});return()=>{live=false;};
  },[entityType,entityId,page,size,revision]);
  const has=(key:string)=>all.has(key);
  function property(field:string){const key=field.split(".").slice(1).join(".");return key?products?.flatMap(p=>p.properties??[]).find(p=>p.key===key):undefined;}
  function label(field:string){
    const prop=property(field),key=field.split(".").slice(1).join(".");
    if(prop)return locale==="ar"?prop.name_ar:prop.name_en;
    if(words.has(`fields.${field}`))return words(`fields.${field}`);
    if(key&&has(`production.planning.specColumns.${key}`))return all(`production.planning.specColumns.${key}`);
    return key||(t.has(`fields.${field}`)?t(`fields.${field}`):t("field"));
  }
  function value(field:string,raw:unknown,kind:string):string{
    if(raw==null||raw==="")return "—";
    if(typeof raw==="boolean")return raw?t("yes"):t("no");
    if(field==="unit")return has(`common.units.units.${raw}`)?all(`common.units.units.${raw}`):formatSpecValue(raw);
    const group=ENUMS[`${kind}.${field}`]??ENUMS[field];
    if(group&&has(`${group}.${raw}`))return all(`${group}.${raw}`);
    const prop=property(field),option=prop?.options?.find(o=>o.value===raw);
    if(option)return locale==="ar"?option.label_ar:option.label_en;
    if(field==="lines"&&Array.isArray(raw))return raw.map(line=>Object.entries(line as Record<string,unknown>).map(([key,item])=>`${label(key)}: ${value(key,item,kind)}`).join(" · ")).join("\n");
    if(typeof raw==="string"&&ISO_DATE.test(raw))return raw.length>10?fmt.dateTime(raw):fmt.date(raw);
    return formatSpecValue(raw);
  }
  function fieldLabel(change:Change){
    if(change.line==null)return label(change.field);
    const line=t("line",{number:change.line}),state=change.line_change==="added"?` (${t("lineAdded")})`:change.line_change==="removed"?` (${t("lineRemoved")})`:"";
    return `${line}${state} · ${label(change.field)}`;
  }
  /** One line per entry: which fields changed (at most five named), the values stay behind "Details". */
  function summary(changes:Change[]){
    const names=[...new Set(changes.map(fieldLabel))],comma=locale==="ar"?"، ":", ";
    return names.length>5?`${names.slice(0,5).join(comma)} ${t("moreFields",{count:names.length-5})}`:names.join(comma);
  }
  return <section className={s.panel} aria-label={t("title")}>
    <h2>{t("title")}</h2>{error?<p role="alert" className={s.error}>{t("loadFailed")}</p>:!data?<p role="status">{t("loading")}</p>:<>
      {!data.items.length&&<p>{t("empty")}</p>}
      <ol className={s.timeline}>{data.items.map(entry=>{
        const details=entry.details??{},related=details.related??{},kind=related.subject_kind??entityType;
        const changes=details.changes??(details.from_status?[{field:"status",old:details.from_status,new:details.to_status}]:details.old_start?[{field:"planned_start_date",old:details.old_start,new:details.new_start},{field:"planned_end_date",old:details.old_end,new:details.new_end}]:[]);
        const eventKey=entry.action.replaceAll(".","_");
        const subject=related.subject_kind&&related.subject_name!=null?`${words.has(`subjects.${related.subject_kind}`)?words(`subjects.${related.subject_kind}`):t("subject")}: ${value("subject_name",related.subject_name,kind)}`:null;
        return <li key={entry.id}><strong>{words.has(`events.${eventKey}`)?words(`events.${eventKey}`):t("event")}</strong>
          <span className={s.muted}>{entry.actor_name??t("system")} · {fmt.dateTime(entry.created_at)}</span>
          {subject&&<span><bdi>{subject}</bdi></span>}
          {related.production_order_number!=null&&<span>{words.has("order")?words("order"):t("order")}: <bdi>{formatSpecValue(related.production_order_number)}</bdi></span>}
          {!!changes.length&&<p className={s.summary}>{t("changedFields",{fields:summary(changes)})}</p>}
          {!!changes.length&&<details className={s.details}><summary>{t("showDetails")}</summary><div className={s.tableWrap}><table className={s.table}><thead><tr><th>{t("field")}</th><th>{t("old")}</th><th>{t("new")}</th></tr></thead><tbody>{changes.map((change,index)=><tr key={`${change.field}-${change.line??""}-${index}`}><th>{fieldLabel(change)}</th><td className={s.value}><bdi dir={isSpecRange(change.old)?"ltr":"auto"}>{value(change.field,change.old,kind)}</bdi></td><td className={s.value}><bdi dir={isSpecRange(change.new)?"ltr":"auto"}>{value(change.field,change.new,kind)}</bdi></td></tr>)}</tbody></table></div></details>}
          {details.reason&&<p className={s.reason}>{t("reason")}: {details.reason}</p>}
        </li>;
      })}</ol>
      <Pagination page={page} pageSize={size} total={data.total} pages={data.pages} onPage={setPage} onPageSize={next=>{setSize(next);setPage(1);}}/>
    </>}
  </section>;
}
