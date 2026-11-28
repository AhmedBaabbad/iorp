"use client";
import {TestMethodSelect} from "./TestMethodSelect";
import {RecordCombobox} from "@/components/ui/RecordCombobox";
import {useUnsavedFormChanges} from "@/hooks/useUnsavedChangesGuard";
import { localName } from "@/lib/local-name";
import {useUnitLabel} from "@/components/UnitLabel";
import {Combobox} from "@/components/ui/Combobox";


import Link from "next/link";
import {ParameterCreateDialog} from "./ParameterFormFields";
import {usePermission} from "@/features/auth/permission-hooks";
import {Q} from "@/lib/quality-permissions";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useMemo, useState, type FormEvent } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { ProductSelect } from "@/features/masterdata";
import s from "@/features/production-demands/demands.module.css";
import { qualityErrorMessage } from "@/features/quality-checks/components/quality-errors";
import { createSpecification, getNumericProperties, getParameters, getSpecification, updateSpecification } from "../api";
import { emptyLine } from "../spec-lines";
import { TARGET_SOURCES, type NumericProperty, type Specification, type SpecificationLineInput, type TargetSource, type TestParameter } from "../types";
import { useRevealNewRow } from "@/hooks/useRevealNewRow";

type Header = { code: string; title: string; product_type: string; grade: string; notes: string };
const DECIMAL = /^-?\d+(\.\d{1,4})?$/;

// A new specification (revision 1, draft) or a draft's edit: header and one line per parameter with its acceptance.
export function SpecificationForm({ specId }: { specId?: string }) {
  const unitText = useUnitLabel();
  const t = useTranslations("quality.specifications");
  const errors = useTranslations("quality.errors");
  const messages = useTranslations("messages");
  const locale = useLocale();
  const router = useRouter();
  const editing = Boolean(specId);
  const [header, setHeader] = useState<Header>({ code: "", title: "", product_type: "", grade: "", notes: "" });
  const [lines, setLines] = useState<SpecificationLineInput[]>([]);
  const revealLine = useRevealNewRow(lines.length, "spec-lines");
  const [existing, setExisting] = useState<Specification | null>(null);
  const [parameters, setParameters] = useState<TestParameter[]>([]);
  const [properties,setProperties]=useState<NumericProperty[]>([]);
  const [adding, setAdding] = useState("");
  const [creatingParameter,setCreatingParameter]=useState(false);
  const canCreateParameter=usePermission(Q.SPECS_CREATE);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([getNumericProperties(), getParameters(), specId ? getSpecification(specId) : Promise.resolve(null)]).then(([numericProperties, params, spec]) => {
      if (!active) return;
      setParameters(params);setProperties(numericProperties);
      if (spec) {
        setExisting(spec);
        setHeader({ code: spec.code, title: spec.title, product_type: spec.product_type, grade: spec.grade ?? "", notes: spec.notes ?? "" });
        setLines(spec.lines.map(({ parameter_id, target_source, order_spec_key, target_value, tolerance_minus, tolerance_plus, min_value, max_value,
          requirement_ar, requirement_en, acceptance_ar, acceptance_en, method_ar, method_en, readings_required }) => ({ parameter_id, target_source, order_spec_key, target_value, tolerance_minus,
          tolerance_plus, min_value, max_value, requirement_ar, requirement_en, acceptance_ar, acceptance_en, method_ar, method_en, readings_required })));
      }
    }).catch(e => { if (active) setError(qualityErrorMessage(e, errors)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [specId, errors]);

  const byId = useMemo(() => new Map(parameters.map(p => [p.id, p])), [parameters]);
  const unused = parameters.filter(p => p.is_active && !lines.some(l => l.parameter_id === p.id));
  const locked = Boolean(existing && !existing.actions.includes("edit"));
  const numbersOk = lines.every(l => [l.target_value, l.tolerance_minus, l.tolerance_plus, l.min_value, l.max_value].every(v => !v || DECIMAL.test(v)));
  const valid = Boolean(header.code.trim() && header.title.trim() && header.product_type.trim()) && numbersOk;
  const name = (p?: TestParameter) => (p ? localName(p, locale) : "—");

  const setLine = (index: number, patch: Partial<SpecificationLineInput>) => setLines(old => old.map((l, i) => (i === index ? { ...l, ...patch } : l)));
  const move = (index: number, step: number) => setLines(old => {
    const next = [...old]; const [line] = next.splice(index, 1); next.splice(Math.max(0, Math.min(next.length, index + step)), 0, line); return next;
  });
  const addLine = (id: string) => { if (id) { revealLine(); setLines(old => [...old, emptyLine(id)]); setAdding(""); } };

  const unsaved=useUnsavedFormChanges({header,lines},!loading);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!valid || busy || locked) return;
    setBusy(true); setError("");
    const body = { title: header.title.trim(), product_type: header.product_type.trim(), grade: header.grade.trim() || null, notes: header.notes.trim() || null,
      lines: lines.map(l => ({ ...l, order_spec_key: l.target_source === "order_line" ? l.order_spec_key : null,
        target_value: l.target_source === "fixed" ? l.target_value || null : null,
        tolerance_minus: l.target_source === "none" ? null : l.tolerance_minus || null, tolerance_plus: l.target_source === "none" ? null : l.tolerance_plus || null,
        min_value: l.target_source==="order_line"?null:l.min_value || null, max_value: l.target_source==="order_line"?null:l.max_value || null,
        requirement_ar:l.requirement_ar?.trim()||null,requirement_en:l.requirement_en?.trim()||null,
        acceptance_ar:l.acceptance_ar?.trim()||null,acceptance_en:l.acceptance_en?.trim()||null,
        method_ar:l.method_ar?.trim()||null,method_en:l.method_en?.trim()||null })) };
    try {
      const saved = specId ? await updateSpecification(specId, body) : await createSpecification({ ...body, code: header.code.trim() });
      unsaved.markSaved(); router.push(`/quality-specifications/${saved.id}`);
    } catch (e) {
      const parameter = (e as { details?: { detail?: { parameter?: string } } }).details?.detail?.parameter;
      setError(qualityErrorMessage(e, errors) + (parameter ? ` (${parameter})` : ""));
      setBusy(false);
    }
  }

  const back = specId ? `/quality-specifications/${specId}` : "/quality-specifications";
  const title = editing ? t("editTitle", { code: existing?.code ?? "", revision: String(existing?.revision ?? "") }) : t("createTitle");
  return <PageFrame title={title} subtitle={t("formSubtitle")} action={<Link href={back} className={s.button}>{t("back")}</Link>}>
    {loading ? <p className={s.muted}>{messages("loading.default")}</p> : <form onKeyDownCapture={unsaved.onKeyboardInteraction} onChangeCapture={unsaved.onInteraction} onClickCapture={unsaved.onInteraction} onSubmit={submit} aria-label={title}>{unsaved.confirmation}
      {locked && <p role="status" className={s.error}>{t("lockedHint")}</p>}
      <section className={s.panel}>
        <div className={s.grid}>
          <label className={s.field}>{t("fields.code")}
            <input required maxLength={40} pattern="[A-Za-z0-9_\-]+" dir="ltr" placeholder="ROF-TDS-PP-001" value={header.code} disabled={editing}
              onChange={e => setHeader(h => ({ ...h, code: e.target.value }))} />
          </label>
          <label className={s.field}>{t("fields.title")}<input required maxLength={200} value={header.title} disabled={busy || locked} onChange={e => setHeader(h => ({ ...h, title: e.target.value }))} /></label>
          <label className={s.field}>{t("fields.productType")}<ProductSelect ariaLabel={t("fields.productType")} value={header.product_type} disabled={busy || locked}
            onChange={key => setHeader(h => ({ ...h, product_type: key }))} /></label>
          <label className={s.field}>{t("fields.grade")}<input maxLength={80} placeholder={t("gradePlaceholder")} value={header.grade} disabled={busy || locked} onChange={e => setHeader(h => ({ ...h, grade: e.target.value }))} /></label>
        </div>
        <p className={s.muted}>{t("productHint")}</p>
        <label className={s.field}>{t("fields.notes")}<textarea maxLength={4000} value={header.notes} disabled={busy || locked} onChange={e => setHeader(h => ({ ...h, notes: e.target.value }))} /></label>
      </section>

      <section className={s.panel} aria-label={t("linesTitle")}>
        <h2 style={{ marginTop: 0 }}>{t("linesTitle")}</h2>
        <p className={s.muted}>{t("linesHint")}</p>
        {parameters.length === 0 && <p className={s.muted}>{t("noParameters")}</p>}
        {canCreateParameter&&!locked&&<button type="button" className={s.button} disabled={busy} onClick={()=>setCreatingParameter(true)}>{t("addParameter")}</button>}
        {creatingParameter&&<ParameterCreateDialog onClose={()=>setCreatingParameter(false)} onCreated={parameter=>{setParameters(old=>[...old,parameter]);addLine(parameter.id);}}/>}
        {lines.map((line, index) => {
          const p = byId.get(line.parameter_id);
          const numeric = p?.kind === "numeric";
          const field = (key: keyof SpecificationLineInput, label: string, extra: Record<string, unknown> = {}) =>
            <label className={s.field}>{label}<input dir="ltr" inputMode="decimal" value={(line[key] as string | null) ?? ""} disabled={busy || locked}
              onChange={e => setLine(index, { [key]: e.target.value })} {...extra} /></label>;
          return <fieldset key={line.parameter_id} data-row="spec-lines" className={s.panel} style={{ margin: "0 0 12px", padding: 16 }} disabled={busy || locked}>
            <legend style={{ fontWeight: 700 }}>{index + 1}. {name(p)} {p?.unit && <span className={s.muted}>({p.unit})</span>}</legend>
            <div className={s.grid}>
              {numeric ? <>
                <label className={s.field}>{t("fields.targetSource")}
                  <select value={line.target_source} onChange={e => setLine(index, { target_source: e.target.value as TargetSource })}>
                    {TARGET_SOURCES.map(v => <option key={v} value={v}>{t(`targetSources.${v}`)}</option>)}
                  </select>
                </label>
                {line.target_source === "order_line" && <>
                  <Combobox label={t("fields.orderSpecKey")} required value={line.order_spec_key} disabled={busy||locked}
                    options={[...properties.map(prop=>({id:prop.key,name:localName(prop,locale),detail:prop.key})),
                      ...(line.order_spec_key&&!properties.some(prop=>prop.key===line.order_spec_key)?[{id:line.order_spec_key,name:line.order_spec_key,detail:t("unknownTemplateKey")}]:[])]}
                    onChange={key=>setLine(index,{order_spec_key:key})}/>
                  <p className={s.muted}>{t("orderLineHint")}</p>
                  {line.order_spec_key&&!properties.some(prop=>prop.key===line.order_spec_key)&&<p role="status" className={s.error}>{t("unknownTemplateKey")}</p>}
                </>}
                {line.target_source === "fixed" && field("target_value", t("fields.target"), { required: true })}
                {line.target_source !== "none" && field("tolerance_minus", t("fields.toleranceMinus"))}
                {line.target_source !== "none" && field("tolerance_plus", t("fields.tolerancePlus"))}
                {line.target_source!=="order_line"&&<>{field("min_value",t("fields.min"))}{field("max_value",t("fields.max"))}</>}
                {line.target_source==="order_line"&&<p className={s.muted}>{t("scalarToleranceHint")}</p>}
                <label className={s.field}>{t("fields.readingsRequired")}
                  <input type="number" min={1} max={50} value={line.readings_required} onChange={e => setLine(index, { readings_required: Number(e.target.value) || 1 })} />
                </label>
              </> : <>
                {(["ar","en"] as const).map(lang=><label className={s.field} key={"requirement_"+lang}>{t(`fields.requirement_${lang}`)}<input maxLength={255} dir={lang==="ar"?"rtl":"ltr"} value={line[`requirement_${lang}`]??""} onChange={e=>setLine(index,{[`requirement_${lang}`]:e.target.value})} required={lang==="ar"&&!line.requirement_ar?.trim()&&!line.requirement_en?.trim()}/></label>)}
                {(["ar","en"] as const).map(lang=><label className={s.field} key={"acceptance_"+lang}>{t(`fields.acceptance_${lang}`)}<input maxLength={255} dir={lang==="ar"?"rtl":"ltr"} value={line[`acceptance_${lang}`]??""} onChange={e=>setLine(index,{[`acceptance_${lang}`]:e.target.value})}/></label>)}
              </>}
              <TestMethodSelect method_ar={line.method_ar} method_en={line.method_en} label={t("fields.method")} labelAr={t("fields.method_ar")} labelEn={t("fields.method_en")} disabled={busy||locked} onChange={method=>setLine(index,method)}/>
            </div>
            <div className={s.actions} style={{ marginTop: 10 }}>
              <button type="button" className={s.button} disabled={index === 0} onClick={() => move(index, -1)} aria-label={t("moveUp")}>↑</button>
              <button type="button" className={s.button} disabled={index === lines.length - 1} onClick={() => move(index, 1)} aria-label={t("moveDown")}>↓</button>
              <button type="button" className={`${s.button} ${s.danger}`} onClick={() => setLines(old => old.filter((_, i) => i !== index))}>{t("removeLine")}</button>
            </div>
          </fieldset>;
        })}
        {!locked && unused.length > 0 && <div className={s.actions}>
          <label className={s.field}>{t("addLine")}
            <RecordCombobox aria-label={t("addLine")} value={adding} disabled={busy} onChange={e => setAdding(e)}>
              <option value="">—</option>
              {unused.map(p => <option key={p.id} value={p.id}>{name(p)}{p.unit ? ` (${unitText(p.unit)})` : ""}</option>)}
            </RecordCombobox>
          </label>
          <button type="button" className={s.button} disabled={!adding || busy} onClick={() => addLine(adding)}>{t("add")}</button>
          <button type="button" className={s.button} disabled={busy} onClick={() => setLines(old => [...old, ...unused.map(p => emptyLine(p.id))])}>{t("addAll")}</button>
        </div>}
      </section>
      {error && <p role="alert" className={s.error}>{error}</p>}
      <div className={s.actions}>
        <button type="submit" className={`${s.button} ${s.primary}`} disabled={!valid || busy || locked}>{editing ? t("save") : t("create")}</button>
        <Link href={back} className={s.button}>{t("cancel")}</Link>
      </div>
    </form>}
  </PageFrame>;
}
