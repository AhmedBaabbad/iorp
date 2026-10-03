// Pure helpers for the downtime screens. The server enforces every rule; these only guide the user.
import type { DowntimeCategory } from "./types";
import {  } from "@/lib/production-permissions";

// Planned stops are outside planned production time; the others are availability losses (changeover included).
export const PLANNED_CATEGORIES: DowntimeCategory[] = ["planned_maintenance", "break_meeting", "no_orders"];
export const LOSS_CATEGORIES: DowntimeCategory[] = ["breakdown", "changeover_setup", "material_shortage", "waiting_labor", "quality_issue", "utilities", "other"];
export const ALL_CATEGORIES: DowntimeCategory[] = [...LOSS_CATEGORIES, ...PLANNED_CATEGORIES];
// A stop can be linked to an order while it runs, or as a late entry once it is completed.
export const LINKABLE_ORDER_STATUSES = ["in_progress", "on_hold", "completed"];

export function isPlanned(category: DowntimeCategory) {
  return PLANNED_CATEGORIES.includes(category);
}

/** `<input type="datetime-local">` value for an ISO instant, in the browser's time zone. */
export function toLocalInput(iso: string | null | undefined) {
  if (!iso) return "";
  const d = new Date(iso);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

/** The ISO instant (with zone) for a datetime-local value; the server rejects times without a zone. */
export function fromLocalInput(value: string) {
  return value ? new Date(value).toISOString() : null;
}

export function nowLocalInput(now = new Date()) {
  return toLocalInput(now.toISOString());
}
