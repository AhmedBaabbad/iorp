"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import s from "@/features/production-demands/demands.module.css";
import { getDefectsByCheck } from "@/features/quality-defects/api/quality-defects-api";
import { DefectCategoryBadge } from "@/features/quality-defects/components/DefectCategoryBadge";
import { DefectSeverityBadge } from "@/features/quality-defects/components/DefectSeverityBadge";
import type { QualityDefectListItem } from "@/features/quality-defects/types";
import { useClassificationName } from "@/features/masterdata";

export type PickedDefect = { quality_defect_id: string; affected_quantity: string };

// The defects of the rejection's inspection it is made for: searchable, several at once, each once; how many of the
// rejected units a defect affects is optional and shown per defect (defects overlap, so they are never added up).
export function RejectionDefectsPicker({ checkId, value, onChange, unit, disabled }: {
  checkId: string; value: PickedDefect[]; onChange: (value: PickedDefect[]) => void; unit: string; disabled?: boolean;
}) {
  const t = useTranslations("quality.qualityRejections.defects");
  const category = useClassificationName("defect_category", "qualityDefect", "defectCategory");
  const [defects, setDefects] = useState<QualityDefectListItem[] | null>(null);
  const [search, setSearch] = useState("");
  useEffect(() => {
    let active = true;
    getDefectsByCheck(checkId).then(list => { if (active) setDefects(list); }).catch(() => { if (active) setDefects([]); });
    return () => { active = false; };
  }, [checkId]);
  if (defects === null) return null;
  const byId = new Map(defects.map(d => [d.id, d]));
  const name = (d: QualityDefectListItem) => category(d.defect_category);
  const query = search.trim().toLowerCase();
  const options = defects.filter(d => !value.some(v => v.quality_defect_id === d.id)
    && (!query || `${name(d)} ${d.description}`.toLowerCase().includes(query)));
  return <fieldset className={s.panel} disabled={disabled} style={{ margin: "16px 0" }}>
    <legend>{t("title")}</legend>
    {!defects.length ? <p className={s.muted}>{t("none")}</p> : <>
      <label className={s.field}>{t("search")}
        <input type="search" value={search} placeholder={t("searchPlaceholder")} onChange={e => setSearch(e.target.value)} />
      </label>
      <ul aria-label={t("available")} style={{ listStyle: "none", padding: 0, display: "flex", flexWrap: "wrap", gap: 8 }}>
        {options.map(d => <li key={d.id}>
          <button type="button" className={s.button} onClick={() => onChange([...value, { quality_defect_id: d.id, affected_quantity: "" }])}
            aria-label={t("add", { defect: name(d) })}>+ {name(d)} · {d.description}</button>
        </li>)}
      </ul>
      {value.length > 0 && <div className={s.tableWrap}><table className={s.table} aria-label={t("selected")}>
        <thead><tr><th>{t("defect")}</th><th>{t("severity")}</th><th>{t("affected", { unit })}</th><th /></tr></thead>
        <tbody>{value.map(v => { const d = byId.get(v.quality_defect_id); return <tr key={v.quality_defect_id}>
          <td>{d ? <><DefectCategoryBadge category={d.defect_category} /> {d.description}</> : "—"}</td>
          <td>{d ? <DefectSeverityBadge severity={d.severity} /> : "—"}</td>
          <td><input type="number" min="0.001" step="0.001" inputMode="decimal" value={v.affected_quantity} aria-label={t("affectedFor", { defect: d ? name(d) : "" })}
            onChange={e => onChange(value.map(x => x.quality_defect_id === v.quality_defect_id ? { ...x, affected_quantity: e.target.value } : x))} /></td>
          <td><button type="button" className={s.button} onClick={() => onChange(value.filter(x => x.quality_defect_id !== v.quality_defect_id))}
            aria-label={t("remove", { defect: d ? name(d) : "" })}>{t("removeShort")}</button></td>
        </tr>; })}</tbody>
      </table></div>}
      <p className={s.muted}>{t("overlapHint")}</p>
    </>}
  </fieldset>;
}
