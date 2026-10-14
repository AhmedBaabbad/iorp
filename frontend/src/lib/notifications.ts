"use client";
/**
 * Notifications on the screens (PROJECT-NOTIFY-001). The server keeps each user's own notifications; this keeps one
 * shared copy of the bell's summary (unread count, the latest few, announcements to acknowledge), asked again every
 * minute, when the window comes back into view, and after the user reads or acknowledges something.
 */
import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { useFormatter } from "@/hooks/useFormatter";
import { apiClient } from "@/lib/api-client";

export type Category = "access" | "security" | "delegation" | "work" | "announcement";
export type Severity = "info" | "important" | "urgent";
export type NotificationItem = {
  id: string; event: string; category: Category; severity: Severity; params: Record<string, string | number | null>;
  link: string | null; actor_name: string | null; created_at: string; read: boolean; settled: boolean;
  announcement: null | { id: string; title: string; body: string; requires_ack: boolean; acknowledged: boolean };
};
export type Summary = { unread: number; latest: NotificationItem[]; pending_ack: NotificationItem[] };

export const ANNOUNCEMENTS_SEND = "notifications:announcements:send";
export const ANNOUNCEMENTS_MANAGE = "notifications:announcements:manage";
export const ANNOUNCEMENTS_PAGE = [ANNOUNCEMENTS_SEND, ANNOUNCEMENTS_MANAGE];

const EVERY_MS = 60_000;
const EMPTY: Summary = { unread: 0, latest: [], pending_ack: [] };
let current: Summary = EMPTY;
const listeners = new Set<(s: Summary) => void>();
let inflight: Promise<void> | null = null;

/** Ask the server again; every bell and window on the screen follows. */
export function refreshNotifications(): Promise<void> {
  inflight ??= apiClient<Summary>("/notifications/summary")
    .then((s) => { current = s ?? EMPTY; listeners.forEach((l) => l(current)); })
    .catch(() => {})
    .finally(() => { inflight = null; });
  return inflight;
}

export async function markRead(id: string) {
  await apiClient(`/notifications/${id}/read`, { method: "POST", notify: false });
  await refreshNotifications();
}

export async function markAllRead() {
  await apiClient("/notifications/read-all", { method: "POST", notify: false });
  await refreshNotifications();
}

/** The reader puts a notification away (never an announcement still to acknowledge). */
export async function hide(id: string) {
  await apiClient(`/notifications/${id}/hide`, { method: "POST", notify: false });
  await refreshNotifications();
}

export async function hideRead() {
  await apiClient("/notifications/hide-read", { method: "POST", notify: false });
  await refreshNotifications();
}

export async function acknowledge(id: string) {
  await apiClient(`/notifications/${id}/acknowledge`, { method: "POST", notify: false });
  await refreshNotifications();
}

/** The bell's summary, kept fresh while the screen is open. */
export function useNotificationSummary(enabled = true): Summary {
  const [summary, setSummary] = useState<Summary>(current);
  useEffect(() => {
    if (!enabled) return;
    listeners.add(setSummary);
    void refreshNotifications();
    const timer = window.setInterval(() => { if (document.visibilityState === "visible") void refreshNotifications(); }, EVERY_MS);
    const onFocus = () => { if (document.visibilityState === "visible") void refreshNotifications(); };
    document.addEventListener("visibilitychange", onFocus);
    return () => { listeners.delete(setSummary); window.clearInterval(timer); document.removeEventListener("visibilitychange", onFocus); };
  }, [enabled]);
  return enabled ? summary : EMPTY;
}

const ISO_DATE = /^\d{4}-\d{2}-\d{2}($|T)/;

/** A notification's sentence in the screen's language: the event's words filled with its details. */
export function useNotificationText() {
  const t = useTranslations("notifications");
  const permissions = useTranslations("administration.delegations.permissions");
  const fmt = useFormatter();
  return useCallback((n: NotificationItem): string => {
    if (n.announcement) return n.announcement.title;
    const values: Record<string, string> = { actor: n.actor_name || t("system") };
    for (const [key, raw] of Object.entries(n.params ?? {})) {
      const value = raw === null || raw === undefined || raw === "" ? "—" : String(raw);
      values[key] = key === "permission" && permissions.has(value.replaceAll(":", "_")) ? permissions(value.replaceAll(":", "_"))
        : key === "status" && t.has(`supplierStatus.${value}`) ? t(`supplierStatus.${value}`)
        : ISO_DATE.test(value) ? fmt.date(value)
        : value;
    }
    const key = `events.${n.event}`;
    if (!t.has(key)) return t(`categories.${n.category}`);
    try { return t(key, values); } catch { return t(`categories.${n.category}`); }
  }, [t, permissions, fmt]);
}
