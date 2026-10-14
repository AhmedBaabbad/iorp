"use client";
/**
 * The security log (who signed in, from where, failures, locks, password changes) and the activity log (what happened
 * in the daily work), for an organization and for the platform. Every entry reads as a sentence with the person's name;
 * its details open as labelled values (ORG-AUDIT-002). Read only, one server page at a time.
 */
import Link from "next/link";
import { Fragment, useEffect, useState, type CSSProperties } from "react";
import { useLocale, useTranslations } from "next-intl";

import { PageFrame } from "@/components/layout/page-frame";
import { Pagination } from "@/components/pagination/Pagination";
import { useAuth } from "@/features/auth";
import { useOptionalPlatformAuth } from "@/features/platform/platform-auth-context";
import { ActivityArchive } from "@/features/logs/ActivityArchive";
import { DetailList, useDetailRows, useEntityText, useOperationText } from "@/features/logs/log-words";
import { useFormatter } from "@/hooks/useFormatter";
import { apiClient } from "@/lib/api-client";
import { DEFAULT_PAGE_SIZE, type Page } from "@/lib/pagination";
import { sharedStyles } from "@/styles/shared-styles";
import css from "@/features/platform/platform-audit.module.css";

type Entry = {
  id: string; created_at: string; event_type?: string; action?: string; actor_name?: string | null; actor_email?: string | null;
  entity_type?: string | null; entity_id?: string | null; entity_name?: string | null; ip_address?: string | null; user_agent?: string | null; details?: unknown;
  occurrences?: number; last_seen_at?: string | null;
};
type Props = { scope: "platform" | "tenant"; kind: "security" | "activity"; namespace: "platformSecurity" | "platformActivity" | "tenantSecurity" | "tenantActivity"; permission: string };

const CARD: CSSProperties = { background: "var(--surface)", border: "1px solid var(--border-strong)", borderRadius: 12, padding: 18 };
// The organization's security log opens on what matters; routine sign-ins are shown on request (ORG-AUDIT-003).
const IMPORTANT = "__important", ALL = "";
const AREAS = ["commercial", "production", "quality", "shipping", "procurement", "masterdata", "workforce"] as const;
// Where a record of the activity log opens (its own page), when it has one.
const PAGES: Record<string, string> = {
  customer: "/customers", purchase_order: "/purchase-orders", supplier: "/suppliers", goods_receipt: "/goods-receipts",
  production_order: "/production-orders", quality_check: "/quality-checks", quality_rejection: "/quality-rejections",
  quality_certificate: "/quality-certificates", quality_specification: "/quality-specifications", ncr_report: "/non-conformance-reports",
  shipment: "/shipments", shipment_return: "/shipment-returns", work_center: "/work-centers",
};
const cell: CSSProperties = { padding: "10px 12px", verticalAlign: "top", textAlign: "start" };

export function SeparatedLogPage(props: Props) {
  const t = useTranslations(props.namespace);
  const logs = useTranslations("logs");
  const operation = useOperationText(t, props.kind === "security" ? "events" : "actions");
  const rows = useDetailRows();
  const entityText = useEntityText();
  const fmt = useFormatter();
  const locale = useLocale();
  const tenant = useAuth();
  const platform = useOptionalPlatformAuth();
  const allowed = props.scope === "platform" ? !!platform?.account?.permissions?.includes(props.permission) : tenant.hasPermission(props.permission);
  const base = `/${props.scope === "platform" ? "platform" : "admin"}/${props.kind}-log`;
  const filterKey = props.kind === "security" ? "event_type" : "action";

  const [page, setPage] = useState(1), [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const importantFirst = props.scope === "tenant" && props.kind === "security";
  const [kind, setKind] = useState(importantFirst ? IMPORTANT : ALL), [from, setFrom] = useState(""), [to, setTo] = useState("");
  const [kinds, setKinds] = useState<string[]>([]);
  const businessLog = props.scope === "tenant" && props.kind === "activity";
  const canArchive = businessLog && tenant.hasPermission("foundation:activity_log:archive");
  const [person, setPerson] = useState(""), [area, setArea] = useState("");
  const [people, setPeople] = useState<{ id: string; name: string }[]>([]);
  const [data, setData] = useState<Page<Entry> | null>(null);
  const [error, setError] = useState(false);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    if (allowed && props.scope === "tenant") apiClient<string[]>(`${base}/kinds`).then(setKinds).catch(() => setKinds([]));
    if (allowed && businessLog) apiClient<{ id: string; name: string }[]>(`${base}/actors`).then(setPeople).catch(() => setPeople([]));
  }, [allowed, base, props.scope, businessLog]);
  useEffect(() => {
    if (!allowed) return;
    let live = true;
    const q = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (kind === IMPORTANT) q.set("important", "true");
    else if (kind) q.set(filterKey, kind);
    if (person) q.set("actor_id", person);
    if (area) q.set("area", area);
    if (from) q.set("date_from", new Date(`${from}T00:00:00`).toISOString());
    if (to) q.set("date_to", new Date(`${to}T23:59:59`).toISOString());
    setError(false);
    apiClient<Page<Entry>>(`${base}?${q}`).then((d) => { if (live) setData(d); }).catch(() => { if (live) setError(true); });
    return () => { live = false; };
  }, [allowed, base, filterKey, page, pageSize, kind, person, area, from, to]);

  const body = <>
    <section style={{ ...CARD, display: "flex", flexWrap: "wrap", gap: 10, marginBottom: 14 }}>
      {kinds.length > 0 && <select style={{ ...sharedStyles.input, flex: "1 1 240px" }} aria-label={logs("kind")} value={kind}
        onChange={(e) => { setKind(e.target.value); setPage(1); }}>
        {importantFirst && <option value={IMPORTANT}>{logs("importantOnly")}</option>}
        <option value={ALL}>{importantFirst ? logs("allEvents") : logs("allKinds")}</option>
        {kinds.map((k) => ({ k, label: operation(k) })).sort((a, b) => a.label.localeCompare(b.label, locale))
          .map(({ k, label }) => <option key={k} value={k}>{label}</option>)}
      </select>}
      {businessLog && <select style={{ ...sharedStyles.input, flex: "0 1 200px" }} aria-label={t("area")} value={area}
        onChange={(e) => { setArea(e.target.value); setPage(1); }}>
        <option value="">{t("allAreas")}</option>
        {AREAS.map((a) => <option key={a} value={a}>{t(`areas.${a}`)}</option>)}
      </select>}
      {businessLog && people.length > 0 && <select style={{ ...sharedStyles.input, flex: "0 1 200px" }} aria-label={t("person")} value={person}
        onChange={(e) => { setPerson(e.target.value); setPage(1); }}>
        <option value="">{t("allPeople")}</option>
        {people.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
      </select>}
      <label style={{ display: "flex", alignItems: "center", gap: 6 }}>{logs("dateFrom")}
        <input style={sharedStyles.input} type="date" value={from} onChange={(e) => { setFrom(e.target.value); setPage(1); }} /></label>
      <label style={{ display: "flex", alignItems: "center", gap: 6 }}>{logs("dateTo")}
        <input style={sharedStyles.input} type="date" value={to} onChange={(e) => { setTo(e.target.value); setPage(1); }} /></label>
      {(kind !== (importantFirst ? IMPORTANT : ALL) || person || area || from || to) && <button type="button" style={sharedStyles.secondaryButton}
        onClick={() => { setKind(importantFirst ? IMPORTANT : ALL); setPerson(""); setArea(""); setFrom(""); setTo(""); setPage(1); }}>{logs("clear")}</button>}
    </section>
    <section style={CARD}>
      {error ? <div role="alert" style={sharedStyles.error}>{t("error")}</div> : !data ? <p>{t("loading")}</p> : <>
        <p style={{ margin: "0 0 10px", color: "var(--text-muted)" }}>{logs("count", { count: data.total })}</p>
        {!data.items.length ? <p>{t("empty")}</p> : <div style={{ overflowX: "auto" }}><table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead><tr>{(props.kind === "security" ? ["time", "what", "by", "from"] as const : ["time", "what", "on", "by"] as const).map((k) =>
            <th key={k} style={{ ...cell, color: "var(--text-muted)", fontSize: 13 }}>{logs(`columns.${k}`)}</th>)}<th style={cell} /></tr></thead>
          <tbody>{data.items.map((e) => {
            const shown = open === e.id;
            const by = e.actor_name || e.actor_email || logs("system");
            return <Fragment key={e.id}>
              <tr style={{ borderTop: "1px solid var(--border)" }}>
                <td style={{ ...cell, whiteSpace: "nowrap" }}>{fmt.dateTime(e.created_at)}</td>
                <td style={{ ...cell, fontWeight: 700 }}>{operation(e.event_type ?? e.action, e.details)}
                  {(e.occurrences ?? 1) > 1 && e.last_seen_at && <div style={{ fontWeight: 400, color: "var(--text-muted)", fontSize: 12 }}>
                    {logs("repeated", { count: e.occurrences ?? 1, time: fmt.dateTime(e.last_seen_at) })}</div>}</td>
                {props.kind === "security"
                  ? <><td style={cell}>{by}</td><td style={cell}>{e.ip_address || "—"}</td></>
                  : <><td style={cell}>{(() => {
                      const name = e.entity_name || entityText(e.entity_type);
                      const page = e.entity_type && e.entity_id ? PAGES[e.entity_type] : undefined;
                      return page ? <Link href={`${page}/${e.entity_id}`} style={{ color: "var(--accent-strong)", fontWeight: 700 }}>{name}</Link> : name;
                    })()}</td><td style={cell}>{by}</td></>}
                <td style={cell}><button type="button" className={css.back} aria-expanded={shown} onClick={() => setOpen(shown ? null : e.id)}>
                  {shown ? logs("hideDetails") : logs("showDetails")}</button></td>
              </tr>
              {shown && <tr><td colSpan={5} style={{ ...cell, background: "var(--surface-muted)" }}>
                <DetailList rows={[...rows(e.details), ...(e.user_agent ? [{ label: logs("fields.user_agent"), value: e.user_agent }] : [])]} />
              </td></tr>}
            </Fragment>;
          })}</tbody>
        </table></div>}
        {data.total > 0 && <Pagination page={data.page} pageSize={data.page_size} total={data.total} pages={data.pages}
          onPage={setPage} onPageSize={(size) => { setPageSize(size); setPage(1); }} />}
      </>}
    </section>
  </>;

  if (props.scope === "tenant") return <PageFrame title={t("title")} subtitle={t("subtitle")}>
    {allowed ? <>{body}{canArchive && <ActivityArchive />}</> : <div className={css.error}>{t("accessDenied")}</div>}</PageFrame>;
  return <main className={css.page} dir={locale === "ar" ? "rtl" : "ltr"}><div className={css.shell}>
    <header className={css.header}><div><h1 className={css.title}>{t("title")}</h1><p className={css.subtitle}>{t("subtitle")}</p></div></header>
    {allowed ? body : <div className={css.error}>{t("accessDenied")}</div>}
  </div></main>;
}
