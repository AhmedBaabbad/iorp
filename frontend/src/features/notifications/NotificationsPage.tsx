"use client";
/**
 * All of the user's notifications (PROJECT-NOTIFY-001), one server page at a time (ARCH-PAGE-001), filtered by kind:
 * unread, important, or by what they are about. Announcements show their whole message here.
 */
import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { PageFrame } from "@/components/layout/page-frame";
import { NotificationRow, useOpenNotification } from "@/components/notify/NotificationCenter";
import { useNotify } from "@/components/notify/Notifications";
import css from "@/components/notify/notification-center.module.css";
import { Pagination } from "@/components/pagination/Pagination";
import { apiClient } from "@/lib/api-client";
import { hide, hideRead, markAllRead, markRead, useNotificationSummary, type NotificationItem } from "@/lib/notifications";
import { useListQuery, type Page } from "@/lib/pagination";

const KINDS = ["all", "unread", "important", "work", "access", "delegation", "security", "announcement"] as const;

export function NotificationsPage() {
  const t = useTranslations("notifications");
  const notify = useNotify();
  const list = useListQuery(["kind"] as const), query = list.apiQuery();
  const kind = list.filters.kind || "all";
  const summary = useNotificationSummary();
  const [data, setData] = useState<Page<NotificationItem> | null>(null);
  const [error, setError] = useState(false);
  const [reload, setReload] = useState(0);
  const again = useCallback(() => setReload((n) => n + 1), []);
  const open = useOpenNotification(again);
  // A notification about a document opens it; an announcement (its message is here) or one without a link is just read.
  const activate = (item: NotificationItem) => {
    if (item.link && !item.announcement) void open(item);
    else void markRead(item.id).then(again).catch(() => {});
  };

  useEffect(() => {
    let live = true;
    setError(false);
    apiClient<Page<NotificationItem>>(`/notifications?${query}`).then((d) => { if (live) setData(d); }).catch(() => { if (live) setError(true); });
    return () => { live = false; };
  }, [query, reload, summary.unread]);

  return <PageFrame title={t("title")} subtitle={t("subtitle")}
    action={<div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
      <button type="button" className={css.linkButton} disabled={summary.unread === 0} style={{ fontSize: 14 }}
        onClick={() => void markAllRead().then(() => { notify.done("readAll"); again(); }).catch(() => {})}>{t("markAllRead")}</button>
      <button type="button" className={css.linkButton} style={{ fontSize: 14 }}
        onClick={() => void hideRead().then(() => { notify.success(t("hidden")); again(); }).catch(() => {})}>{t("hideRead")}</button>
    </div>}>
    <div className={css.toolbar}>
      <div className={css.tabs} role="tablist" style={{ padding: 0 }}>
        {KINDS.map((k) => <button key={k} type="button" role="tab" aria-selected={kind === k} className={`${css.tab} ${kind === k ? css.tabOn : ""}`}
          onClick={() => list.setFilter("kind", k === "all" ? "" : k)}>{t(`filters.${k}`)}</button>)}
      </div>
      <span style={{ color: "var(--text-muted)", fontSize: 14 }}>{t("unreadCount", { count: summary.unread })}</span>
    </div>
    <section className={css.pageList}>
      {error ? <div className={css.empty} role="alert">{t("error")}</div>
        : !data ? <div className={css.empty}>{t("loading")}</div>
        : data.items.length === 0 ? <div className={css.empty}>{kind === "unread" ? t("emptyUnread") : t("empty")}</div>
        : data.items.map((n) => <div key={n.id} style={{ position: "relative" }}>
            <NotificationRow item={n} showBody onOpen={(n.link && !n.announcement) || !n.read ? activate : undefined} />
            {!(n.announcement?.requires_ack && !n.announcement.acknowledged) &&
              <button type="button" className={css.linkButton} style={{ position: "absolute", bottom: 10, insetInlineEnd: 14 }}
                onClick={() => void hide(n.id).then(() => { notify.success(t("hidden")); again(); }).catch(() => notify.error(t("needsAck")))}>{t("hide")}</button>}
          </div>)}
    </section>
    {data && data.total > 0 && <Pagination page={data.page} pageSize={data.page_size} total={data.total} pages={data.pages}
      onPage={list.setPage} onPageSize={list.setPageSize} />}
  </PageFrame>;
}
