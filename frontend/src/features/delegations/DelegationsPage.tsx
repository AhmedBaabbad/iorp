"use client";
/**
 * Approval delegations (PROJECT-GOV-004), governed: whoever holds an approval asks to delegate it and a delegation
 * manager agrees; a manager proposes one on a holder's behalf and the holder agrees; the organization's administrator
 * delegating their own needs no one. At most 90 days. The signer of a document is always the person signed in, and the
 * server checks every rule again.
 *
 * Two pages, like every module: the list (server pages, filters, what waits for the user's answer) and a new delegation.
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useTranslations } from "next-intl";

import { PageFrame } from "@/components/layout/page-frame";
import { useNotify } from "@/components/notify/Notifications";
import { Pagination } from "@/components/pagination/Pagination";
import { useFormatter } from "@/hooks/useFormatter";
import { apiClient } from "@/lib/api-client";
import { refreshDelegationsWaiting } from "@/lib/delegations";
import { useListQuery, type Page } from "@/lib/pagination";
import { sharedStyles } from "@/styles/shared-styles";

type Status = "awaiting_manager" | "awaiting_holder" | "lapsed" | "rejected" | "scheduled" | "active" | "ended" | "revoked";
type Delegation = { id: string; delegator_name: string; delegate_name: string; permission_code: string; effective_from: string;
  effective_to: string; reason: string; status: Status; usable: boolean; created_by_name: string; decided_by_name: string | null;
  decision_reason: string | null; revoked_at: string | null; revoked_by_name: string | null; revoke_reason: string | null;
  can_answer: boolean; can_revoke: boolean };
type Options = { delegators: { id: string; name: string; permissions: string[] }[]; delegates: { id: string; name: string }[]; manages: boolean };
type Pending = { delegation: Delegation; verb: "reject" | "revoke" } | null;

const ROOT = "/delegations";
const MAX_DAYS = 90;
const STATES = ["waiting", "active", "scheduled", "ended", "lapsed", "rejected", "revoked"] as const;
const CARD = { background: "var(--surface)", border: "1px solid var(--border-strong)", borderRadius: 8, padding: 18 };
const today = () => new Date().toLocaleDateString("en-CA");
const addDays = (day: string, days: number) => {
  const d = new Date(`${day}T00:00:00`);
  d.setDate(d.getDate() + days);
  return d.toLocaleDateString("en-CA");
};

function useWords() {
  const t = useTranslations("administration.delegations");
  const perms = useTranslations("administration.delegations.permissions");
  const permission = useCallback((code: string) => (perms.has(code.replaceAll(":", "_")) ? perms(code.replaceAll(":", "_")) : code), [perms]);
  const message = useCallback((e: unknown) => {
    const code = (e as { details?: { detail?: unknown } })?.details?.detail;
    return typeof code === "string" && t.has(`errors.${code}`) ? t(`errors.${code}`) : t("errors.generic");
  }, [t]);
  return { t, permission, message };
}

/** The list: one page at a time (ARCH-PAGE-001), what waits for the user's answer on top. */
export function DelegationsPage() {
  const { t, permission, message } = useWords();
  const notify = useNotify();
  const fmt = useFormatter();
  const list = useListQuery(["state", "search"] as const), query = list.apiQuery();
  const [data, setData] = useState<Page<Delegation> | null>(null);
  const [waiting, setWaiting] = useState<Delegation[]>([]);
  const [canDelegate, setCanDelegate] = useState(false);
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [pending, setPending] = useState<Pending>(null), [pendingReason, setPendingReason] = useState("");
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let live = true;
    apiClient<Page<Delegation>>(`${ROOT}?${query}`).then((d) => { if (live) setData(d); }).catch((e) => { if (live) setError(message(e)); });
    apiClient<{ count: number; items: Delegation[] }>(`${ROOT}/waiting`).then((w) => { if (live) setWaiting(w.items ?? []); }).catch(() => {});
    refreshDelegationsWaiting();
    return () => { live = false; };
  }, [query, reload, message]);
  useEffect(() => {
    apiClient<Options>(`${ROOT}/options`).then((o) => setCanDelegate(o.delegators.length > 0)).catch(() => {});
  }, []);

  async function act(call: () => Promise<unknown>, done: string) {
    setBusy(true); setError("");
    try { await call(); notify.done(done); setPending(null); setPendingReason(""); setReload((n) => n + 1); }
    catch (err) { const text = message(err); setError(text); notify.error(text); } finally { setBusy(false); }
  }
  function confirmPending(e: FormEvent) {
    e.preventDefault();
    if (!pending) return;
    const { delegation, verb } = pending;
    void act(() => apiClient(`${ROOT}/${delegation.id}/${verb}`, { method: "POST", body: { reason: pendingReason } }),
      verb === "reject" ? "delegationRejected" : "delegationRevoked");
  }

  const cell = { padding: 10, verticalAlign: "top" as const };
  return <PageFrame title={t("title")} subtitle={t("subtitle")}
    action={canDelegate ? <Link href="/admin/delegations/new" style={sharedStyles.button}>{t("newTitle")}</Link> : undefined}>
    {error && <div role="alert" style={sharedStyles.error}>{error}</div>}

    {waiting.length > 0 && <section style={{ ...CARD, borderColor: "var(--warning)", marginBottom: 16 }} aria-label={t("waitingTitle")}>
      <h2 style={{ margin: "0 0 8px", fontSize: 18 }}>{t("waitingTitle")} ({waiting.length})</h2>
      {waiting.map((d) => <div key={d.id} style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "center", padding: "10px 0", borderTop: "1px solid var(--border)" }}>
        <span style={{ flex: "1 1 320px" }}>{t(`asks.${d.status === "awaiting_holder" ? "awaiting_holder" : "awaiting_manager"}`, { by: d.created_by_name,
          delegate: d.delegate_name, delegator: d.delegator_name, permission: permission(d.permission_code), from: fmt.date(d.effective_from), to: fmt.date(d.effective_to) })}
          <div style={{ color: "var(--text-muted)", fontSize: 13 }}>{t("fields.reason")}: {d.reason}</div></span>
        <button style={sharedStyles.button} disabled={busy}
          onClick={() => void act(() => apiClient(`${ROOT}/${d.id}/approve`, { method: "POST", body: { reason: "" } }), "delegationApproved")}>{t("approve")}</button>
        <button style={sharedStyles.secondaryButton} disabled={busy} onClick={() => { setPending({ delegation: d, verb: "reject" }); setPendingReason(""); }}>{t("reject")}</button>
      </div>)}
    </section>}

    {pending && <section style={{ ...CARD, marginBottom: 16 }}>
      <form onSubmit={confirmPending} style={{ display: "grid", gap: 12 }}>
        <strong>{t(`${pending.verb}Title`, { delegate: pending.delegation.delegate_name, permission: permission(pending.delegation.permission_code) })}</strong>
        <label style={sharedStyles.field}><span style={sharedStyles.label}>{t(`fields.${pending.verb}Reason`)}</span>
          <textarea style={sharedStyles.textarea} required maxLength={2000} value={pendingReason} onChange={(e) => setPendingReason(e.target.value)} /></label>
        <div style={{ display: "flex", gap: 8 }}>
          <button style={sharedStyles.button} disabled={busy}>{t(pending.verb)}</button>
          <button type="button" style={sharedStyles.secondaryButton} onClick={() => setPending(null)}>{t("cancel")}</button>
        </div>
      </form>
    </section>}

    <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginBottom: 12 }}>
      <input style={{ ...sharedStyles.input, flex: "1 1 220px" }} aria-label={t("search")} placeholder={t("searchPlaceholder")}
        value={list.filters.search} onChange={(e) => list.setFilter("search", e.target.value)} />
      <select style={{ ...sharedStyles.input, flex: "0 1 240px" }} aria-label={t("columns.status")} value={list.filters.state}
        onChange={(e) => list.setFilter("state", e.target.value)}>
        <option value="">{t("allStates")}</option>
        {STATES.map((s) => <option key={s} value={s}>{t(`stateFilter.${s}`)}</option>)}
      </select>
    </div>

    <section style={CARD}>
      {!data ? <p>{t("loading")}</p> : !data.items.length ? <p>{t("empty")}</p> : <div style={{ overflowX: "auto" }}><table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead><tr>{(["delegator", "delegate", "permission", "period", "status", "reason", ""] as const).map((k) =>
          <th key={k} style={{ textAlign: "start", padding: 10, color: "var(--text-muted)", fontSize: 13 }}>{k ? t(`columns.${k}`) : ""}</th>)}</tr></thead>
        <tbody>{data.items.map((d) => <tr key={d.id} style={{ borderTop: "1px solid var(--border)" }}>
          <td style={cell}>{d.delegator_name}</td>
          <td style={cell}>{d.delegate_name}</td>
          <td style={cell}>{permission(d.permission_code)}</td>
          <td style={cell}>{fmt.date(d.effective_from)} → {fmt.date(d.effective_to)}</td>
          <td style={cell}>{t(`status.${d.status}`)}
            {d.status === "active" && !d.usable && <div style={{ color: "var(--danger)", fontSize: 12 }}>{t("notUsable")}</div>}
            {d.decided_by_name && d.status !== "awaiting_manager" && d.status !== "awaiting_holder" &&
              <div style={{ fontSize: 12, color: "var(--text-muted)" }}>{t(d.status === "rejected" ? "rejectedBy" : "approvedBy", { name: d.decided_by_name, reason: d.decision_reason ?? "" })}</div>}
            {d.revoked_at && <div style={{ fontSize: 12, color: "var(--text-muted)" }}>{t("revokedBy", { name: d.revoked_by_name ?? "", reason: d.revoke_reason ?? "" })}</div>}</td>
          <td style={cell}>{d.reason}</td>
          <td style={cell}>{d.can_revoke && <button style={sharedStyles.secondaryButton} disabled={busy}
            onClick={() => { setPending({ delegation: d, verb: "revoke" }); setPendingReason(""); }}>{t("revoke")}</button>}</td>
        </tr>)}</tbody>
      </table></div>}
      {data && <Pagination page={data.page} pageSize={data.page_size} total={data.total} pages={data.pages} onPage={list.setPage} onPageSize={list.setPageSize} />}
    </section>
  </PageFrame>;
}

/** A new delegation: a holder asks for their own approval; a manager may propose one on a holder's behalf. */
export function DelegationForm() {
  const { t, permission, message } = useWords();
  const notify = useNotify();
  const router = useRouter();
  const [options, setOptions] = useState<Options | null>(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [form, setForm] = useState({ delegator_user_id: "", delegate_user_id: "", permission_code: "", effective_from: today(), effective_to: "", reason: "" });
  const set = (key: keyof typeof form, value: string) => setForm((f) => ({ ...f, [key]: value }));
  useEffect(() => {
    apiClient<Options>(`${ROOT}/options`).then((o) => {
      setOptions(o);
      if (!o.manages && o.delegators.length === 1) setForm((f) => ({ ...f, delegator_user_id: o.delegators[0].id }));  // a holder: oneself
    }).catch((e) => setError(message(e)));
  }, [message]);
  const delegator = options?.delegators.find((d) => d.id === form.delegator_user_id);

  async function create(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      const made = await apiClient<Delegation>(ROOT, { method: "POST", body: form });
      notify.done({ awaiting_manager: "delegationRequested", awaiting_holder: "delegationProposed", active: "delegationActive",
        scheduled: "delegationScheduled" }[made.status as string] ?? "save");
      refreshDelegationsWaiting();
      router.push("/admin/delegations");
    } catch (err) { const text = message(err); setError(text); notify.error(text); } finally { setBusy(false); }
  }

  return <PageFrame title={t("newTitle")} subtitle={options?.manages ? t("newHintManager") : t("newHint")}
    action={<Link href="/admin/delegations" style={sharedStyles.secondaryButton}>{t("backToList")}</Link>}>
    {error && <div role="alert" style={sharedStyles.error}>{error}</div>}
    {!options ? <p>{t("loading")}</p> : options.delegators.length === 0 ? <p>{t("nothingToDelegate")}</p> :
      <section style={CARD}><form onSubmit={create} style={{ display: "grid", gap: 14, gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
        <label style={sharedStyles.field}><span style={sharedStyles.label}>{t("fields.delegator")}</span>
          <select style={sharedStyles.input} required value={form.delegator_user_id} disabled={!options.manages}
            onChange={(e) => { set("delegator_user_id", e.target.value); set("permission_code", ""); }}>
            <option value="">{t("choose")}</option>
            {options.delegators.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select></label>
        <label style={sharedStyles.field}><span style={sharedStyles.label}>{t("fields.permission")}</span>
          <select style={sharedStyles.input} required value={form.permission_code} onChange={(e) => set("permission_code", e.target.value)}>
            <option value="">{t("choose")}</option>
            {(delegator?.permissions ?? []).map((code) => <option key={code} value={code}>{permission(code)}</option>)}
          </select></label>
        <label style={sharedStyles.field}><span style={sharedStyles.label}>{t("fields.delegate")}</span>
          <select style={sharedStyles.input} required value={form.delegate_user_id} onChange={(e) => set("delegate_user_id", e.target.value)}>
            <option value="">{t("choose")}</option>
            {options.delegates.filter((u) => u.id !== form.delegator_user_id).map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
          </select></label>
        <label style={sharedStyles.field}><span style={sharedStyles.label}>{t("fields.from")}</span>
          <input style={sharedStyles.input} type="date" required min={today()} value={form.effective_from} onChange={(e) => set("effective_from", e.target.value)} /></label>
        <label style={sharedStyles.field}><span style={sharedStyles.label}>{t("fields.to")}</span>
          <input style={sharedStyles.input} type="date" required min={form.effective_from} max={addDays(form.effective_from, MAX_DAYS - 1)}
            value={form.effective_to} onChange={(e) => set("effective_to", e.target.value)} />
          <span style={{ color: "var(--text-muted)", fontSize: 12 }}>{t("maxDays", { days: MAX_DAYS })}</span></label>
        <label style={{ ...sharedStyles.field, gridColumn: "1 / -1" }}><span style={sharedStyles.label}>{t("fields.reason")}</span>
          <textarea style={sharedStyles.textarea} required maxLength={2000} value={form.reason} placeholder={t("reasonHint")} onChange={(e) => set("reason", e.target.value)} /></label>
        <div style={{ display: "flex", gap: 8 }}>
          <button style={sharedStyles.button} disabled={busy}>{options.manages ? t("create") : t("request")}</button>
          <Link href="/admin/delegations" style={sharedStyles.secondaryButton}>{t("cancel")}</Link>
        </div>
      </form></section>}
  </PageFrame>;
}
