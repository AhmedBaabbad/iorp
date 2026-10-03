"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState, type ReactNode } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import s from "@/features/production-demands/demands.module.css";
import { useFormatter } from "@/hooks/useFormatter";
import { closeDowntimeEvent, deleteDowntimeEvent, getDowntimeEventById } from "../api";
import { fromLocalInput, nowLocalInput } from "../downtime-rules";
import type { DowntimeEvent } from "../types";
import { DowntimeCategoryBadge, DowntimeStatusBadge, DowntimeTypeBadge } from "./DowntimeBadges";
import { downtimeErrorMessage } from "./downtime-errors";

function Item({ label, children }: { label: string; children: ReactNode }) {
  return <div><dt className={s.muted}>{label}</dt><dd style={{ margin: "4px 0 0", overflowWrap: "anywhere" }}>{children}</dd></div>;
}

export function DowntimeEventDetail({ eventId }: { eventId: string }) {
  const t = useTranslations("production.downtimeEvents");
  const orderStatus = useTranslations("enums.productionOrder.status");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const router = useRouter();
  const [event, setEvent] = useState<DowntimeEvent | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dialog, setDialog] = useState<"close" | "delete" | null>(null);
  const [end, setEnd] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try { setEvent(await getDowntimeEventById(eventId)); } catch (e) { setError(downtimeErrorMessage(e, t)); } finally { setLoading(false); }
  }, [eventId, t]);
  useEffect(() => { void load(); }, [load]);

  async function run(action: () => Promise<unknown>, after?: () => void) {
    setBusy(true); setError("");
    try { await action(); setDialog(null); if (after) after(); else await load(); }
    catch (e) { setError(downtimeErrorMessage(e, t)); }
    finally { setBusy(false); }
  }

  const back = <Link href="/downtime-events" className={s.button}>{t("actions.backToList")}</Link>;
  if (loading) return <PageFrame title={t("detailTitle")} action={back}><p className={s.muted}>{messages("loading.default")}</p></PageFrame>;
  if (!event) return <PageFrame title={t("detailTitle")} action={back}><p role="alert" className={s.error}>{error || t("notFound")}</p></PageFrame>;
  const labels = event.labels;
  const actions = labels?.actions ?? [];
  const minutes = (value: string | null | undefined) => (value ? fmt.duration(Math.round(Number(value))) : "—");

  return <PageFrame title={t("detailTitle")} subtitle={labels?.work_center_name ?? undefined} action={back}>
    {labels?.order_status === "closed" && <p role="status" className={s.muted}>{t("hints.locked")}</p>}
    {error && !dialog && <p role="alert" className={s.error}>{error}</p>}
    <section className={s.panel}>
      <div className={s.actions} style={{ justifyContent: "space-between", marginBottom: 16 }}>
        <span className={s.actions}><DowntimeStatusBadge status={event.status} /><DowntimeCategoryBadge category={event.category} /><DowntimeTypeBadge planned={event.planned} /></span>
        {actions.length > 0 && <span className={s.actions}>
          {actions.includes("close") && <button type="button" className={`${s.button} ${s.primary}`} disabled={busy} onClick={() => { setEnd(nowLocalInput()); setDialog("close"); }}>{t("actions.close")}</button>}
          {actions.includes("edit") && <Link href={`/downtime-events/${event.id}/edit`} className={s.button}>{t("actions.edit")}</Link>}
          {actions.includes("delete") && <button type="button" className={`${s.button} ${s.danger}`} disabled={busy} onClick={() => setDialog("delete")}>{t("actions.delete")}</button>}
        </span>}
      </div>
      <dl className={s.grid} style={{ margin: 0 }}>
        <Item label={t("fields.workCenter")}>{labels?.work_center_name ?? "—"}</Item>
        <Item label={t("fields.startTime")}>{fmt.dateTime(event.start_time)}</Item>
        <Item label={t("fields.endTime")}>{event.end_time ? fmt.dateTime(event.end_time) : t("ongoing")}</Item>
        <Item label={t("fields.duration")}>{event.status === "open" ? t("elapsed", { minutes: minutes(labels?.elapsed_minutes) }) : minutes(event.duration_minutes)}</Item>
        <Item label={t("fields.productionOrder")}>{event.production_order_id ? <Link href={`/production-orders/${event.production_order_id}`}>{labels?.order_number ?? "—"}</Link> : t("placeholders.noOrder")}</Item>
        <Item label={t("fields.orderStatus")}>{labels?.order_status ? orderStatus(labels.order_status) : "—"}</Item>
        <Item label={t("fields.run")}>{labels?.run_date ? fmt.date(labels.run_date) : "—"}</Item>
        <Item label={t("fields.reasonCode")}>{event.reason_code ?? "—"}</Item>
        <Item label={t("fields.recordedBy")}>{labels?.created_by_name ?? "—"}</Item>
        <Item label={t("fields.closedBy")}>{labels?.closed_by_name ?? "—"}</Item>
      </dl>
      {event.notes && <p style={{ marginBottom: 0, whiteSpace: "pre-wrap" }}><span className={s.muted}>{t("fields.notes")}: </span>{event.notes}</p>}
    </section>
    {dialog && <div className={s.overlay} onKeyDown={e => { if (e.key === "Escape" && !busy) setDialog(null); }}>
      <div role="dialog" aria-modal="true" aria-label={t(`${dialog}Dialog.title`)} className={`${s.panel} ${s.dialog}`}>
        <h2>{t(`${dialog}Dialog.title`)}</h2>
        <p className={s.muted}>{t(`${dialog}Dialog.text`)}</p>
        {dialog === "close" && <label className={s.field}>{t("fields.endTime")}
          <input type="datetime-local" value={end} disabled={busy} onChange={e => setEnd(e.target.value)} />
        </label>}
        {error && <p role="alert" className={s.error}>{error}</p>}
        <div className={s.actions}>
          <button type="button" className={s.button} disabled={busy} onClick={() => setDialog(null)} autoFocus>{t("actions.cancel")}</button>
          {dialog === "close"
            ? <button type="button" className={`${s.button} ${s.primary}`} disabled={busy || !end} onClick={() => run(() => closeDowntimeEvent(event.id, fromLocalInput(end)))}>{t("actions.close")}</button>
            : <button type="button" className={`${s.button} ${s.danger}`} disabled={busy} onClick={() => run(() => deleteDowntimeEvent(event.id), () => router.push("/downtime-events"))}>{t("actions.delete")}</button>}
        </div>
      </div>
    </div>}
  </PageFrame>;
}
