// Pure helpers for the result screens. The server enforces every rule; these only guide the user.
import { fromMilli, toMilli } from "@/features/production-demands/planning-lifecycle";
import type { Disposition, OrderResult, ResultOriginal } from "./types";
import {  } from "@/lib/production-permissions";

export const DISPOSITIONS: Disposition[] = ["customer_good", "stock_good", "sample", "scrap", "rework"];
// Loss is fixed for every disposition except samples, where the user must choose.
export const FIXED_LOSS: Partial<Record<Disposition, boolean>> = { customer_good: false, stock_good: false, scrap: true, rework: false };
export const QUANTITY = /^\d+(\.\d{1,3})?$/;
export const SIGNED_QUANTITY = /^-?\d+(\.\d{1,3})?$/;
// Statuses that come before the result can be recorded (a short hint is shown; cancelled shows nothing).
export const RESULT_PENDING_STATUSES = ["draft", "released", "in_progress", "on_hold"];

export function lossFor(disposition: Disposition, chosen: boolean | null): boolean | null {
  return disposition in FIXED_LOSS ? FIXED_LOSS[disposition]! : chosen;
}

export type CustomerRoom = { allocated: string; recorded: string; remaining: string };

/** How much customer_good the entry may still take, in the scope the server checks (item or order + unit). */
export function customerRoom(view: OrderResult, itemId: string | null, unit: string, editing?: ResultOriginal | null): CustomerRoom | null {
  let allocated: string | null = null;
  let recorded = BigInt(0);
  if (view.allocation_level === "item") {
    const item = view.items.find(i => i.id === itemId);
    allocated = item?.allocated_quantity ?? null;
    recorded = toMilli(item?.summary.customer_good ?? "0");
  } else if (view.allocation_level === "order") {
    const total = view.totals.find(t => t.unit === unit);
    allocated = total?.allocated_qty ?? null;
    recorded = toMilli(total?.customer_good ?? "0");
  }
  if (allocated === null || toMilli(allocated) <= BigInt(0)) return null;
  // Editing replaces the entry's own quantity, so it does not count against itself.
  if (editing && editing.disposition === "customer_good" && (view.allocation_level === "order" || editing.production_order_item_id === itemId)) {
    recorded -= toMilli(editing.effective_quantity);
  }
  const remaining = toMilli(allocated) - recorded;
  return { allocated: fromMilli(toMilli(allocated)), recorded: fromMilli(recorded), remaining: fromMilli(remaining > BigInt(0) ? remaining : BigInt(0)) };
}

export function exceeds(room: CustomerRoom | null, quantity: string) {
  return Boolean(room && QUANTITY.test(quantity) && toMilli(quantity) > toMilli(room.remaining));
}

export function specSummary(spec: Record<string, unknown> | null | undefined) {
  return Object.entries(spec ?? {}).filter(([, v]) => v !== null && v !== "" && v !== undefined)
    .map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : String(v)}`).join(" · ");
}

export function isNegative(value: string) {
  return toMilli(value) < BigInt(0);
}
