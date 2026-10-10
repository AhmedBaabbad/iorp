// Pure helpers for the waste screens. The server enforces every rule; these only guide the user.
import type { WasteCategory } from "./types";
import {  } from "@/lib/production-permissions";

export const WASTE_CATEGORIES: WasteCategory[] = ["startup_setup", "changeover", "process", "material_defect", "machine_fault", "handling_damage", "contamination", "other"];
// Waste is recorded while the order runs, or as a late entry once it is completed; closing locks it.
export const WASTE_ORDER_STATUSES = ["in_progress", "on_hold", "completed"];
export const QUANTITY = /^\d+(\.\d{1,3})?$/;

// Mirror of the server's split_categories (domain/waste_rules.py): one category takes the whole quantity; several need
// each a quantity > 0, adding up to the quantity wasted. Integer thousandths avoid floating-point drift.
export function splitCheck(quantity: string, shares: { quantity: string }[]) {
  const milli = (value: string) => (QUANTITY.test(value) ? Math.round(Number(value) * 1000) : null);
  const show = (value: number) => String(value / 1000);
  if (shares.length === 0) return { ok: false, total: "0", remaining: quantity || "0" };
  if (shares.length === 1) return { ok: true, total: quantity || "0", remaining: "0" };
  const parts = shares.map(x => milli(x.quantity));
  const sum = parts.reduce<number>((acc, part) => acc + (part ?? 0), 0);
  const whole = milli(quantity) ?? 0;
  const ok = parts.every(part => part !== null && part > 0) && sum === whole && whole > 0;
  return { ok, total: show(sum), remaining: show(whole - sum) };
}

export function todayIso(now = new Date()) {
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}
