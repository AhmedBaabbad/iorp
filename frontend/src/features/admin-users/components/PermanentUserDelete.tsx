"use client";
import { useState, type CSSProperties, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { Dialog } from "@/components/ui/Dialog";
import { usePermission } from "@/features/auth";
import { useNotify } from "@/components/notify/Notifications";
import { apiErrorCode } from "@/lib/api-error-handler";
import { ApiClientError } from "@/lib/api-client";
import { sharedStyles } from "@/styles/shared-styles";
import { permanentlyDeleteAdminUser } from "../api/admin-users-api";
import type { AdminUserListItem, UserDeleteBlock } from "../types";

export function PermanentUserDelete({user,onDeleted,onDeactivate,className,style,showBlock=false}:{user:AdminUserListItem & {can_delete_permanently?:boolean;delete_block?:UserDeleteBlock|null};showBlock?:boolean;onDeleted?:()=>void;onDeactivate?:()=>void;className?:string;style?:CSSProperties}) {
  const allowed=usePermission("foundation:users:delete"),t=useTranslations("administration.users.permanentDelete");
  const router=useRouter(),notify=useNotify();
  const [open,setOpen]=useState(false),[name,setName]=useState(""),[reason,setReason]=useState(""),[busy,setBusy]=useState(false),[error,setError]=useState("");
  const [errorTables,setErrorTables]=useState<string[]>([]);
  const block=user.delete_block;
  if(!allowed || (showBlock?(block===undefined):!user.can_delete_permanently))return null;
  const nameMatches=Boolean(name.trim())&&name.trim()===user.full_name.trim();
  function finishDeletion(){
    setOpen(false);
    if(onDeleted)onDeleted();
    else{router.push("/admin/users");router.refresh();}
  }
  const blockers=(tables:string[])=><ul aria-label={t("blockers")} style={{paddingInlineStart:24,marginBlock:8}}>{tables.map(key=><li key={key}>{t.has(`tableTypes.${key}`)?t(`tableTypes.${key}`):t("linkedRecords")}</li>)}</ul>;
  const offboarding=()=>onDeactivate&&<button type="button" style={sharedStyles.secondaryButton} onClick={()=>{setOpen(false);onDeactivate();}}>{t("offboarding")}</button>;
  async function submit(event:FormEvent){
    event.preventDefault();if(block||busy||!nameMatches||reason.trim().length<3)return;
    setBusy(true);setError("");setErrorTables([]);
    try{await permanentlyDeleteAdminUser(user.id,reason.trim());notify.success(t("success"));finishDeletion();}
    catch(e){
      if(e instanceof ApiClientError&&e.status===404){notify.error(t("notFound"));finishDeletion();}
      else{
        setError(apiErrorCode(e)??"FAILED");
        const tables=(e as {details?:{details?:{tables?:unknown}}})?.details?.details?.tables;
        if(Array.isArray(tables))setErrorTables(tables.filter((value):value is string=>typeof value==="string"));
      }
    }finally{setBusy(false);}
  }
  return <>
    <button type="button" className={className} style={style??sharedStyles.dangerButton} disabled={showBlock&&!!block} onClick={()=>{setOpen(true);setName("");setReason("");setError("");setErrorTables([]);}}>{t("button")}</button>
    {showBlock&&block&&<div role="note" style={{color:"inherit",flexBasis:"100%",overflowWrap:"anywhere"}}>
      <p>{t.has(block.code)?t(block.code):t("FAILED")}</p>
      {block.tables.length>0&&blockers(block.tables)}
      {block.code==="USER_DELETE_HAS_HISTORY"&&<><p>{t("transferFirst")}</p>{offboarding()}</>}
    </div>}
    {open&&<Dialog title={t("title")} onClose={()=>setOpen(false)} onSubmit={submit} busy={busy}
      footer={<><button type="submit" style={sharedStyles.dangerButton} disabled={busy||!nameMatches||reason.trim().length<3}>{t("button")}</button>
        <button type="button" style={sharedStyles.secondaryButton} disabled={busy} onClick={()=>setOpen(false)}>{t("cancel")}</button></>}>
      <div style={{display:"grid",gap:18}}>
        <p style={{margin:0,color:"var(--danger)"}}>{t("warning")}</p>
        <label style={sharedStyles.field}><span style={sharedStyles.label}>{t("reason")}</span><textarea style={sharedStyles.textarea} value={reason} onChange={e=>setReason(e.target.value)} minLength={3} maxLength={500} required disabled={busy}/></label>
        <label style={sharedStyles.field}><span style={sharedStyles.label}>{t("confirmName",{name:user.full_name})}</span><input style={sharedStyles.input} autoComplete="off" value={name} onChange={e=>setName(e.target.value)} required disabled={busy}/></label>
        {error&&<div role="alert" style={sharedStyles.error}><p>{t.has(error)?t(error):t("FAILED")}</p>{errorTables.length>0&&blockers(errorTables)}
          {error==="USER_DELETE_HAS_HISTORY"&&<><p>{t("useDeactivation")}</p>{offboarding()}</>}
        </div>}
      </div>
    </Dialog>}
  </>;
}
