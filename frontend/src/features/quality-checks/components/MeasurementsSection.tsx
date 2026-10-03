"use client";

import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { usePermission } from "@/features/auth/permission-hooks";
import s from "@/features/production-demands/demands.module.css";
import { Q } from "@/lib/quality-permissions";
import { applyPlan, getPlanCandidates, recordMeasurement } from "../api/quality-checks-api";
import type { Measurement, QualityCheckData } from "../types";
import { qualityErrorMessage } from "./quality-errors";

const VERDICT_CLASS = { pass: s.green, fail: s.urgent, recorded: s.blue, pending: "" } as const;

// "a, b c" or Arabic separators → readings as typed.
export function splitReadings(text: string) {
  return text.split(/[\s,،؛;]+/).map(v => v.trim()).filter(Boolean);
}

export function limitsText(m: Pick<Measurement, "lower_limit" | "upper_limit">) {
  const trim = (v: string) => String(Number(v));
  if (m.lower_limit !== null && m.upper_limit !== null) return `${trim(m.lower_limit)} – ${trim(m.upper_limit)}`;
  if (m.lower_limit !== null) return `≥ ${trim(m.lower_limit)}`;
  if (m.upper_limit !== null) return `≤ ${trim(m.upper_limit)}`;
  return "—";
}

// "نتائج القياس": the plan copied from the product's specification and the inspector's readings; verdicts come from the server.
export function MeasurementsSection({ check, onChange }: { check: QualityCheckData; onChange: (check: QualityCheckData) => void }) {
  const t = useTranslations("quality.measurements");
  const errors = useTranslations("quality.errors");
  const ar = useLocale() === "ar";
  const canReadSpecs = usePermission(Q.SPECS_READ);
  const editable = check.actions.includes("measure");
  const [candidates, setCandidates] = useState<{ id: string; code: string; revision: number; title: string }[] | null>(null);
  const [choice, setChoice] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const planned = check.measurements.length > 0;
  useEffect(() => {
    if (planned || !editable) return;
    let active = true;
    getPlanCandidates(check.id).then(list => { if (active) { setCandidates(list); setChoice(list[0]?.id ?? ""); } })
      .catch(() => { if (active) setCandidates([]); });
    return () => { active = false; };
  }, [check.id, planned, editable]);

  async function run(action: () => Promise<QualityCheckData>) {
    setBusy(true); setError("");
    try { onChange(await action()); } catch (e) { setError(qualityErrorMessage(e, errors)); } finally { setBusy(false); }
  }

  const counts = { pass: 0, fail: 0, pending: 0, recorded: 0 };
  check.measurements.forEach(m => { counts[m.status] += 1; });

  return <section className={s.panel} aria-label={t("title")}>
    <div className={s.actions} style={{ justifyContent: "space-between" }}>
      <h2 style={{ margin: 0 }}>{t("title")}</h2>
      {check.specification_code && <span className={s.muted}>{t("reference", { code: check.specification_code, revision: String(check.specification_revision) })}</span>}
    </div>
    {error && <p role="alert" className={s.error}>{error}</p>}
    {!planned && !editable && <p className={s.muted} style={{ marginBottom: 0 }}>{t("noPlan")}</p>}
    {!planned && editable && candidates !== null && (candidates.length === 0
      ? <p className={s.muted} style={{ marginBottom: 0 }}>{t("noSpecification")} {canReadSpecs && <Link href="/quality-specifications">{t("openSpecifications")}</Link>}</p>
      : <div className={s.toolbar} style={{ marginBottom: 0 }}>
        <label className={s.field}>{t("chooseSpecification")}
          <select value={choice} disabled={busy} onChange={e => setChoice(e.target.value)}>
            {candidates.map(c => <option key={c.id} value={c.id}>{c.code} — rev {c.revision} — {c.title}</option>)}
          </select>
        </label>
        <button type="button" className={`${s.button} ${s.primary}`} disabled={busy || !choice} onClick={() => void run(() => applyPlan(check.id, choice))}>{t("applyPlan")}</button>
      </div>)}
    {planned && <>
      <p className={s.muted}>{t("summary", { pass: String(counts.pass), fail: String(counts.fail), pending: String(counts.pending) })}</p>
      <div className={s.tableWrap}><table className={s.table} aria-label={t("title")}>
        <thead><tr>{["parameter", "unit", "target", "acceptance", "result", "stats", "verdict"].map(c => <th key={c}>{t(`columns.${c}`)}</th>)}</tr></thead>
        <tbody>{check.measurements.map(m => <MeasurementRow key={m.id} m={m} ar={ar} editable={editable} busy={busy}
          onSave={body => void run(() => recordMeasurement(check.id, m.id, body))} />)}</tbody>
      </table></div>
      <p className={s.muted} style={{ marginBottom: 0 }}>{t("rule")}</p>
    </>}
  </section>;
}

function MeasurementRow({ m, ar, editable, busy, onSave }: { m: Measurement; ar: boolean; editable: boolean; busy: boolean;
  onSave: (body: { readings?: string[]; attribute_result?: "conforming" | "nonconforming" | null; observation?: string | null }) => void }) {
  const t = useTranslations("quality.measurements");
  const [readings, setReadings] = useState((m.readings ?? []).join(" "));
  const [result, setResult] = useState(m.attribute_result ?? "");
  const [observation, setObservation] = useState(m.observation ?? "");
  const numeric = m.kind === "numeric";
  const name = ar ? m.name_ar : m.name_en;
  const number = (v: string | null) => (v === null ? "—" : String(Number(v)));

  return <tr>
    <td><strong>{name}</strong>{m.method && <div className={s.muted}>{m.method}</div>}</td>
    <td>{m.unit ?? "—"}</td>
    <td>{numeric ? number(m.target) : (m.requirement ?? "—")}</td>
    <td><bdi>{numeric ? limitsText(m) : (m.acceptance ?? "—")}</bdi>{numeric && m.readings_required > 1 && <div className={s.muted}>{t("readingsRequired", { count: String(m.readings_required) })}</div>}</td>
    <td>{editable ? (numeric
      ? <span className={s.actions}>
        <input aria-label={t("readingsFor", { name })} value={readings} disabled={busy} inputMode="decimal" dir="ltr" placeholder={t("readingsPlaceholder")}
          onChange={e => setReadings(e.target.value)} style={{ width: 170 }} />
        <button type="button" className={s.button} disabled={busy} onClick={() => onSave({ readings: splitReadings(readings), observation: observation || null })}>{t("save")}</button>
      </span>
      : <span className={s.actions}>
        <select aria-label={t("resultFor", { name })} value={result} disabled={busy} onChange={e => setResult(e.target.value)}>
          <option value="">—</option>
          <option value="conforming">{t("conforming")}</option>
          <option value="nonconforming">{t("nonconforming")}</option>
        </select>
        <input aria-label={t("observationFor", { name })} value={observation} disabled={busy} maxLength={255} placeholder={t("observation")}
          onChange={e => setObservation(e.target.value)} style={{ width: 150 }} />
        <button type="button" className={s.button} disabled={busy}
          onClick={() => onSave({ attribute_result: (result || null) as "conforming" | "nonconforming" | null, observation: observation || null })}>{t("save")}</button>
      </span>)
      : numeric ? <bdi dir="ltr">{(m.readings ?? []).join(" · ") || "—"}</bdi>
        : <>{m.attribute_result ? t(m.attribute_result) : "—"}{m.observation && <div className={s.muted}>{m.observation}</div>}</>}</td>
    <td>{numeric && m.reading_count > 0 ? <bdi>{t("stats", { n: String(m.reading_count), mean: number(m.mean), min: number(m.minimum), max: number(m.maximum) })}</bdi> : "—"}</td>
    <td><span className={`${s.badge} ${VERDICT_CLASS[m.status]}`}>{t(`verdict.${m.status}`)}</span></td>
  </tr>;
}
