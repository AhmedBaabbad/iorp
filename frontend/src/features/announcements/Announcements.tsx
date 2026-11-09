"use client";
/**
 * Announcements (PROJECT-NOTIFY-001): a message written by a holder of notifications:announcements:send to named users,
 * a role's members or the whole organization; its author (and a holder of :manage, for every announcement) follows who
 * read it and who acknowledged it, and may withdraw it. Three pages, like every module: the list, a new one, one detail.
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type CSSProperties, type FormEvent } from "react";
import { useTranslations } from "next-intl";

import { PageFrame } from "@/components/layout/page-frame";
import { useNotify } from "@/components/notify/Notifications";
import css from "@/components/notify/notification-center.module.css";
import { Pagination } from "@/components/pagination/Pagination";
import { useFormatter } from "@/hooks/useFormatter";
import { apiClient } from "@/lib/api-client";
import type { Severity } from "@/lib/notifications";
import { useListQuery, type Page } from "@/lib/pagination";
import { sharedStyles } from "@/styles/shared-styles";

type Audience = "users" | "role" | "everyone";
type Announcement = {
  id: string; title: string; body: string; severity: Severity; requires_ack: boolean; audience: Audience; audience_label: string | null;
  recipient_count: number; author_name: string; created_at: string; expires_at: string | null; withdrawn_at: string | null;
  withdrawn_by_name: string | null; state: "live" | "expired" | "withdrawn"; read_count: number; acknowledged_count: number; can_withdraw: boolean;
};
type Receipt = { user_id: string; name: string; read_at: string | null; acknowledged_at: string | null };
type Options = { users: { id: string; name: string }[]; roles: { id: string; code: string; name: string }[] };

const ROOT = "/announcements";
const CARD: CSSProperties = { minInlineSize: 0, background: "var(--surface)", border: "1px solid var(--border-strong)", borderRadius: 12, padding: 18 };
const cell: CSSProperties = { padding: 10, verticalAlign: "top" };
const SEVERITY_CHIP: Record<Severity, string> = { info: "", important: css.chipImportant, urgent: css.chipUrgent };

function useWords() {
  const t = useTranslations("notifications.announcements");
  const n = useTranslations("notifications");
  const message = (e: unknown) => {
    const code = (e as { details?: { detail?: unknown } })?.details?.detail;
    return typeof code === "string" && t.has(`errors.${code}`) ? t(`errors.${code}`) : t("errors.generic");
  };
  const audience = (a: Announcement) => a.audience === "everyone" ? t("everyone")
    : a.audience === "role" ? a.audience_label ?? t("audience.role") : t("usersCount", { count: a.recipient_count });
  return { t, n, message, audience };
}

function Chip({ severity }: { severity: Severity }) {
  const n = useTranslations("notifications");
  return <span className={`${css.chip} ${SEVERITY_CHIP[severity]}`} style={severity === "info" ? { background: "var(--surface-muted)" } : undefined}>
    {n(`severity.${severity}`)}</span>;
}

/** The announcements the user sent (all of them for a manager), with how many read and acknowledged. */
export function AnnouncementsList() {
  const { t, audience } = useWords();
  const fmt = useFormatter();
  const router = useRouter();
  const list = useListQuery(["search", "state"] as const), query = list.apiQuery();
  const [data, setData] = useState<Page<Announcement> | null>(null);
  useEffect(() => {
    let live = true;
    apiClient<Page<Announcement>>(`${ROOT}?${query}`).then((d) => { if (live) setData(d); }).catch(() => { if (live) setData({ items: [], total: 0, page: 1, page_size: 50, pages: 0 }); });
    return () => { live = false; };
  }, [query]);
  return <PageFrame title={t("title")} subtitle={t("subtitle")}
    action={<Link href="/admin/announcements/new" style={sharedStyles.button}>{t("new")}</Link>}>
    <input style={{ ...sharedStyles.input, maxWidth: 360, marginBottom: 12 }} aria-label={t("search")} placeholder={t("searchPlaceholder")}
      value={list.filters.search} onChange={(e) => list.setFilter("search", e.target.value)} />
    <select style={{ ...sharedStyles.input, maxWidth: 220, marginBottom: 12, marginInlineStart: 8 }} aria-label={t("columns.state")} value={list.filters.state}
      onChange={(e) => list.setFilter("state", e.target.value)}>
      <option value="">{t("allStates")}</option>
      {(["live", "expired", "withdrawn"] as const).map((s) => <option key={s} value={s}>{t(`state.${s}`)}</option>)}
    </select>
    <section style={CARD}>
      {!data ? <p>{t("loading")}</p> : !data.items.length ? <p>{t("empty")}</p> : <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead><tr>{(["title", "audience", "severity", "sent", "read", "ack", "state"] as const).map((k) =>
            <th key={k} style={{ ...cell, textAlign: "start", color: "var(--text-muted)", fontSize: 13 }}>{t(`columns.${k}`)}</th>)}</tr></thead>
          <tbody>{data.items.map((a) => <tr key={a.id} style={{ borderTop: "1px solid var(--border)", cursor: "pointer" }}
            onClick={() => router.push(`/admin/announcements/${a.id}`)}>
            <td style={cell}><Link href={`/admin/announcements/${a.id}`} style={{ color: "var(--accent-strong)", fontWeight: 700 }}>{a.title}</Link></td>
            <td style={cell}>{audience(a)}</td>
            <td style={cell}><Chip severity={a.severity} /></td>
            <td style={cell}>{fmt.dateTime(a.created_at)}</td>
            <td style={cell}>{t("readOf", { done: a.read_count, total: a.recipient_count })}</td>
            <td style={cell}>{a.requires_ack ? t("readOf", { done: a.acknowledged_count, total: a.recipient_count }) : "—"}</td>
            <td style={cell}>{t(`state.${a.state}`)}</td>
          </tr>)}</tbody>
        </table></div>}
      {data && data.total > 0 && <Pagination page={data.page} pageSize={data.page_size} total={data.total} pages={data.pages}
        onPage={list.setPage} onPageSize={list.setPageSize} />}
    </section>
  </PageFrame>;
}

/** A new announcement: what, how important, to whom, and whether its readers must confirm. */
export function AnnouncementForm() {
  const { t, message } = useWords();
  const notify = useNotify();
  const router = useRouter();
  const [options, setOptions] = useState<Options | null>(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [form, setForm] = useState({ title: "", body: "", severity: "info" as Severity, requires_ack: false, audience: "everyone" as Audience,
    role_id: "", user_ids: [] as string[], expires_at: "" });
  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) => setForm((f) => ({ ...f, [key]: value }));
  useEffect(() => { apiClient<Options>(`${ROOT}/options`).then(setOptions).catch((e) => setError(message(e))); }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  async function send(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      const made = await apiClient<Announcement>(ROOT, { method: "POST", notify: false, body: {
        title: form.title, body: form.body, severity: form.severity, requires_ack: form.requires_ack, audience: form.audience,
        role_id: form.audience === "role" ? form.role_id || null : null, user_ids: form.audience === "users" ? form.user_ids : [],
        expires_at: form.expires_at ? new Date(`${form.expires_at}T23:59:59`).toISOString() : null } });
      notify.success(t("sent", { count: made.recipient_count }));
      router.push(`/admin/announcements/${made.id}`);
    } catch (err) { const text = message(err); setError(text); notify.error(text); } finally { setBusy(false); }
  }

  const label = (key: string) => <span style={sharedStyles.label}>{t(`fields.${key}`)}</span>;
  return <PageFrame title={t("new")} subtitle={t("newSubtitle")}
    action={<Link href="/admin/announcements" style={sharedStyles.secondaryButton}>{t("backToList")}</Link>}>
    {error && <div role="alert" style={sharedStyles.error}>{error}</div>}
    <section style={CARD}><form onSubmit={send} style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))" }}>
      <label style={{ ...sharedStyles.field, gridColumn: "1 / -1" }}>{label("title")}
        <input style={sharedStyles.input} required maxLength={200} value={form.title} onChange={(e) => set("title", e.target.value)} /></label>
      <label style={{ ...sharedStyles.field, gridColumn: "1 / -1" }}>{label("body")}
        <textarea style={{ ...sharedStyles.textarea, minHeight: 140 }} required maxLength={5000} value={form.body} onChange={(e) => set("body", e.target.value)} /></label>
      <label style={sharedStyles.field}>{label("severity")}
        <select style={sharedStyles.input} value={form.severity} onChange={(e) => set("severity", e.target.value as Severity)}>
          {(["info", "important", "urgent"] as const).map((s) => <option key={s} value={s}><SeverityName severity={s} /></option>)}
        </select></label>
      <label style={sharedStyles.field}>{label("audience")}
        <select style={sharedStyles.input} value={form.audience} onChange={(e) => set("audience", e.target.value as Audience)}>
          {(["everyone", "role", "users"] as const).map((a) => <option key={a} value={a}>{t(`audience.${a}`)}</option>)}
        </select></label>
      {form.audience === "role" && <label style={sharedStyles.field}>{label("role")}
        <select style={sharedStyles.input} required value={form.role_id} onChange={(e) => set("role_id", e.target.value)}>
          <option value="">{t("choose")}</option>
          {options?.roles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
        </select></label>}
      {form.audience === "users" && <fieldset style={{ ...sharedStyles.field, gridColumn: "1 / -1", border: "1px solid var(--border)", borderRadius: 10, padding: 12 }}>
        <legend style={sharedStyles.label}>{t("fields.users")}</legend>
        <div style={{ display: "grid", gap: 6, gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", maxHeight: 220, overflowY: "auto" }}>
          {options?.users.map((u) => <label key={u.id} style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input type="checkbox" checked={form.user_ids.includes(u.id)}
              onChange={(e) => set("user_ids", e.target.checked ? [...form.user_ids, u.id] : form.user_ids.filter((x) => x !== u.id))} />{u.name}</label>)}
        </div></fieldset>}
      <label style={sharedStyles.field}>{label("expiresAt")}
        <input style={sharedStyles.input} type="date" value={form.expires_at} min={new Date().toLocaleDateString("en-CA")}
          onChange={(e) => set("expires_at", e.target.value)} /></label>
      <label style={{ display: "flex", gap: 10, alignItems: "center", gridColumn: "1 / -1", fontWeight: 700 }}>
        <input type="checkbox" checked={form.requires_ack} onChange={(e) => set("requires_ack", e.target.checked)} />{t("fields.requiresAck")}</label>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, gridColumn: "1 / -1" }}>
        <button style={sharedStyles.button} disabled={busy || !options}>{t("send")}</button>
        <Link href="/admin/announcements" style={sharedStyles.secondaryButton}>{t("cancel")}</Link>
      </div>
    </form></section>
  </PageFrame>;
}

function SeverityName({ severity }: { severity: Severity }) {
  const n = useTranslations("notifications");
  return <>{n(`severity.${severity}`)}</>;
}

/** One announcement: its message, and each reader with when they read and acknowledged it. */
export function AnnouncementDetail({ id }: { id: string }) {
  const { t, message, audience } = useWords();
  const notify = useNotify();
  const fmt = useFormatter();
  const [data, setData] = useState<(Announcement & { receipts: Receipt[] }) | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { apiClient<Announcement & { receipts: Receipt[] }>(`${ROOT}/${id}`).then(setData).catch((e) => setError(message(e))); }, [id]);  // eslint-disable-line react-hooks/exhaustive-deps

  async function withdraw() {
    if (!window.confirm(t("confirmWithdraw"))) return;
    try { setData(await apiClient(`${ROOT}/${id}/withdraw`, { method: "POST", notify: false })); notify.success(t("withdrawn")); }
    catch (e) { notify.error(message(e)); }
  }

  return <PageFrame title={data?.title ?? t("title")} subtitle={data ? t("author", { name: data.author_name, date: fmt.dateTime(data.created_at) }) : undefined}
    action={<div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
      {data?.can_withdraw && <button type="button" style={sharedStyles.secondaryButton} onClick={() => void withdraw()}>{t("withdraw")}</button>}
      <Link href="/admin/announcements" style={sharedStyles.secondaryButton}>{t("backToList")}</Link></div>}>
    {error && <div role="alert" style={sharedStyles.error}>{error}</div>}
    {!data ? !error && <p>{t("loading")}</p> : <div style={{ display: "grid", gap: 16 }}>
      <section style={CARD}>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center", marginBottom: 12, color: "var(--text-muted)", fontSize: 14 }}>
          <Chip severity={data.severity} /><span>{t("columns.audience")}: <strong style={{ color: "var(--text)" }}>{audience(data)}</strong></span>
          <span>· {t(`state.${data.state}`)}</span>
          {data.withdrawn_at && <span>· {t("withdrawnBy", { name: data.withdrawn_by_name ?? "", date: fmt.dateTime(data.withdrawn_at) })}</span>}
        </div>
        <p className={css.dialogMessage}>{data.body}</p>
      </section>
      <section style={CARD}>
        <h2 style={{ margin: "0 0 4px", fontSize: 18 }}>{t("receipts")}</h2>
        <p style={{ margin: "0 0 12px", color: "var(--text-muted)" }}>
          {t("columns.read")}: {t("readOf", { done: data.read_count, total: data.recipient_count })}
          {data.requires_ack && <> · {t("columns.ack")}: {t("readOf", { done: data.acknowledged_count, total: data.recipient_count })}</>}</p>
        <div style={{ overflowX: "auto" }}><table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead><tr>{(["name", "read", ...(data.requires_ack ? ["ack"] : [])] as const).map((k) =>
            <th key={k} style={{ ...cell, textAlign: "start", color: "var(--text-muted)", fontSize: 13 }}>{t(`receiptColumns.${k}`)}</th>)}</tr></thead>
          <tbody>{data.receipts.map((r) => <tr key={r.user_id} style={{ borderTop: "1px solid var(--border)" }}>
            <td style={cell}>{r.name}</td>
            <td style={cell}>{r.read_at ? fmt.dateTime(r.read_at) : <span style={{ color: "var(--text-muted)" }}>{t("notYet")}</span>}</td>
            {data.requires_ack && <td style={cell}>{r.acknowledged_at ? <span className={`${css.chip} ${css.chipDone}`}>{fmt.dateTime(r.acknowledged_at)}</span>
              : <span style={{ color: "var(--text-muted)" }}>{t("notYet")}</span>}</td>}
          </tr>)}</tbody>
        </table></div>
      </section>
    </div>}
  </PageFrame>;
}
