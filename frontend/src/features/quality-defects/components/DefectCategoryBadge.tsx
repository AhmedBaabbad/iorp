"use client";

import { useClassificationName } from "@/features/masterdata";
import { defectCategoryColors } from "@/styles/badge-colors";
import { sharedStyles } from "@/styles/shared-styles";
import type { DefectCategory } from "../types";

type DefectCategoryBadgeProps = {
  category: DefectCategory;
};

/** A defect's category by its name in the organization's list (MD-003); an added category shows in neutral colours. */
export function DefectCategoryBadge({ category }: DefectCategoryBadgeProps) {
  const name = useClassificationName("defect_category", "qualityDefect", "defectCategory");
  return (
    <span style={{ ...sharedStyles.badge, ...(defectCategoryColors[category] ?? { background: "var(--surface-muted)", color: "var(--text-muted)" }) }}>
      {name(category)}
    </span>
  );
}
