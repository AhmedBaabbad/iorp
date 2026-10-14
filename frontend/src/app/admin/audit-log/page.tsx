"use client";

import { Suspense } from "react";

import { AuditLogPage } from "@/features/admin-audit/AuditLogPage";

export default function Page() {
  return <Suspense><AuditLogPage /></Suspense>;
}
