"use client";

import { useTranslations } from "next-intl";

import { getEnumLabel } from "@/i18n/enum-helpers";
import type { DefectCategory, DefectSeverity } from "../types";
import { DefectCategoryBadge } from "./DefectCategoryBadge";
import { DefectSeverityBadge } from "./DefectSeverityBadge";

export type DefectChip = { defect_category: DefectCategory; severity: DefectSeverity; defect_count?: number };

// The defects of a record as chips (most severe first, as the server sends them): the first ones shown, the rest as "+N"
// with their names on hover; then the record's severity, the highest among its defects.
export function DefectChips({ defects, severity, max = 2 }: { defects: DefectChip[]; severity?: DefectSeverity | null; max?: number }) {
  const t = useTranslations();
  if (!defects.length) return <>—</>;
  const shown = defects.slice(0, max);
  const rest = defects.slice(max);
  return <span style={{ display: "inline-flex", flexWrap: "wrap", gap: 4, alignItems: "center" }}>
    {severity ? <DefectSeverityBadge severity={severity} /> : null}
    {shown.map(d => <DefectCategoryBadge key={d.defect_category} category={d.defect_category} />)}
    {rest.length > 0 && <span title={rest.map(d => getEnumLabel("qualityDefect", "defectCategory", d.defect_category, t)).join("، ")}>+{rest.length}</span>}
  </span>;
}
