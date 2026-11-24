"use client";
import {useId,useRef,useState} from "react";
import {useTranslations} from "next-intl";
import {RecordDialog} from "@/components/ui/RecordDialog";
import {usePermission} from "@/features/auth/permission-hooks";
import {apiErrorCode} from "@/lib/api-error-handler";
import {P} from "@/lib/production-permissions";
import {useFormatter} from "@/hooks/useFormatter";
import {rescheduleProductionOrder} from "../api/production-orders-api";
import type {ProductionOrderData} from "../types";
import s from "@/features/production-demands/demands.module.css";

export type SchedulingOrder={id:string;status:string;planned_start_date:string;planned_end_date:string;
  lifecycle?:{actual_start_at?:string|null;finish_overdue?:boolean}|null;finish_overdue?:boolean;actual_start_at?:string|null};
export const scheduleOpen=(order:SchedulingOrder)=>["draft","released","in_progress","on_hold"].includes(order.status);
export const scheduleStarted=(order:SchedulingOrder)=>Boolean(order.actual_start_at||order.lifecycle?.actual_start_at||!["draft","released"].includes(order.status));
export const scheduleOverdue=(order:SchedulingOrder)=>Boolean(order.lifecycle?.finish_overdue??order.finish_overdue);
export function dateDifference(from:string,to:string){const days=(Date.parse(`${to}T00:00:00Z`)-Date.parse(`${from}T00:00:00Z`))/86400000;return Number.isFinite(days)?days:null;}
type Translator=((key:string)=>string)&{has:(key:string)=>boolean};
class ScheduleInputError extends Error{constructor(public code:string){super(code);}}
export function schedulingError(error:unknown,t:Translator,fallback:()=>string){
  let code=error instanceof ScheduleInputError?error.code:apiErrorCode(error);
  const data=error as {status?:number;details?:{detail?:{loc?:unknown[]}[]}};
  if(!code&&data.status===403)code="FORBIDDEN";
  if(!code&&Array.isArray(data.details?.detail))code=data.details.detail.some(row=>row.loc?.includes("reason"))?"RESCHEDULE_REASON_INVALID":"INVALID_PLANNED_DATES";
  return code&&t.has(`errors.${code}`)?t(`errors.${code}`):fallback();
}

export function DateChangePreview({oldStart,newStart,oldEnd,newEnd}:{oldStart?:string;newStart?:string;oldEnd:string;newEnd:string}){
  const t=useTranslations("production.productionOrders.reschedule");
  const fmt=useFormatter();
  const days=dateDifference(oldEnd,newEnd);
  const range=(from:string,to:string)=>t.rich("fromTo",{from:fmt.date(from),to:to?fmt.date(to):"—",date:chunks=><bdi dir="ltr" style={{whiteSpace:"nowrap"}}>{chunks}</bdi>});
  return <div style={{gridColumn:"1 / -1"}} aria-live="polite">
    {oldStart&&newStart&&<p>{t("start")}: {range(oldStart,newStart)}</p>}
    <p>{t("end")}: {range(oldEnd,newEnd)}</p>
    {days!==null&&<p>{t("daysChange",{days})}</p>}
  </div>;
}

export function RescheduleOrderButton({order,onChanged,extend=false,ariaLabel}:{order:ProductionOrderData;onChanged?:()=>void;extend?:boolean;ariaLabel?:string}){
  const t=useTranslations("production.productionOrders.reschedule"),allowed=usePermission(P.ORDERS_UPDATE);
  const [open,setOpen]=useState(false);
  if(!allowed||!scheduleOpen(order))return null;
  return <><button type="button" className={s.button} style={{minBlockSize:"var(--control-height)"}} aria-label={ariaLabel} onClick={()=>setOpen(true)}>{t(extend?"extend":"edit")}</button>
    {open&&<OrderRescheduleDialog order={order} onClose={()=>setOpen(false)} onChanged={onChanged}/>}</>;
}

export function OrderRescheduleDialog({order,onClose,onChanged}:{order:ProductionOrderData;onClose:()=>void;onChanged?:()=>void}){
  const t=useTranslations("production.productionOrders.reschedule");
  const hint=useId();
  const [start,setStart]=useState(order.planned_start_date),[end,setEnd]=useState(order.planned_end_date),[reason,setReason]=useState("");
  const [error,setError]=useState("");
  const started=scheduleStarted(order),changed=start!==order.planned_start_date||end!==order.planned_end_date;
  return <RecordDialog title={t("title")} onClose={onClose} error={error} disabled={!changed||!start||!end||end<start||reason.trim().length<3}
    onSave={async()=>{setError("");try{await rescheduleProductionOrder(order.id,{...(!started?{planned_start_date:start}:{}),planned_end_date:end,reason:reason.trim()});onChanged?.();return true;}
      catch(e){setError(schedulingError(e,t,()=>t("errors.request_failed")));return false;}}}>
    <label className={s.field}>{t("start")}<input aria-label={t("start")} aria-describedby={started?`${hint}-start`:undefined} type="date" value={start} disabled={started} required onChange={event=>setStart(event.target.value)}/>{started&&<small id={`${hint}-start`}>{t("startLocked")}</small>}</label>
    <label className={s.field}>{t("end")}<input type="date" min={start} value={end} required onChange={event=>setEnd(event.target.value)}/></label>
    <label className={s.field} style={{gridColumn:"1 / -1"}}>{t("reason")}<textarea aria-label={t("reason")} aria-describedby={`${hint}-reason`} required minLength={3} maxLength={500} value={reason} onChange={event=>setReason(event.target.value)}/><small id={`${hint}-reason`}>{t("reasonHint")}</small></label>
    <DateChangePreview oldStart={order.planned_start_date} newStart={start} oldEnd={order.planned_end_date} newEnd={end}/>
  </RecordDialog>;
}

/** Keep the successful reschedule if allocation fails; retrying must not send it twice. */
export function useOrderExtension(order:SchedulingOrder,onRescheduled?:(saved:ProductionOrderData)=>void){
  const [enabled,setEnabled]=useState(false),[end,setEnd]=useState(""),[reason,setReason]=useState("");
  const applied=useRef("");
  async function beforeAttach(){
    if(!enabled)return;
    const key=JSON.stringify([order.id,end,reason.trim()]);
    if(applied.current===key)return;
    if(reason.trim().length<3||reason.trim().length>500)throw new ScheduleInputError("RESCHEDULE_REASON_INVALID");
    if(!end||end<order.planned_start_date||(dateDifference(order.planned_end_date,end)??0)<=0)throw new ScheduleInputError("INVALID_EXTENSION_DATE");
    const saved=await rescheduleProductionOrder(order.id,{planned_end_date:end,reason:reason.trim()});
    applied.current=key;onRescheduled?.(saved);
  }
  return {enabled,setEnabled,end,setEnd,reason,setReason,beforeAttach};
}

export function ExtendEndFields({order,extension}:{order:SchedulingOrder;extension:ReturnType<typeof useOrderExtension>}){
  const t=useTranslations("production.productionOrders.reschedule");
  return <fieldset className={s.panel} style={{minWidth:0,gridColumn:"1 / -1"}}>
    <label className={s.actions} style={{minBlockSize:"var(--control-height)"}}><input type="checkbox" checked={extension.enabled} onChange={event=>extension.setEnabled(event.target.checked)}/> {t("extendEnd")}</label>
    {extension.enabled&&<div className={s.grid}>
      <label className={s.field}>{t("end")}<input required type="date" value={extension.end} onChange={event=>extension.setEnd(event.target.value)}/></label>
      <label className={s.field}>{t("reason")}<textarea required minLength={3} maxLength={500} value={extension.reason} onChange={event=>extension.setReason(event.target.value)}/></label>
      <DateChangePreview oldEnd={order.planned_end_date} newEnd={extension.end}/>
    </div>}
  </fieldset>;
}
