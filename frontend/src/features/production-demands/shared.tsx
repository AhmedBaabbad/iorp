"use client";
import { useTranslations } from "next-intl";
import { ApiClientError } from "@/lib/api-client";
import type { DemandPriority, DemandStatus, Item } from "./api";
import styles from "./demands.module.css";

export const priorities: DemandPriority[] = ["low", "normal", "high", "urgent"];
export const statuses: DemandStatus[] = ["draft", "ready_for_planning", "partially_planned", "planned", "cancelled"];
export const transitions: Record<DemandStatus, DemandStatus[]> = { draft: ["ready_for_planning", "cancelled"], ready_for_planning: ["draft", "cancelled"], partially_planned: [], planned: [], cancelled: ["draft"] };
export function today() { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; }
export function errorKey(error: unknown) {
  if (error instanceof ApiClientError) {
    const details = error.details as { detail?: { code?: string } } | undefined;
    const code = details?.detail?.code;
    if (code) return code;
    if (error.status === 403) return "forbidden";
    if (error.status === 404) return "demand_not_found";
  }
  return "request_failed";
}
export function ErrorMessage({ code }: { code: string }) {
  const t = useTranslations("production.demands.errors");
  return code ? <p className={styles.error} role="alert">{t(t.has(code) ? code : "request_failed")}</p> : null;
}
export function Badge({ value, priority = false }: { value: DemandStatus | DemandPriority; priority?: boolean }) {
  const t = useTranslations("production.demands");
  const color = priority ? ({ urgent: styles.urgent, high: styles.high, normal: styles.blue, low: "" }[value as DemandPriority]) : ({ draft: "", ready_for_planning: styles.blue, partially_planned: styles.high, planned: styles.green, cancelled: styles.cancelled }[value as DemandStatus]);
  return <span className={`${styles.badge} ${color}`}>{t(`${priority ? "priorities" : "statuses"}.${value}`)}</span>;
}
export function Specs({ value }: { value: Item["target_spec_json"] }) {
  const t = useTranslations("production.planning");
  return <div className={styles.specs}>{Object.entries(value ?? {}).map(([key, val]) => <div key={key}><strong>{t.has(`specColumns.${key}`) ? t(`specColumns.${key}`) : key}</strong>{": "}{typeof val === "object" ? JSON.stringify(val) : String(val)}</div>)}</div>;
}
