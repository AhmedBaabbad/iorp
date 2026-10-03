"use client";

import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { apiClient } from "@/lib/api-client";
import { hasPermission, useAuth } from "@/features/auth/auth-context";
import { sharedStyles as styles } from "@/styles/shared-styles";
import { P } from "@/lib/production-permissions";

type Member = { id?: string; workforce_member_id: string; workforce_name?: string; employee_code?: string; role_code?: string; role_note?: string | null; is_lead?: boolean; is_shift_lead?: boolean; started_at?: string | null; ended_at?: string | null; notes?: string | null };
type RecordData = { members_editable?: boolean; period_state?: "upcoming" | "current" | "ended"; id: string; name?: string | null; shift_definition_id: string | null; shift_roster_id?: string | null; shift_name: string | null; work_center_name?: string; run_date?: string; effective_from?: string; effective_to?: string | null; started_at?: string | null; ended_at?: string | null; status: string; team_count: number; members: Member[] };
type Option = { id: string; name: string };
type Worker = { id: string; full_name: string; employee_code: string; status: string };
const base = "/production/";
const emptyDraft: Member = { workforce_member_id: "", role_code: "operator" };

// datetime-local works in local wall time without a zone; the API stores UTC instants.
function toLocalInput(iso?: string | null) {
  if (!iso) return "";
  const date = new Date(iso);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

export function ExecutionPanel({ orderId }: { orderId?: string }) {
  const t = useTranslations("production.execution");
  const locale = useLocale();
  const { permissions } = useAuth();
  const resource = orderId ? "runs" : "shift_rosters";
  const can = useCallback((action: string) => hasPermission(permissions, `production:${resource}:${action}`), [permissions, resource]);
  const [rows, setRows] = useState<RecordData[]>([]);
  const [shifts, setShifts] = useState<Option[]>([]);
  const [centers, setCenters] = useState<Option[]>([]);
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [rosters, setRosters] = useState<RecordData[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(false);
  const [replacement, setReplacement] = useState<string | null>(null);
  const [shift, setShift] = useState("");
  const [center, setCenter] = useState("");
  const [roster, setRoster] = useState("");
  const [day, setDay] = useState("");
  const [until, setUntil] = useState("");
  const [name, setName] = useState("");
  const [team, setTeam] = useState<Member[]>([]);
  const [selected, setSelected] = useState<RecordData | null>(null);
  const [closeDate, setCloseDate] = useState("");
  const [workerFilter, setWorkerFilter] = useState("");
  const [memberDraft, setMemberDraft] = useState<Member>(emptyDraft);

  const load = useCallback(async () => {
    if (!can("read")) { setLoading(false); return; }
    const query = new URLSearchParams();
    if (orderId) query.set("production_order_id", orderId);
    if (orderId && workerFilter) query.set("workforce_member_id", workerFilter);
    const data = await apiClient<RecordData[]>(`${base}${orderId ? "runs" : "shift-rosters"}?${query}`);
    setRows(data);
    setSelected(current => current ? data.find(row => row.id === current.id) ?? null : null);
  }, [can, orderId, workerFilter]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    load().catch(e => { if (active) setError(String(e.message)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [load]);

  useEffect(() => {
    if (!can("read")) return;
    const requests: Promise<void>[] = [];
    if (hasPermission(permissions, P.SHIFTS_READ)) requests.push(apiClient<Option[]>(base + "shift-definitions").then(setShifts));
    if (hasPermission(permissions, "workforce:members:read")) requests.push(apiClient<Worker[]>("/workforce-members").then(setWorkers));
    if (orderId && hasPermission(permissions, P.WORK_CENTERS_READ)) requests.push(apiClient<Option[]>(base + "work-centers").then(setCenters));
    if (orderId && hasPermission(permissions, P.ROSTERS_READ)) requests.push(apiClient<RecordData[]>(base + "shift-rosters").then(setRosters));
    Promise.all(requests).catch(e => setError(String(e.message)));
  }, [can, orderId, permissions]);

  async function mutate(path: string, body?: unknown, method: "POST" | "PUT" | "DELETE" = "POST") {
    setBusy(true); setError("");
    try { await apiClient(base + path, { method, body }); await load(); return true; }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); return false; }
    finally { setBusy(false); }
  }

  function memberBody(m: Member) {
    return orderId ? { workforce_member_id: m.workforce_member_id, role_code: m.role_code || "operator", is_lead: Boolean(m.is_lead), started_at: m.started_at ?? null, ended_at: m.ended_at ?? null, notes: m.notes ?? null }
      : { workforce_member_id: m.workforce_member_id, role_note: m.role_note || null, is_shift_lead: Boolean(m.is_shift_lead) };
  }

  function openForm(row?: RecordData) {
    setEditing(true); setReplacement(row?.id ?? null); setShift(row?.shift_definition_id ?? "");
    setTeam(row?.members.map(m => ({ ...m, id: undefined })) ?? []);
    setDay(""); setUntil(""); setName(row?.name ?? ""); setRoster("");
  }

  const workerLabel = (w: Worker) => `${w.employee_code} — ${w.full_name}${w.status === "active" ? "" : ` ${t("inactiveWorker")}`}`;
  // Only active workers can join a team; the current value stays visible when it is locked.
  const workerSelect = (value: string, change: (id: string) => void, { optional = false, activeOnly = true, locked = false } = {}) => <select aria-label={t("worker")} style={styles.input} value={value} onChange={e => change(e.target.value)} required={!optional} disabled={locked}>
    <option value="">{t("selectWorker")}</option>
    {workers.filter(w => !activeOnly || w.status === "active" || w.id === value).map(w => <option key={w.id} value={w.id}>{workerLabel(w)}</option>)}
  </select>;
  const memberFields = (m: Member, change: (m: Member) => void, locked = false) => <>
    {workerSelect(m.workforce_member_id, id => change({ ...m, workforce_member_id: id }), { locked })}
    <input style={styles.input} aria-label={t("role")} placeholder={t("role")} value={orderId ? m.role_code ?? "" : m.role_note ?? ""} onChange={e => change({ ...m, [orderId ? "role_code" : "role_note"]: e.target.value })} required={Boolean(orderId)} maxLength={orderId ? 64 : 255} />
    <label><input type="checkbox" checked={Boolean(orderId ? m.is_lead : m.is_shift_lead)} onChange={e => change({ ...m, [orderId ? "is_lead" : "is_shift_lead"]: e.target.checked })} /> {t("lead")}</label>
  </>;
  const statusLabel = (row: RecordData) => {
    const status = t.has(`status.${row.status}`) ? t(`status.${row.status}`) : row.status;
    return row.period_state ? `${status} · ${t(`period.${row.period_state}`)}` : status;
  };
  const formatInstant = (iso: string) => new Date(iso).toLocaleString(locale);
  const runActions: [string, string, string[]][] = [["start", "start", ["planned", "paused"]], ["pause", "pause", ["in_progress"]], ["complete", "complete", ["in_progress", "paused"]], ["cancel", "cancel", ["planned", "in_progress", "paused"]]];

  if (!can("read")) return null;
  const runStarted = Boolean(orderId && selected && selected.status !== "planned");
  return <section style={{ padding: 24, background: "var(--surface)", border: "1px solid var(--border-strong)", borderRadius: 8, marginTop: 20 }}>
    <h2>{orderId ? t("runsTitle") : t("rostersTitle")}</h2>
    {!orderId && <Link href="/shifts">{t("shiftDefinitionsLink")}</Link>}
    <p>{orderId ? t("runsHint") : t("rostersHint")}</p>
    {error && <p role="alert" style={styles.error}>{error}</p>}
    <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
      {/* Rosters page shows only the create action; runs keep their worker filter. */}
      {orderId && workerSelect(workerFilter, setWorkerFilter, { optional: true, activeOnly: false })}
      {can("create") && can("manage_members") && <button style={styles.button} disabled={busy} onClick={() => openForm()}>{t("create")}</button>}
    </div>
    {loading ? <p>{t("loading")}</p> : rows.length === 0 ? <p>{t("empty")}</p> : <div style={{ overflowX: "auto" }}><table style={{ width: "100%", textAlign: "start", borderSpacing: 12 }}>
      <thead><tr>{[t("columns.record"), t("columns.shift"), orderId ? t("columns.workCenter") : t("columns.lead"), t("columns.dateStart"), t("columns.end"), t("columns.status"), t("columns.team")].map(h => <th key={h}>{h}</th>)}</tr></thead>
      <tbody>{rows.map(row => <tr key={row.id}><td><button style={styles.secondaryButton} onClick={() => { setSelected(row); setCloseDate(""); setMemberDraft(emptyDraft); }}>{row.name || row.id.slice(0, 8)}</button></td><td>{row.shift_name || "—"}</td><td>{orderId ? row.work_center_name : row.members.filter(m => m.is_shift_lead).map(m => m.workforce_name).join(", ") || "—"}</td><td>{row.run_date || row.effective_from}{row.started_at && <div>{formatInstant(row.started_at)}</div>}</td><td>{row.effective_to || (row.ended_at ? formatInstant(row.ended_at) : "—")}</td><td>{statusLabel(row)}</td><td>{orderId ? row.team_count : <TeamList members={row.members} empty={t("noMembers")} lead={t("leadMarker")} />}</td></tr>)}</tbody>
    </table></div>}

    {editing && <form onSubmit={async e => {
      e.preventDefault();
      const body = orderId ? { production_order_id: orderId, work_center_id: center, shift_definition_id: shift || null, shift_roster_id: roster || null, run_date: day, members: team.map(memberBody) }
        : { shift_definition_id: shift, name: name || null, effective_from: day, effective_to: until || null, members: team.map(memberBody) };
      if (await mutate(orderId ? "runs" : replacement ? `shift-rosters/${replacement}/replace` : "shift-rosters", body)) setEditing(false);
    }} style={{ display: "grid", gap: 12, marginTop: 20 }}>
      <h3>{replacement ? t("replacementRoster") : t("newRecord")}</h3>
      {!orderId && <label>{t("name")}<input style={styles.input} value={name} onChange={e => setName(e.target.value)} maxLength={255} /></label>}
      <label>{t("shift")}<select aria-label={t("shift")} style={styles.input} required={!orderId} value={shift} disabled={Boolean(replacement)} onChange={e => { setShift(e.target.value); setRoster(""); }}><option value="">{t("selectShift")}</option>{shifts.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
      <label>{t("dateFrom")}<input style={styles.input} type="date" required value={day} onChange={e => { setDay(e.target.value); setRoster(""); }} /></label>
      {!orderId && <label>{t("effectiveTo")}<input style={styles.input} type="date" min={day} value={until} onChange={e => setUntil(e.target.value)} /></label>}
      {orderId && <><label>{t("workCenter")}<select aria-label={t("workCenter")} style={styles.input} required value={center} onChange={e => setCenter(e.target.value)}><option value="">—</option>{centers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
        <label>{t("roster")}<select aria-label={t("roster")} style={styles.input} value={roster} onChange={e => { setRoster(e.target.value); const r = rosters.find(r => r.id === e.target.value); if (r) setShift(r.shift_definition_id || ""); }}><option value="">—</option>{rosters.filter(r => (!shift || r.shift_definition_id === shift) && day && r.effective_from! <= day && (!r.effective_to || r.effective_to >= day)).map(r => <option key={r.id} value={r.id}>{r.shift_name} — {r.name || r.effective_from}</option>)}</select></label>
        <button style={styles.secondaryButton} type="button" disabled={!roster} onClick={() => {
          const r = rosters.find(r => r.id === roster);
          const active = new Set(workers.filter(w => w.status === "active").map(w => w.id));
          if (r) setTeam(r.members.filter(m => active.has(m.workforce_member_id)).map(m => ({ workforce_member_id: m.workforce_member_id, role_code: "operator", is_lead: m.is_shift_lead, notes: m.role_note })));
        }}>{t("loadRosterMembers")}</button></>}
      <h4>{t("team")}</h4>
      {team.map((m, i) => <div key={i} style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>{memberFields(m, value => setTeam(team.map((x, index) => i === index ? value : x)))}<button style={styles.secondaryButton} type="button" onClick={() => setTeam(team.filter((_, index) => i !== index))}>{t("remove")}</button></div>)}
      <button style={styles.secondaryButton} type="button" onClick={() => setTeam([...team, { ...emptyDraft }])}>{t("addWorker")}</button>
      <button style={styles.button} disabled={busy}>{t("save")}</button><button style={styles.secondaryButton} type="button" onClick={() => setEditing(false)}>{t("cancel")}</button>
    </form>}

    {selected && <section style={{ borderTop: "1px solid var(--border-strong)", marginTop: 20, paddingTop: 16 }}>
      <h3>{selected.name || selected.id}</h3>
      <ul>{selected.members.map(m => <li key={m.id} style={{ marginBottom: 12 }}>{m.employee_code} — {m.workforce_name} · {m.role_code || m.role_note} {(m.is_lead || m.is_shift_lead) && t("leadMarker")}
        {orderId && m.started_at && <> · {formatInstant(m.started_at)} → {m.ended_at ? formatInstant(m.ended_at) : "…"}</>}
        {can("manage_members") && <>
          {(!orderId ? selected.members_editable : selected.status === "planned") && <button style={styles.secondaryButton} disabled={busy} onClick={() => mutate(`${orderId ? "runs" : "shift-rosters"}/${selected.id}/members/${m.id}`, undefined, "DELETE")}>{t("remove")}</button>}
          {orderId && !["completed", "cancelled"].includes(selected.status) && <button style={styles.secondaryButton} onClick={() => setMemberDraft({ ...m })}>{t("editParticipation")}</button>}
        </>}
      </li>)}</ul>
      {can("manage_members") && (!orderId ? selected.members_editable : !["completed", "cancelled"].includes(selected.status)) && <form style={{ display: "flex", gap: 8, flexWrap: "wrap" }} onSubmit={async e => { e.preventDefault(); if (await mutate(`${orderId ? "runs" : "shift-rosters"}/${selected.id}/members${memberDraft.id ? `/${memberDraft.id}` : ""}`, memberBody(memberDraft), memberDraft.id ? "PUT" : "POST")) setMemberDraft(emptyDraft); }}>
        {memberFields(memberDraft, setMemberDraft, Boolean(memberDraft.id))}
        {runStarted && <><label>{t("joinedAt")}<input type="datetime-local" value={toLocalInput(memberDraft.started_at)} onChange={e => setMemberDraft({ ...memberDraft, started_at: e.target.value ? new Date(e.target.value).toISOString() : null })} /></label><label>{t("leftAt")}<input type="datetime-local" value={toLocalInput(memberDraft.ended_at)} onChange={e => setMemberDraft({ ...memberDraft, ended_at: e.target.value ? new Date(e.target.value).toISOString() : null })} /></label></>}
        <button style={styles.secondaryButton} disabled={busy}>{t("saveMember")}</button>
        {memberDraft.id && <button style={styles.secondaryButton} type="button" onClick={() => setMemberDraft(emptyDraft)}>{t("newMember")}</button>}
      </form>}
      {!orderId && can("update") && selected.status === "active" && <div style={{ marginTop: 16 }}>
        {can("manage_members") && <button style={styles.secondaryButton} onClick={() => openForm(selected)}>{t("createReplacement")}</button>}
        <label>{t("closeOn")}<input type="date" value={closeDate} onChange={e => setCloseDate(e.target.value)} /></label><button style={styles.secondaryButton} disabled={busy || !closeDate} onClick={() => mutate(`shift-rosters/${selected.id}/close`, { effective_to: closeDate })}>{t("closePeriod")}</button>
      </div>}
      {orderId && <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
        {selected.status === "planned" && selected.shift_roster_id && can("manage_members") && <button style={styles.secondaryButton} disabled={busy} onClick={() => mutate(`runs/${selected.id}/load-roster-members`)}>{t("loadRosterMembers")}</button>}
        {runActions.filter(([, permission, states]) => can(permission) && states.includes(selected.status)).map(([action]) => <button style={styles.secondaryButton} key={action} disabled={busy} onClick={() => mutate(`runs/${selected.id}/${action}`)}>{t(`actions.${action}`)}</button>)}
      </div>}
    </section>}
  </section>;
}

function TeamList({ members, empty, lead }: { members: Member[]; empty: string; lead: string }) {
  if (!members.length) return <span style={{ color: "var(--text-muted)" }}>{empty}</span>;
  return <ul style={{ margin: 0, paddingInlineStart: 18 }}>{members.map(m => <li key={m.id ?? m.workforce_member_id}>{m.workforce_name ?? m.employee_code}{m.is_shift_lead && ` ${lead}`}</li>)}</ul>;
}
