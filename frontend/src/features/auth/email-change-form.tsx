"use client";
import {useState} from "react";
import {useLocale,useTranslations} from "next-intl";
import {apiClient, ApiClientError} from "@/lib/api-client";
import {removeStoredAccessToken} from "@/lib/auth";
import css from "./my-profile-page.module.css";
export function EmailChangeForm(){
 const t=useTranslations("profile.emailChange"),locale=useLocale();
 const [email,setEmail]=useState(""),[password,setPassword]=useState(""),[oldCode,setOldCode]=useState(""),[newCode,setNewCode]=useState("");
 const [sent,setSent]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState<string | null>(null);
 async function submit(){setBusy(true);setError(null);try{
  await apiClient(sent?"/auth/me/email-change/confirm":"/auth/me/email-change",{method:"POST",headers:{"Accept-Language":locale},body:sent?{old_code:oldCode.trim(),new_code:newCode.trim()}:{email,current_password:password},notify:false});
  setPassword("");
  if(sent){removeStoredAccessToken();window.location.assign("/login");}else setSent(true);
 }catch(caught){
  let key = "error";
  if(caught instanceof ApiClientError){
    const details = caught.details as {code?: string} | null;
    if(details?.code && t.has(`errors.${details.code}`)) key = `errors.${details.code}`;
    else if(caught.status===429) key="errors.RATE_LIMIT_EXCEEDED";
    else if(caught.status===422) key="errors.INVALID_INPUT";
    else if(caught.status===404) key="errors.SERVICE_UNAVAILABLE";
    else if(caught.status>=500) key="errors.SERVER_ERROR";
  } else if(caught instanceof TypeError) key="errors.NETWORK_ERROR";
  setError(key);
 }finally{setBusy(false);}}
 return <section className={css.card}><h2>{t("title")}</h2><p>{t("hint")}</p><form className={css.form} onSubmit={e=>{e.preventDefault();void submit();}}><div className={css.formGrid}>
 {!sent?<><label>{t("email")}<input type="email" autoComplete="email" required value={email} onChange={e=>setEmail(e.target.value)}/></label><label>{t("password")}<input type="password" autoComplete="current-password" required value={password} onChange={e=>setPassword(e.target.value)}/></label></>:<><p role="status">{t("sent")}</p><label>{t("oldCode")}<input dir="ltr" required minLength={32} maxLength={32} value={oldCode} onChange={e=>setOldCode(e.target.value)}/></label><label>{t("newCode")}<input dir="ltr" required minLength={32} maxLength={32} value={newCode} onChange={e=>setNewCode(e.target.value)}/></label></>}
 </div>{error?<p role="alert">{t(error)}</p>:null}<div className={css.formFooter}><button disabled={busy}>{t(sent?"confirm":"request")}</button>{sent?<button type="button" disabled={busy} onClick={()=>{setSent(false);setOldCode("");setNewCode("");}}>{t("restart")}</button>:null}</div></form></section>;
}
