"use client";

import type { CSSProperties } from "react";

import { useEnumLabel } from "@/i18n/enum-helpers";
import type { WorkerType } from "../types";

const base: CSSProperties = {
  borderRadius: "999px",
  display: "inline-flex",
  fontSize: "12px",
  fontWeight: 700,
  lineHeight: 1,
  padding: "6px 9px",
  whiteSpace: "nowrap",
};

const MANAGEMENT: WorkerType[] = ["factory_manager", "production_manager", "supervisor"];
const TECHNICAL: WorkerType[] = ["technician", "operator", "maintenance_technician"];
const QUALITY_SAFETY: WorkerType[] = ["quality_inspector", "safety_officer"];
const SALES: WorkerType[] = ["sales_manager", "sales_rep"];

function colorFor(workerType: WorkerType): CSSProperties {
  if (MANAGEMENT.includes(workerType)) {
    return { background: "var(--accent-soft)", color: "var(--accent-strong)" };
  }
  if (TECHNICAL.includes(workerType)) {
    return { background: "var(--teal-soft)", color: "var(--teal)" };
  }
  if (QUALITY_SAFETY.includes(workerType)) {
    return { background: "var(--purple-soft)", color: "var(--purple)" };
  }
  if (SALES.includes(workerType)) {
    return { background: "var(--success-soft)", color: "var(--success)" };
  }
  return { background: "var(--surface-muted)", color: "var(--text-muted)" };
}

export function WorkforceMemberTypeBadge({ workerType }: { workerType: WorkerType }) {
  const enumLabel = useEnumLabel();
  return (
    <span style={{ ...base, ...colorFor(workerType) }}>
      {enumLabel("workforceMember", "workerType", workerType)}
    </span>
  );
}
