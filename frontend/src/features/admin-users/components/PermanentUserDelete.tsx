"use client";
import { useState, type CSSProperties, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { usePermission } from "@/features/auth";
import { useNotify } from "@/components/notify/Notifications";
import { apiErrorCode } from "@/lib/api-error-handler";
import { sharedStyles } from "@/styles/shared-styles";
import { permanentlyDeleteAdminUser } from "../api/admin-users-api";
import type { AdminUserListItem } from "../types";

export function PermanentUserDelete({user,onDeactivate,className,style}:{user:AdminUserListItem;onDeactivate?:()=>void;className?:string;style?:CSSProperties}) {
  const allowed=usePermission("foundation:users:delete"),t=useTranslations("administration.users.permanentDelete");
  const router=useRouter(),notify=useNotify();
  const [open,setOpen]=useState(false),[email,setEmail]=useState(""),[reason,setReason]=useState(""),[busy,setBusy]=useState(false),[error,setError]=useState("");
  if(!allowed||!user.can_delete_permanently)return null;
  async function submit(event:FormEvent){
    event.preventDefault();if(busy||email.trim()!==user.email||reason.trim().length<3)return;
    setBusy(true);setError("");
    try{await permanentlyDeleteAdminUser(user.id,reason.trim());notify.success(t("success"));router.push("/admin/users");router.refresh();}
    catch(e){setError(apiErrorCode(e)??"FAILED");}finally{setBusy(false);}
  }
  return <>
    <button type="button" className={className} style={style??sharedStyles.dangerButton} onClick={()=>{setOpen(true);setEmail("");setReason("");setError("");}}>{t("button")}</button>
    {open&&<div style={sharedStyles.modalOverlay} onKeyDown={e=>{if(e.key==="Escape"&&!busy)setOpen(false);}}>
      <form role="dialog" aria-modal="true" aria-labelledby={`delete-user-${user.id}`} style={{...sharedStyles.modal,width:"min(460px, 100%)",display:"grid",gap:18}} onSubmit={submit}>
        <h2 id={`delete-user-${user.id}`} style={{margin:0}}>{t("title")}</h2>
        <p style={{margin:0,color:"var(--danger)"}}>{t("warning")}</p>
        <label style={sharedStyles.field}><span style={sharedStyles.label}>{t("reason")}</span><textarea style={sharedStyles.textarea} value={reason} onChange={e=>setReason(e.target.value)} minLength={3} maxLength={500} required disabled={busy}/></label>
        <label style={sharedStyles.field}><span style={sharedStyles.label}>{t("confirmEmail",{email:user.email})}</span><input style={sharedStyles.input} type="email" autoComplete="off" value={email} onChange={e=>setEmail(e.target.value)} required disabled={busy}/></label>
        {error&&<div role="alert" style={sharedStyles.error}><p>{t.has(error)?t(error):t("FAILED")}</p>{error==="USER_DELETE_HAS_HISTORY"&&<p>{t("useDeactivation")}{onDeactivate&&<button type="button" style={sharedStyles.secondaryButton} onClick={()=>{setOpen(false);onDeactivate();}}>{t("deactivate")}</button>}</p>}</div>}
        <div style={{display:"flex",flexWrap:"wrap",gap:12}}><button type="submit" style={sharedStyles.dangerButton} disabled={busy||email.trim()!==user.email||reason.trim().length<3}>{t("button")}</button><button type="button" style={sharedStyles.secondaryButton} disabled={busy} onClick={()=>setOpen(false)}>{t("cancel")}</button></div>
      </form>
    </div>}
  </>;
}
