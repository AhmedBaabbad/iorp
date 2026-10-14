"use client";
/**
 * Approval delegations on the screens (PROJECT-GOV-004). The server decides everything; this only knows which approvals
 * can be delegated (to show the page to whoever holds one) and how many delegations wait for the user's answer.
 */
import { useEffect, useState } from "react";

import { apiClient } from "@/lib/api-client";
import { P } from "@/lib/production-permissions";

export const DELEGATIONS_READ = "foundation:delegations:read";
export const DELEGATIONS_MANAGE = "foundation:delegations:manage";

/** The approvals that can be signed under a delegation (backend foundation/domain/delegations.py DELEGABLE). */
export const DELEGABLE = [
  "commercial:quotes:issue",
  "commercial:orders:confirm",
  "commercial:complaints:close",
  "procurement:purchase_orders:approve",
  "procurement:suppliers:approve",
  P.ORDERS_RELEASE,
  P.ORDERS_CLOSE,
  "quality:quality_checks:close",
  "quality:rejections:decide",
  "quality:ncr_reports:verify",
  "quality:certificates:issue",
  "shipping:returns:approve",
];

/** Whoever holds an approval that can be delegated, reads or manages delegations, sees the page. */
export const DELEGATIONS_PAGE = [DELEGATIONS_READ, DELEGATIONS_MANAGE, ...DELEGABLE];

const listeners = new Set<(count: number) => void>();

/** Ask again (after an answer on the page), so the number on the menu follows. */
export function refreshDelegationsWaiting() {
  apiClient<{ count: number }>("/delegations/waiting").then((r) => listeners.forEach((l) => l(r.count))).catch(() => {});
}

/** How many delegations wait for the user's answer (the number on the menu). */
export function useDelegationsWaiting(enabled: boolean): number {
  const [count, setCount] = useState(0);
  useEffect(() => {
    if (!enabled) return;
    let active = true;
    const listener = (next: number) => { if (active) setCount(next); };
    listeners.add(listener);
    Promise.resolve().then(() => apiClient<{ count: number }>("/delegations/waiting")).then((r) => listener(r?.count ?? 0)).catch(() => {});
    return () => { active = false; listeners.delete(listener); };
  }, [enabled]);
  return enabled ? count : 0;
}
