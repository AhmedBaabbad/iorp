// Pure helpers for the waste screens. The server enforces every rule; these only guide the user.
import type { WasteCategory } from "./types";
import {  } from "@/lib/production-permissions";

export const WASTE_CATEGORIES: WasteCategory[] = ["startup_setup", "changeover", "process", "material_defect", "machine_fault", "handling_damage", "contamination", "other"];
// Waste is recorded while the order runs, or as a late entry once it is completed; closing locks it.
export const WASTE_ORDER_STATUSES = ["in_progress", "on_hold", "completed"];
export const QUANTITY = /^\d+(\.\d{1,3})?$/;

export function todayIso(now = new Date()) {
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}
