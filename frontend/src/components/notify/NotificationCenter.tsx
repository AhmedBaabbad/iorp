"use client";
/**
 * The notification centre (PROJECT-NOTIFY-001): the bell at the top of every page with the unread count, its panel of
 * the latest notifications, the row used by the panel and the full page, and the window that keeps an announcement
 * requiring acknowledgement in front of its reader until they confirm.
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { useLocale, useTranslations } from "next-intl";

import { useNotify } from "@/components/notify/Notifications";
import { IconBell, IconClipboardCheck, IconDelegation, IconInbox, IconLock, IconMegaphone, IconShield } from "@/components/layout/nav-icons";
import { useFormatter } from "@/hooks/useFormatter";
import {
  acknowledge, markAllRead, markRead, useNotificationSummary, useNotificationText, type Category, type NotificationItem,
} from "@/lib/notifications";
import css from "./notification-center.module.css";

const ICONS: Record<Category, (p: { size?: number }) => ReactNode> = {
  access: IconShield, security: IconLock, delegation: IconDelegation, work: IconClipboardCheck, announcement: IconMegaphone,
};

/** "5 minutes ago", "yesterday", or the date for older ones, in the screen's language. */
function useAgo() {
  const locale = useLocale();
  const fmt = useFormatter();
  return useCallback((iso: string) => {
    const seconds = Math.round((new Date(iso).getTime() - Date.now()) / 1000);
    const rtf = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
    const abs = Math.abs(seconds);
    if (abs < 60) return rtf.format(0, "minute");
    if (abs < 3600) return rtf.format(Math.round(seconds / 60), "minute");
    if (abs < 86400) return rtf.format(Math.round(seconds / 3600), "hour");
    if (abs < 7 * 86400) return rtf.format(Math.round(seconds / 86400), "day");
    return fmt.dateTime(iso);
  }, [locale, fmt]);
}

/** One notification: its kind's icon, its sentence, who and when, and its importance. */
export function NotificationRow({ item, onOpen, showBody = false }: { item: NotificationItem; onOpen?: (item: NotificationItem) => void; showBody?: boolean }) {
  const t = useTranslations("notifications");
  const text = useNotificationText();
  const ago = useAgo();
  const Icon = ICONS[item.category] ?? IconInbox;
  const unread = !item.read && !item.settled;
  const classes = [css.row, unread ? css.unread : "", item.severity === "urgent" ? css.urgent : "", item.settled ? css.settled : ""].join(" ");
  const content = <>
    <span className={`${css.icon} ${css[item.category]}`} aria-hidden="true"><Icon size={19} /></span>
    <span className={css.text}>
      <p className={css.sentence}>{text(item)}</p>
      {showBody && item.announcement && <p className={css.body}>{item.announcement.body}</p>}
      <span className={css.meta}>
        <span>{t(`categories.${item.category}`)}</span>
        <span aria-hidden="true">·</span>
        <time dateTime={item.created_at}>{ago(item.created_at)}</time>
        {item.announcement && item.actor_name && <span>{t("by", { name: item.actor_name })}</span>}
        {item.severity !== "info" && <span className={`${css.chip} ${item.severity === "urgent" ? css.chipUrgent : css.chipImportant}`}>{t(`severity.${item.severity}`)}</span>}
        {item.settled && <span className={`${css.chip} ${css.chipDone}`}>{t("done")}</span>}
        {unread && <span className={css.srOnly}>{t("new")}</span>}
      </span>
    </span>
  </>;
  return onOpen
    ? <button type="button" className={classes} data-link={Boolean(item.link)} onClick={() => onOpen(item)}>{content}</button>
    : <div className={classes}>{content}</div>;
}

/** Reads a notification and goes where it points (an announcement opens the notifications page). */
export function useOpenNotification(after?: () => void) {
  const router = useRouter();
  return useCallback(async (item: NotificationItem) => {
    if (!item.read) await markRead(item.id).catch(() => {});
    after?.();
    const target = item.announcement ? "/notifications" : item.link;
    if (target) router.push(target);
  }, [router, after]);
}

type Tab = "all" | "unread" | "important";

/** The bell at the top of every page: the unread count, and the latest notifications in a panel. */
export function NotificationBell() {
  const t = useTranslations("notifications");
  const notify = useNotify();
  const summary = useNotificationSummary();
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<Tab>("all");
  const [ring, setRing] = useState(false);
  const last = useRef(summary.unread);
  const box = useRef<HTMLDivElement>(null);
  const close = useCallback(() => setOpen(false), []);
  const openItem = useOpenNotification(close);

  useEffect(() => {  // a new notification rings the bell once
    if (summary.unread > last.current) { setRing(true); window.setTimeout(() => setRing(false), 1300); }
    last.current = summary.unread;
  }, [summary.unread]);
  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !box.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", away);
    return () => { document.removeEventListener("mousedown", away); document.removeEventListener("keydown", away); };
  }, [open]);

  const shown = summary.latest.filter((n) => tab === "all" || (tab === "unread" ? !n.read && !n.settled : n.severity !== "info"));
  const count = summary.unread > 99 ? "99+" : String(summary.unread);
  return <div className={css.wrap} ref={box}>
    <button type="button" className={`${css.bell} ${open ? css.bellActive : ""}`} aria-haspopup="dialog" aria-expanded={open}
      aria-label={`${t("bell")} — ${t("unreadCount", { count: summary.unread })}`} onClick={() => setOpen((v) => !v)}>
      <span className={ring ? css.ring : undefined} style={{ display: "inline-grid" }}><IconBell size={21} /></span>
      {summary.unread > 0 && <span className={css.count} aria-hidden="true">{count}</span>}
    </button>
    {open && <div className={css.panel} role="dialog" aria-label={t("title")}>
      <div className={css.panelHead}>
        <div>
          <h2 className={css.panelTitle}>{t("title")}</h2>
          <p className={css.panelSub}>{t("unreadCount", { count: summary.unread })}</p>
        </div>
        <button type="button" className={css.linkButton} disabled={summary.unread === 0}
          onClick={() => void markAllRead().then(() => notify.done("readAll")).catch(() => {})}>{t("markAllRead")}</button>
      </div>
      <div className={css.tabs} role="tablist">
        {(["all", "unread", "important"] as const).map((k) => <button key={k} type="button" role="tab" aria-selected={tab === k}
          className={`${css.tab} ${tab === k ? css.tabOn : ""}`} onClick={() => setTab(k)}>{t(`filters.${k}`)}</button>)}
      </div>
      <div className={css.list}>
        {shown.length === 0
          ? <div className={css.empty}><span className={css.emptyIcon}><IconInbox size={22} /></span>{tab === "unread" ? t("emptyUnread") : t("empty")}</div>
          : shown.map((n) => <NotificationRow key={n.id} item={n} onOpen={(item) => void openItem(item)} />)}
      </div>
      <Link href="/notifications" className={css.panelFoot} onClick={close}>{t("viewAll")}</Link>
    </div>}
  </div>;
}

/** An announcement that requires acknowledgement stays in front of its reader until they confirm they have read it. */
export function AcknowledgeGate() {
  const t = useTranslations("notifications");
  const notify = useNotify();
  const fmt = useFormatter();
  const { pending_ack: pending } = useNotificationSummary();
  const [busy, setBusy] = useState(false);
  const button = useRef<HTMLButtonElement>(null);
  const first = pending[0];
  useEffect(() => { if (first) button.current?.focus(); }, [first]);
  if (!first?.announcement) return null;
  const urgent = first.severity === "urgent";
  async function confirm() {
    setBusy(true);
    try { await acknowledge(first.id); notify.done("acknowledge"); } catch { /* stays open: try again */ } finally { setBusy(false); }
  }
  return <div className={css.overlay}>
    <div className={css.dialog} role="alertdialog" aria-modal="true" aria-labelledby="ack-title" aria-describedby="ack-body">
      <div className={css.dialogHead}>
        <span className={`${css.dialogIcon} ${urgent ? css.dialogUrgent : ""}`} aria-hidden="true"><IconMegaphone size={24} /></span>
        <div>
          <p style={{ margin: 0, color: "var(--text-muted)", fontSize: 13, fontWeight: 700 }}>
            {t("ack.title")} · {t("ack.subtitle", { count: pending.length })}</p>
          <h2 id="ack-title" className={css.dialogTitle}>{first.announcement.title}</h2>
        </div>
      </div>
      <div className={css.dialogBody}><p id="ack-body" className={css.dialogMessage}>{first.announcement.body}</p></div>
      <div className={css.dialogFoot}>
        <span style={{ color: "var(--text-muted)", fontSize: 13 }}>
          {first.actor_name ? t("ack.from", { name: first.actor_name }) : null} · {fmt.dateTime(first.created_at)}
          {first.severity !== "info" && <> · <span className={`${css.chip} ${urgent ? css.chipUrgent : css.chipImportant}`}>{t(`severity.${first.severity}`)}</span></>}
        </span>
        <button ref={button} type="button" className={css.confirm} disabled={busy} onClick={() => void confirm()}>{t("ack.confirm")}</button>
      </div>
    </div>
  </div>;
}
