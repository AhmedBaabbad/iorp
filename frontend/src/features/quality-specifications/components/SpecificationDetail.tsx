"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useState, type ReactNode } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import s from "@/features/production-demands/demands.module.css";
import { qualityErrorMessage } from "@/features/quality-checks/components/quality-errors";
import { useFormatter } from "@/hooks/useFormatter";
import { activateSpecification, getSpecification, reviseSpecification } from "../api";
import { limitsText, targetText } from "../spec-lines";
import type { Specification } from "../types";
import { SpecificationStatusBadge } from "./SpecificationStatusBadge";

function Item({ label, children }: { label: string; children: ReactNode }) {
  return <div><dt className={s.muted}>{label}</dt><dd style={{ margin: "4px 0 0", overflowWrap: "anywhere" }}>{children}</dd></div>;
}

export function SpecificationDetail({ specId }: { specId: string }) {
  const t = useTranslations("quality.specifications");
  const errors = useTranslations("quality.errors");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const ar = useLocale() === "ar";
  const router = useRouter();
  const [spec, setSpec] = useState<Specification | null>(null);
  const [loading, setLoading] = useState(true);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try { setSpec(await getSpecification(specId)); } catch (e) { setError(qualityErrorMessage(e, errors)); } finally { setLoading(false); }
  }, [specId, errors]);
  useEffect(() => { void load(); }, [load]);

  async function activate() {
    setBusy(true); setError("");
    try { setSpec(await activateSpecification(specId)); setConfirming(false); } catch (e) { setError(qualityErrorMessage(e, errors)); } finally { setBusy(false); }
  }
  async function revise() {
    setBusy(true); setError("");
    try { const draft = await reviseSpecification(specId); router.push(`/quality-specifications/${draft.id}/edit`); }
    catch (e) { setError(qualityErrorMessage(e, errors)); setBusy(false); }
  }

  const back = <Link href="/quality-specifications" className={s.button}>{t("backToList")}</Link>;
  if (loading) return <PageFrame title={t("detailTitle")} action={back}><p className={s.muted}>{messages("loading.default")}</p></PageFrame>;
  if (!spec) return <PageFrame title={t("detailTitle")} action={back}><p role="alert" className={s.error}>{error || t("notFound")}</p></PageFrame>;

  return <PageFrame title={`${spec.code} — rev ${spec.revision}`} subtitle={spec.title} action={back}>
    {spec.status === "superseded" && <p role="status" className={s.muted}>{t("supersededHint")}</p>}
    {error && <p role="alert" className={s.error}>{error}</p>}
    <section className={s.panel}>
      <div className={s.actions} style={{ justifyContent: "space-between", marginBottom: 16 }}>
        <SpecificationStatusBadge status={spec.status} />
        <span className={s.actions}>
          {spec.actions.includes("edit") && <Link href={`/quality-specifications/${spec.id}/edit`} className={s.button}>{t("edit")}</Link>}
          {spec.actions.includes("activate") && <button type="button" className={`${s.button} ${s.primary}`} disabled={busy} onClick={() => setConfirming(true)}>{t("activate")}</button>}
          {spec.actions.includes("revise") && <button type="button" className={s.button} disabled={busy} onClick={() => void revise()}>{t("revise")}</button>}
        </span>
      </div>
      <dl className={s.grid} style={{ margin: 0 }}>
        <Item label={t("fields.productType")}>{spec.product_type}</Item>
        <Item label={t("fields.grade")}>{spec.grade ?? "—"}</Item>
        <Item label={t("fields.createdBy")}>{spec.created_by_name ?? "—"}</Item>
        <Item label={t("fields.activatedAt")}>{spec.activated_at ? `${fmt.dateTime(spec.activated_at)} — ${spec.activated_by_name ?? ""}` : "—"}</Item>
      </dl>
      {spec.notes && <p style={{ marginBottom: 0, whiteSpace: "pre-wrap" }}><span className={s.muted}>{t("fields.notes")}: </span>{spec.notes}</p>}
    </section>
    <section className={s.panel} aria-label={t("linesTitle")}>
      <h2 style={{ marginTop: 0 }}>{t("linesTitle")}</h2>
      {spec.lines.length === 0 ? <p className={s.muted} style={{ margin: 0 }}>{t("noLines")}</p> : <div className={s.tableWrap}><table className={s.table}>
        <thead><tr>{["parameter", "unit", "target", "acceptance", "readingsRequired", "method"].map(c => <th key={c}>{t(`columns.${c}`)}</th>)}</tr></thead>
        <tbody>{spec.lines.map(line => <tr key={line.id}>
          <td><strong>{ar ? line.name_ar : line.name_en}</strong></td>
          <td>{line.unit ?? "—"}</td>
          <td><bdi>{line.kind === "numeric" ? targetText(line, t) : line.requirement}</bdi></td>
          <td><bdi>{line.kind === "numeric" ? limitsText(line, t) : (line.acceptance ?? "—")}</bdi></td>
          <td>{line.kind === "numeric" ? line.readings_required : "—"}</td>
          <td dir="auto">{line.method || line.parameter_method || "—"}</td>
        </tr>)}</tbody>
      </table></div>}
    </section>
    {confirming && <div className={s.overlay} onKeyDown={e => { if (e.key === "Escape" && !busy) setConfirming(false); }}>
      <div role="dialog" aria-modal="true" aria-label={t("activateTitle")} className={`${s.panel} ${s.dialog}`}>
        <h2 style={{ margin: 0 }}>{t("activateTitle")}</h2>
        <p className={s.muted}>{t("activateText")}</p>
        <div className={s.actions}>
          <button type="button" className={s.button} disabled={busy} onClick={() => setConfirming(false)} autoFocus>{t("cancel")}</button>
          <button type="button" className={`${s.button} ${s.primary}`} disabled={busy} onClick={() => void activate()}>{t("activate")}</button>
        </div>
      </div>
    </div>}
  </PageFrame>;
}
