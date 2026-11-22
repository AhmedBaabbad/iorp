"use client";
import Link from "next/link";
import type {ReactNode} from "react";
import {useTranslations} from "next-intl";
import {PageFrame} from "@/components/layout/page-frame";
import {RecordDialog} from "@/components/ui/RecordDialog";
import s from "@/features/production-demands/demands.module.css";

/** Shared field content and validation for a standalone editor and its contextual dialog. */
export function EditorSurface({title,subtitle,back,backLabel,cancelLabel,saveLabel,onClose,onSave,loading,busy,disabled,error,children}:{
  title:string;subtitle?:string;back:string;backLabel:string;cancelLabel:string;saveLabel:string;onClose?:()=>void;
  onSave:()=>Promise<boolean>;loading:boolean;busy:boolean;disabled:boolean;error:string;children:ReactNode;
}){
  const messages=useTranslations("messages");
  const content=loading?<p>{messages("loading.default")}</p>:children;
  if(onClose)return <RecordDialog title={title} onClose={onClose} onSave={onSave} error={error} disabled={disabled||loading} saveLabel={saveLabel}>
    <div style={{gridColumn:"1 / -1",minWidth:0}}>{content}</div>
  </RecordDialog>;
  return <PageFrame title={title} subtitle={subtitle} action={<Link href={back} className={s.button}>{backLabel}</Link>}>
    {loading?content:<form className={s.panel} aria-label={title} onSubmit={async event=>{event.preventDefault();await onSave();}}>
      {content}{error&&<p role="alert" className={s.error}>{error}</p>}
      <div className={s.actions} style={{marginTop:16}}><button type="submit" className={`${s.button} ${s.primary}`} disabled={disabled||busy}>{saveLabel}</button>
        <Link href={back} className={s.button}>{cancelLabel}</Link></div>
    </form>}
  </PageFrame>;
}
