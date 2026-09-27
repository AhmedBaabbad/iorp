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
    return { background: "#dbeafe", color: "#1e40af" };
  }
  if (TECHNICAL.includes(workerType)) {
    return { background: "#ccfbf1", color: "#0f766e" };
  }
  if (QUALITY_SAFETY.includes(workerType)) {
    return { background: "#f3e8ff", color: "#7e22ce" };
  }
  if (SALES.includes(workerType)) {
    return { background: "#dcfce7", color: "#166534" };
  }
  return { background: "#f1f5f9", color: "#475569" };
}

export function WorkforceMemberTypeBadge({ workerType }: { workerType: WorkerType }) {
  const enumLabel = useEnumLabel();
  return (
    <span style={{ ...base, ...colorFor(workerType) }}>
      {enumLabel("workforceMember", "workerType", workerType)}
    </span>
  );
}
