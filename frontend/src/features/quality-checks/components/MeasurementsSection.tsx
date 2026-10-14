"use client";

import {UnitLabel} from "@/components/UnitLabel";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { usePermission } from "@/features/auth/permission-hooks";
import s from "@/features/production-demands/demands.module.css";
import { Q } from "@/lib/quality-permissions";
import { applyPlan, getPlanCandidates, recordMeasurement } from "../api/quality-checks-api";
import type { Measurement, PlanCandidate, QualityCheckData } from "../types";
import { qualityErrorMessage } from "./quality-errors";

const VERDICT_CLASS = { pass: s.green, fail: s.urgent, recorded: s.blue, pending: "" } as const;

// One reading as typed → a plain decimal: Arabic-Indic or Persian digits, the Arabic decimal separator (٫) and a decimal comma.
export function normalizeReading(text: string) {
  return text.trim()
    .replace(/[\u0660-\u0669]/g, d => String(d.charCodeAt(0) - 0x0660))
    .replace(/[\u06F0-\u06F9]/g, d => String(d.charCodeAt(0) - 0x06F0))
    .replace(/[\u066B,]/g, ".");
}

const READING = /^-?\d+(\.\d+)?$/;
export const isReading = (text: string) => READING.test(normalizeReading(text));

// Several readings pasted in one text: spaces, Arabic commas or semicolons between them.
export function splitReadings(text: string) {
  return text.split(/[\s،؛;]+/).map(normalizeReading).filter(Boolean);
}

type Draft = { readings: string[]; result: string; observation: string };
const draftOf = (m: Measurement): Draft => ({ readings: [...(m.readings ?? [])], result: m.attribute_result ?? "", observation: m.observation ?? "" });
const filled = (d: Draft) => d.readings.map(r => r.trim()).filter(Boolean);

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
  const [candidates, setCandidates] = useState<PlanCandidate[] | null>(null);
  const [choice, setChoice] = useState("");
  const [lotValues, setLotValues] = useState<Record<string, string>>({});
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

  const chosen = candidates?.find(c => c.id === choice) ?? null;
  const missing = chosen?.missing_keys ?? [];
  const valuesReady = missing.every(k => /^\d+(\.\d+)?$/.test((lotValues[k] ?? "").trim()));
  const matching = candidates?.filter(c => c.matches_product) ?? [];
  const others = candidates?.filter(c => !c.matches_product) ?? [];
  const option = (c: PlanCandidate) => <option key={c.id} value={c.id}>{c.code} — rev {c.revision} — {c.title}</option>;
  const keyLabel = (key: string) => (t.has(`keys.${key}`) ? t(`keys.${key}`) : key);

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
      : <>
        <div className={s.toolbar} style={{ marginBottom: 0 }}>
          <label className={s.field}>{t("chooseSpecification")}
            <select value={choice} disabled={busy} onChange={e => setChoice(e.target.value)}>
              {matching.length > 0 && <optgroup label={t("matchingGroup")}>{matching.map(option)}</optgroup>}
              {others.length > 0 && <optgroup label={t("otherGroup")}>{others.map(option)}</optgroup>}
            </select>
          </label>
          {missing.map(key => <label key={key} className={s.field}>{keyLabel(key)}
            <input required dir="ltr" inputMode="decimal" style={{ width: 120 }} value={lotValues[key] ?? ""} disabled={busy}
              onChange={e => setLotValues(old => ({ ...old, [key]: e.target.value }))} />
          </label>)}
          <button type="button" className={`${s.button} ${s.primary}`} disabled={busy || !choice || !valuesReady}
            onClick={() => void run(() => applyPlan(check.id, choice, Object.fromEntries(missing.map(k => [k, lotValues[k].trim()]))))}>{t("applyPlan")}</button>
        </div>
        {chosen && !chosen.matches_product && <p className={s.muted} style={{ margin: "8px 0 0" }}>{t("otherProductHint", { product: chosen.product_type })}</p>}
        {missing.length > 0 && <p className={s.muted} style={{ margin: "8px 0 0" }}>{t("missingValuesHint")}</p>}
      </>)}
    {planned && <MeasurementTable check={check} ar={ar} editable={editable} busy={busy} setBusy={setBusy} setError={setError} onChange={onChange}
      keyLabel={keyLabel} counts={counts} />}
  </section>;
}

function MeasurementTable({ check, ar, editable, busy, setBusy, setError, onChange, keyLabel, counts }: {
  check: QualityCheckData; ar: boolean; editable: boolean; busy: boolean; setBusy: (v: boolean) => void; setError: (v: string) => void;
  onChange: (check: QualityCheckData) => void; keyLabel: (key: string) => string; counts: Record<string, number>;
}) {
  const t = useTranslations("quality.measurements");
  const errors = useTranslations("quality.errors");
  const [drafts, setDrafts] = useState<Record<string, Draft>>(() => Object.fromEntries(check.measurements.map(m => [m.id, draftOf(m)])));
  const [saved, setSaved] = useState("");

  const changed = check.measurements.filter(m => {
    const before = draftOf(m), d = drafts[m.id] ?? before;
    return m.kind === "numeric"
      ? JSON.stringify(filled(d).map(normalizeReading)) !== JSON.stringify(filled(before)) || d.observation.trim() !== before.observation
      : d.result !== before.result || d.observation.trim() !== before.observation;
  });
  const invalid = check.measurements.some(m => m.kind === "numeric" && filled(drafts[m.id] ?? draftOf(m)).some(r => !isReading(r)));
  const set = (id: string, patch: Partial<Draft>) => { setSaved(""); setDrafts(old => ({ ...old, [id]: { ...(old[id] ?? draftOf(check.measurements.find(m => m.id === id)!)), ...patch } })); };

  async function saveAll() {
    setBusy(true); setError(""); setSaved("");
    let latest: QualityCheckData | null = null;
    try {
      for (const m of changed) {
        const d = drafts[m.id] ?? draftOf(m);
        latest = await recordMeasurement(check.id, m.id, m.kind === "numeric"
          ? { readings: filled(d).map(normalizeReading), observation: d.observation.trim() || null }
          : { attribute_result: (d.result || null) as "conforming" | "nonconforming" | null, observation: d.observation.trim() || null });
      }
      setSaved(t("savedCount", { count: String(changed.length) }));
    } catch (e) {
      setError(qualityErrorMessage(e, errors));
    } finally {
      if (latest) onChange(latest);
      setBusy(false);
    }
  }

  return <>
    {check.lot_values && <p className={s.muted}>{t("lotValues", { values: Object.entries(check.lot_values).map(([k, v]) => `${keyLabel(k)}: ${v}`).join(" · ") })}</p>}
    <p className={s.muted}>{t("summary", { pass: String(counts.pass), fail: String(counts.fail), pending: String(counts.pending) })}</p>
    <div className={s.tableWrap}><table className={s.table} aria-label={t("title")}>
      <thead><tr>{["parameter", "unit", "target", "acceptance", "result", "stats", "verdict"].map(c => <th key={c}>{t(`columns.${c}`)}</th>)}</tr></thead>
      <tbody>{check.measurements.map(m => <MeasurementRow key={m.id} m={m} draft={drafts[m.id] ?? draftOf(m)} ar={ar} editable={editable} busy={busy}
        onDraft={patch => set(m.id, patch)} />)}</tbody>
    </table></div>
    {editable && <div className={s.actions} style={{ marginTop: 12 }}>
      <button type="button" className={`${s.button} ${s.primary}`} disabled={busy || invalid || changed.length === 0} onClick={() => void saveAll()}>
        {changed.length ? t("saveChanged", { count: String(changed.length) }) : t("saveAll")}</button>
      {invalid && <span role="alert" className={s.error} style={{ padding: "6px 10px" }}>{t("invalidReading")}</span>}
      {saved && <span role="status" className={s.muted}>{saved}</span>}
    </div>}
    <p className={s.muted} style={{ marginBottom: 0 }}>{t("rule")}</p>
  </>;
}

function MeasurementRow({ m, draft, ar, editable, busy, onDraft }: { m: Measurement; draft: Draft; ar: boolean; editable: boolean; busy: boolean;
  onDraft: (patch: Partial<Draft>) => void }) {
  const t = useTranslations("quality.measurements");
  const numeric = m.kind === "numeric";
  const name = ar ? m.name_ar : m.name_en;
  const number = (v: string | null) => (v === null ? "—" : String(Number(v)));
  // One box per required reading (more can be added); a pasted list is spread over the boxes.
  const boxes = Math.max(m.readings_required, draft.readings.length, 1);
  const values = Array.from({ length: boxes }, (_, i) => draft.readings[i] ?? "");
  const count = filled(draft).length;
  const setReading = (index: number, text: string) => {
    const parts = splitReadings(text);
    const next = [...values];
    if (parts.length > 1) next.splice(index, parts.length, ...parts); else next[index] = text;
    onDraft({ readings: next });
  };

  return <tr>
    <td><strong>{name}</strong>{m.method && <div className={s.muted}>{m.method}</div>}</td>
    <td>{m.unit ? <UnitLabel value={m.unit}/> : "—"}</td>
    <td>{numeric ? number(m.target) : (m.requirement ?? "—")}</td>
    <td><bdi>{numeric ? limitsText(m) : (m.acceptance ?? "—")}</bdi></td>
    <td>{editable ? (numeric
      ? <div>
        <span className={s.actions} style={{ gap: 4 }}>
          {values.map((value, i) => <input key={i} aria-label={t("readingFor", { name, n: String(i + 1) })} value={value} disabled={busy} dir="ltr"
            inputMode="decimal" style={{ width: 62, padding: 6, borderColor: value.trim() && !isReading(value) ? "var(--danger)" : undefined }}
            onChange={e => setReading(i, e.target.value)} />)}
          {boxes < 50 && <button type="button" className={s.button} style={{ padding: "4px 9px" }} disabled={busy} aria-label={t("addReading", { name })}
            onClick={() => onDraft({ readings: [...values, ""] })}>+</button>}
        </span>
        <div className={s.muted} style={{ color: count < m.readings_required ? "var(--warning)" : undefined }}>
          {t("readingsProgress", { count: String(count), required: String(m.readings_required) })}</div>
      </div>
      : <span className={s.actions}>
        <select aria-label={t("resultFor", { name })} value={draft.result} disabled={busy} onChange={e => onDraft({ result: e.target.value })}>
          <option value="">—</option>
          <option value="conforming">{t("conforming")}</option>
          <option value="nonconforming">{t("nonconforming")}</option>
        </select>
        <input aria-label={t("observationFor", { name })} value={draft.observation} disabled={busy} maxLength={255} placeholder={t("observation")}
          onChange={e => onDraft({ observation: e.target.value })} style={{ width: 150 }} />
      </span>)
      : numeric ? <bdi dir="ltr">{(m.readings ?? []).join(" · ") || "—"}</bdi>
        : <>{m.attribute_result ? t(m.attribute_result) : "—"}{m.observation && <div className={s.muted}>{m.observation}</div>}</>}</td>
    <td>{numeric && m.reading_count > 0 ? <bdi>{t("stats", { n: String(m.reading_count), mean: number(m.mean), min: number(m.minimum), max: number(m.maximum) })}</bdi> : "—"}</td>
    <td><span className={`${s.badge} ${VERDICT_CLASS[m.status]}`}>{t(`verdict.${m.status}`)}</span>
      {m.status === "pending" && numeric && m.reading_count > 0 && <div className={s.muted}>{t("needsMore", { count: String(m.readings_required - m.reading_count) })}</div>}</td>
  </tr>;
}
