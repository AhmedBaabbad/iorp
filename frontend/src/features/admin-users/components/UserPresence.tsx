"use client";
import { useFormatter, useTranslations } from "next-intl";

export function UserPresence({user}:{user:{last_seen_at?:string|null;is_online?:boolean|null}}) {
  const t=useTranslations("administration.users.presence"),fmt=useFormatter();
  if(user.is_online)return <span style={{display:"inline-flex",alignItems:"center",gap:6}}><span aria-hidden="true" style={{width:8,height:8,borderRadius:"50%",background:"var(--success)",flexShrink:0}}/>{t("online")}</span>;
  return <span>{user.last_seen_at?t("lastSeen",{time:fmt.relativeTime(new Date(user.last_seen_at),new Date())}):t("never")}</span>;
}
