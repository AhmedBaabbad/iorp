"use client";

import Link from "next/link";
import {useCallback,useEffect,useState,type FormEvent} from "react";
import {useTranslations} from "next-intl";
import {usePermission} from "@/features/auth";
import {useFormatter} from "@/hooks/useFormatter";
import {sharedStyles as s} from "@/styles/shared-styles";
import {getApiErrorMessage} from "@/lib/api-error-handler";
import {getEligibleSalesOwners,reassignCustomersByOwner} from "@/features/customers/customer-api";
import {getEligibleAssignees,reassignFollowUpsByUser} from "@/features/followups/followup-api";
import {archiveAdminUser,deactivateAdminUser,getUserDeactivationImpact} from "../api/admin-users-api";
import type {AdminUserDetail,UserDeactivationImpact} from "../types";
import css from "./admin-user-detail.module.css";

type Option={id:string;full_name:string;email:string};
export function UserOffboarding({user,onChanged,onReload,allowOffboarding=true}:{user:AdminUserDetail;onChanged:(user:AdminUserDetail)=>void;onReload:()=>void;allowOffboarding?:boolean}){
  const t=useTranslations("administration.users.offboarding"),messages=useTranslations("messages"),fmt=useFormatter();
  const assignCustomers=usePermission("commercial:customers:assign_owner"),readCustomers=usePermission("commercial:customers:read");
  const assignFollowUps=usePermission("commercial:follow_ups:assign"),readFollowUps=usePermission("commercial:follow_ups:read");
  const canRestore=usePermission("foundation:users:activate");
  const deactivatePermission=usePermission("foundation:users:deactivate"),canOffboard=allowOffboarding&&deactivatePermission;
  const canCustomers=assignCustomers&&readCustomers,canFollowUps=assignFollowUps&&readFollowUps;
  const [impact,setImpact]=useState<UserDeactivationImpact|null>(null),[error,setError]=useState<string|null>(null);
  const [owners,setOwners]=useState<Option[]>([]),[assignees,setAssignees]=useState<Option[]>([]);
  const [owner,setOwner]=useState(""),[assignee,setAssignee]=useState(""),[busy,setBusy]=useState(false);
  const [action,setAction]=useState<"deactivate"|"archive"|"restore"|null>(null),[reason,setReason]=useState("");
  const refresh=useCallback(async()=>{
    setImpact(await getUserDeactivationImpact(user.id));
  },[user.id]);
  useEffect(()=>{if(!canOffboard)return;let live=true;getUserDeactivationImpact(user.id).then(value=>{if(live)setImpact(value);}).catch(e=>{if(live)setError(getApiErrorMessage(e,messages));});return()=>{live=false;};},[user.id,user.status,user.archived_at,messages,canOffboard]);
  useEffect(()=>{let live=true;
    if(!canOffboard)return;
    if(canCustomers)void getEligibleSalesOwners().then(rows=>{if(live)setOwners(rows.filter(row=>row.id!==user.id));}).catch(e=>{if(live)setError(getApiErrorMessage(e,messages));});
    if(canFollowUps)void getEligibleAssignees().then(rows=>{if(live)setAssignees(rows.filter(row=>row.id!==user.id));}).catch(e=>{if(live)setError(getApiErrorMessage(e,messages));});
    return()=>{live=false;};
  },[user.id,canCustomers,canFollowUps,messages,canOffboard]);
  const clear=impact?.total_blocking_items===0,inactive=user.status==="inactive",archived=!!user.archived_at;
  async function transfer(kind:"customers"|"followUps"){
    if(busy||archived||(kind==="customers"?(!canCustomers||!owner):(!canFollowUps||!assignee)))return;
    setBusy(true);setError(null);
    try{if(kind==="customers"){await reassignCustomersByOwner(user.id,owner);setOwner("");}else{await reassignFollowUpsByUser(user.id,assignee);setAssignee("");}await refresh();onReload();}
    catch(e){setError(getApiErrorMessage(e,messages));}finally{setBusy(false);}
  }
  async function submit(e:FormEvent){
    e.preventDefault();if(!action||busy||reason.trim().length<3)return;
    if(action!=="restore"&&!canOffboard)return;
    if(action==="deactivate"&&(!clear||inactive||archived))return;
    if(action==="archive"&&(!clear||!inactive||archived))return;
    if(action==="restore"&&(!archived||!canRestore))return;
    setBusy(true);setError(null);
    try{const next=action==="deactivate"?await deactivateAdminUser(user.id,reason.trim()):await archiveAdminUser(user.id,reason.trim(),action==="restore");setAction(null);setReason("");onChanged(next);}
    catch(caught){setError(getApiErrorMessage(caught,messages));}finally{setBusy(false);}
  }
  function start(next:typeof action){setReason("");setAction(next);}
  function state(done:boolean,available:boolean){return t(done?"completed":available?"current":"locked");}
  function transferControls(kind:"customers"|"followUps",allowed:boolean,options:Option[],value:string,set:(value:string)=>void){return allowed?<div style={{display:"grid",gap:"var(--form-gap, 18px)",gridTemplateColumns:"repeat(auto-fit, minmax(min(220px, 100%), 1fr))"}}>
    <label style={s.field}><span style={s.label}>{t("toUser")}</span><select style={s.input} value={value} disabled={busy||archived} onChange={e=>set(e.target.value)}><option value="">{t("chooseUser")}</option>{options.map(option=><option key={option.id} value={option.id}>{option.full_name} ({option.email})</option>)}</select></label>
    <button type="button" style={s.secondaryButton} disabled={!value||busy||archived} onClick={()=>void transfer(kind)}>{t("transfer")}</button>
    {!options.length&&<p>{t("noCandidates")}</p>}
  </div>:<p role="note">{t("noTransferPermission")}</p>;}
  return <section id="user-offboarding" className={css.card} aria-labelledby="offboarding-title">
    <header className={css.cardHeader}><h2 id="offboarding-title" className={css.cardTitle}>{t(canOffboard?"title":"archiveDetails")}</h2></header>
    {error&&!action&&<p role="alert" style={s.error}>{error}</p>}
    {canOffboard&&!impact&&<p role="status">{t("loading")}</p>}
    {archived&&<div role="status"><p>{t("archivedSummary",{date:fmt.dateTime(user.archived_at!),name:user.archived_by_name??t("unknown"),reason:user.archived_reason??t("unknown")})}</p>{canRestore&&<button type="button" style={s.secondaryButton} disabled={busy} onClick={()=>start("restore")}>{t("restore")}</button>}</div>}
    {canOffboard&&<ol role="list" style={{display:"grid",gap:"var(--form-gap, 18px)",paddingInlineStart:0,listStyle:"none"}}>
      <li aria-current={!clear&&!archived?"step":undefined}><h3>{t("step1")} — {clear||archived?"✓ ":""}{state(clear||archived,true)}</h3>
        {impact&&<><p>{t("customers",{count:impact.dependencies.assigned_customers})}</p>{impact.dependencies.assigned_customers>0&&!archived&&transferControls("customers",canCustomers,owners,owner,setOwner)}
          <p>{t("followUps",{count:impact.dependencies.open_follow_ups})}</p>{impact.dependencies.open_follow_ups>0&&!archived&&transferControls("followUps",canFollowUps,assignees,assignee,setAssignee)}
          {impact.dependencies.active_workforce_link&&<p>{t("workforceHint")} {impact.workforce_member_id?<Link href={`/workforce/${impact.workforce_member_id}`}>{t("workforceRecord")}</Link>:<Link href="/workforce">{t("workforceRecord")}</Link>}</p>}
          <button type="button" style={s.secondaryButton} disabled={busy} onClick={()=>void refresh().catch(e=>setError(getApiErrorMessage(e,messages)))}>{t("refreshImpact")}</button></>}
      </li>
      <li aria-current={clear&&!inactive&&!archived?"step":undefined}><h3>{t("step2")} — {inactive?"✓ ":""}{state(inactive,clear&&!archived)}</h3><p>{t("deactivateHint")}</p><button type="button" style={s.dangerButton} disabled={!clear||inactive||archived||busy} onClick={()=>start("deactivate")}>{t("deactivate")}</button></li>
      <li aria-current={clear&&inactive&&!archived?"step":undefined}><h3>{t("step3")} — {archived?"✓ ":""}{state(archived,clear&&inactive)}</h3><button type="button" style={s.secondaryButton} disabled={!clear||!inactive||archived||busy} onClick={()=>start("archive")}>{t("archive")}</button></li>
    </ol>}
    {action&&<div style={s.modalOverlay}><form role="dialog" aria-modal="true" aria-labelledby="offboarding-action" style={s.modal} onSubmit={submit}>
      <h2 id="offboarding-action">{t(action)}</h2><p>{t("confirmAction")}</p>
      {error&&<p role="alert" style={s.error}>{error}</p>}
      <label style={s.field}><span style={s.label}>{t("reason")}</span><textarea style={s.textarea} minLength={3} maxLength={500} required value={reason} disabled={busy} onChange={e=>setReason(e.target.value)}/></label>
      <div style={s.modalActions}><button type="submit" style={s.button} disabled={busy||reason.trim().length<3}>{t("confirm")}</button><button type="button" style={s.secondaryButton} disabled={busy} onClick={()=>setAction(null)}>{t("cancel")}</button></div>
    </form></div>}
  </section>;
}
