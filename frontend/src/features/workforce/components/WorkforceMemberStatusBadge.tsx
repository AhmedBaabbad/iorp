"use client";

import type { CSSProperties } from "react";

import { useEnumLabel } from "@/i18n/enum-helpers";
import type { WorkforceMemberStatus } from "../types";

const base: CSSProperties = {
  borderRadius: "999px",
  display: "inline-flex",
  fontSize: "12px",
  fontWeight: 700,
  lineHeight: 1,
  padding: "6px 9px",
  whiteSpace: "nowrap",
};

const colors: Record<WorkforceMemberStatus, CSSProperties> = {
  active: { background: "var(--success-soft)", color: "var(--success)" },
  inactive: { background: "var(--surface-muted)", color: "var(--text-muted)" },
  suspended: { background: "var(--warning-soft)", color: "var(--warning)" },
  terminated: { background: "var(--danger-soft)", color: "var(--danger)" },
};

export function WorkforceMemberStatusBadge({ status }: { status: WorkforceMemberStatus }) {
  const enumLabel = useEnumLabel();
  return (
    <span style={{ ...base, ...colors[status] }}>
      {enumLabel("workforceMember", "status", status)}
    </span>
  );
}
