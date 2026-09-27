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
  active: { background: "#dcfce7", color: "#166534" },
  inactive: { background: "#f1f5f9", color: "#475569" },
  suspended: { background: "#fef3c7", color: "#92400e" },
  terminated: { background: "#fee2e2", color: "#991b1b" },
};

export function WorkforceMemberStatusBadge({ status }: { status: WorkforceMemberStatus }) {
  const enumLabel = useEnumLabel();
  return (
    <span style={{ ...base, ...colors[status] }}>
      {enumLabel("workforceMember", "status", status)}
    </span>
  );
}
