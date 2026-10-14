"use client";
/**
 * The organization's audit trail (ORG-AUDIT-002): who changed what in its administration — users, roles, permissions,
 * settings, delegations, announcements — when, and the values before and after. Read only; one server page at a time.
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type CSSProperties } from "react";
import { useLocale, useTranslations } from "next-intl";

import { AccessDeniedMessage } from "@/components/AccessDeniedMessage";
import { PageFrame } from "@/components/layout/page-frame";
import { useNotify } from "@/components/notify/Notifications";
import { Pagination } from "@/components/pagination/Pagination";
import { usePermission } from "@/features/auth/permission-hooks";
import { DetailList, useDetailRows, useOperationText } from "@/features/logs/log-words";
import { useFormatter } from "@/hooks/useFormatter";
import { apiClient } from "@/lib/api-client";
import { downloadFile } from "@/lib/download";
import { useListQuery, type Page } from "@/lib/pagination";
import { sharedStyles } from "@/styles/shared-styles";

export type AuditEntry = {
  id: string; created_at: string; action: string; entity_type: string; entity_id: string | null; entity_name: string | null;
  actor_id: string | null; actor_name: string | null; details: unknown; permission_names: Record<string, { ar: string; en: string }>;
};

const READ = "foundation:audit:read";
const ENTITIES = ["user", "role", "role_assignment", "organization", "delegation", "announcement", "activity_log", "shipping_drivers", "shipping_vehicles",
  "shipping_carriers", "commercial_customer_contacts", "commercial_customer_sites", "procurement_supplier_contacts"] as const;
const CARD: CSSProperties = { background: "var(--surface)", border: "1px solid var(--border-strong)", borderRadius: 12, padding: 18 };
const cell: CSSProperties = { padding: "10px 12px", verticalAlign: "top", textAlign: "start" };

function useAuditWords() {
  const t = useTranslations("tenantAudit");
  const logs = useTranslations("logs");
  const operation = useOperationText(t);
  const entity = (key: string) => t.has(`entities.${key}`) ? t(`entities.${key}`) : logs("unknownEntity");
  return { t, logs, operation, entity };
}

export function AuditLogPage() {
  const allowed = usePermission(READ);
  const { t, logs, operation, entity } = useAuditWords();
  const notify = useNotify();
  const fmt = useFormatter();
  const locale = useLocale();
  const router = useRouter();
  const list = useListQuery(["entity_type", "action", "search", "from", "to"] as const);
  const f = list.filters;
  const [data, setData] = useState<Page<AuditEntry> | null>(null);
  const [error, setError] = useState(false);
  const [reload, setReload] = useState(0);

  const query = new URLSearchParams([["page", String(list.page)], ["page_size", String(list.pageSize)]]);
  if (f.entity_type) query.set("entity_type", f.entity_type);
  if (f.action) query.set("action", f.action);
  if (f.search) query.set("search", f.search);
  if (f.from) query.set("date_from", new Date(`${f.from}T00:00:00`).toISOString());
  if (f.to) query.set("date_to", new Date(`${f.to}T23:59:59`).toISOString());
  const qs = query.toString();

  useEffect(() => {
    if (!allowed) return;
    let live = true;
    setError(false);
    apiClient<Page<AuditEntry>>(`/admin/audit-log?${qs}`).then((d) => { if (live) setData(d); }).catch(() => { if (live) setError(true); });
    return () => { live = false; };
  }, [allowed, qs, reload]);

  if (!allowed) return <AccessDeniedMessage />;
  const actions = Object.keys((t.raw("actions") as Record<string, Record<string, string>>) ?? {})
    .flatMap((group) => Object.keys((t.raw(`actions.${group}`) as Record<string, string>) ?? {}).map((verb) => `${group}.${verb}`))
    .filter((code) => !f.entity_type || code.startsWith(`${f.entity_type}.`));
  async function exportCsv() {
    const q = new URLSearchParams(qs);
    q.delete("page"); q.delete("page_size"); q.set("locale", locale);
    try { await downloadFile(`/admin/audit-log/export?${q}`, "organization-audit.csv"); } catch { notify.error(t("error")); }
  }

  return <PageFrame section={t("section")} title={t("title")} subtitle={t("subtitle")}
    action={<button type="button" style={sharedStyles.secondaryButton} onClick={() => void exportCsv()}>{t("export")}</button>}>
    <section style={{ ...CARD, display: "flex", flexWrap: "wrap", gap: 10, marginBottom: 14 }}>
      <input style={{ ...sharedStyles.input, flex: "1 1 220px" }} aria-label={t("search")} placeholder={t("searchPlaceholder")} value={f.search}
        onChange={(e) => list.setFilter("search", e.target.value)} />
      <select style={{ ...sharedStyles.input, flex: "0 1 200px" }} aria-label={t("allEntities")} value={f.entity_type}
        onChange={(e) => list.setFilters({ entity_type: e.target.value, action: "" })}>
        <option value="">{t("allEntities")}</option>
        {ENTITIES.map((k) => <option key={k} value={k}>{entity(k)}</option>)}
      </select>
      <select style={{ ...sharedStyles.input, flex: "0 1 240px" }} aria-label={t("allActions")} value={f.action} onChange={(e) => list.setFilter("action", e.target.value)}>
        <option value="">{t("allActions")}</option>
        {actions.map((code) => <option key={code} value={code}>{operation(code)}</option>)}
      </select>
      <label style={{ display: "flex", alignItems: "center", gap: 6 }}>{logs("dateFrom")}
        <input style={sharedStyles.input} type="date" value={f.from} onChange={(e) => list.setFilter("from", e.target.value)} /></label>
      <label style={{ display: "flex", alignItems: "center", gap: 6 }}>{logs("dateTo")}
        <input style={sharedStyles.input} type="date" value={f.to} onChange={(e) => list.setFilter("to", e.target.value)} /></label>
      {(f.search || f.entity_type || f.action || f.from || f.to) &&
        <button type="button" style={sharedStyles.secondaryButton} onClick={list.clearFilters}>{logs("clear")}</button>}
    </section>
    <section style={CARD}>
      {error ? <div role="alert" style={sharedStyles.error}>{t("error")} <button type="button" style={sharedStyles.secondaryButton} onClick={() => setReload((n) => n + 1)}>{t("retry")}</button></div>
        : !data ? <p>{t("loading")}</p>
        : <>
          <p style={{ margin: "0 0 10px", color: "var(--text-muted)" }}>{logs("count", { count: data.total })}</p>
          {!data.items.length ? <p>{t("empty")}</p> : <div style={{ overflowX: "auto" }}><table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead><tr>{(["time", "what", "on", "by"] as const).map((k) =>
              <th key={k} style={{ ...cell, color: "var(--text-muted)", fontSize: 13 }}>{logs(`columns.${k}`)}</th>)}</tr></thead>
            <tbody>{data.items.map((e) => <tr key={e.id} style={{ borderTop: "1px solid var(--border)", cursor: "pointer" }}
              onClick={() => router.push(`/admin/audit-log/${e.id}`)}>
              <td style={{ ...cell, whiteSpace: "nowrap" }}>{fmt.dateTime(e.created_at)}</td>
              <td style={cell}><Link href={`/admin/audit-log/${e.id}`} style={{ color: "var(--accent-strong)", fontWeight: 700 }}>{operation(e.action)}</Link></td>
              <td style={cell}>{e.entity_name || entity(e.entity_type)}<div style={{ color: "var(--text-muted)", fontSize: 12 }}>{entity(e.entity_type)}</div></td>
              <td style={cell}>{e.actor_name || logs("system")}</td>
            </tr>)}</tbody>
          </table></div>}
          {data.total > 0 && <Pagination page={data.page} pageSize={data.page_size} total={data.total} pages={data.pages}
            onPage={list.setPage} onPageSize={list.setPageSize} />}
        </>}
    </section>
  </PageFrame>;
}

export function AuditLogDetailPage({ id }: { id: string }) {
  const allowed = usePermission(READ);
  const { t, logs, operation, entity } = useAuditWords();
  const rows = useDetailRows();
  const fmt = useFormatter();
  const [entry, setEntry] = useState<AuditEntry | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => { if (allowed) apiClient<AuditEntry>(`/admin/audit-log/${id}`).then(setEntry).catch(() => setError(true)); }, [allowed, id]);
  if (!allowed) return <AccessDeniedMessage />;
  return <PageFrame section={t("section")} title={entry ? operation(entry.action) : t("detailTitle")}
    action={<Link href="/admin/audit-log" style={sharedStyles.secondaryButton}>{t("back")}</Link>}>
    {error ? <div role="alert" style={sharedStyles.error}>{t("error")}</div> : !entry ? <p>{t("loading")}</p> : <div style={{ display: "grid", gap: 16 }}>
      <section style={CARD}>
        <DetailList rows={[
          { label: t("detail.action"), value: operation(entry.action) },
          { label: t("detail.time"), value: fmt.dateTime(entry.created_at) },
          { label: t("detail.actor"), value: entry.actor_name || logs("system") },
          { label: t("detail.entity"), value: entity(entry.entity_type) },
          ...(entry.entity_name ? [{ label: t("detail.target"), value: entry.entity_name }] : []),
        ]} />
      </section>
      <section style={CARD}>
        <h2 style={{ margin: "0 0 12px", fontSize: 18 }}>{t("changes")}</h2>
        <DetailList rows={rows(entry.details, entry.permission_names)} />
      </section>
    </div>}
  </PageFrame>;
}
