"use client";

import { useLocale } from "next-intl";

import { useClassificationName } from "@/features/masterdata";
import type { DefectCategory, DefectSeverity } from "../types";
import { DefectCategoryBadge } from "./DefectCategoryBadge";
import { DefectSeverityBadge } from "./DefectSeverityBadge";

import { joinList } from "@/lib/utils";
export type DefectChip = { defect_category: DefectCategory; severity: DefectSeverity; defect_count?: number };

// The defects of a record as chips (most severe first, as the server sends them): the first ones shown, the rest as "+N"
// with their names on hover; then the record's severity, the highest among its defects.
export function DefectChips({ defects, severity, max = 2 }: { defects: DefectChip[]; severity?: DefectSeverity | null; max?: number }) {
  const name = useClassificationName("defect_category", "qualityDefect", "defectCategory");
  const locale = useLocale();
  if (!defects.length) return <>—</>;
  const shown = defects.slice(0, max);
  const rest = defects.slice(max);
  return <span style={{ display: "inline-flex", flexWrap: "wrap", gap: 4, alignItems: "center" }}>
    {severity ? <DefectSeverityBadge severity={severity} /> : null}
    {shown.map(d => <DefectCategoryBadge key={d.defect_category} category={d.defect_category} />)}
    {rest.length > 0 && <span title={joinList(rest.map(d => name(d.defect_category)), locale)}>+{rest.length}</span>}
  </span>;
}
