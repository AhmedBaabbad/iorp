"use client";
import type { ReactNode } from "react";
import { useTranslations } from "next-intl";
import s from "./demands.module.css";

// The specification columns the server sorts lines by, in order.
export const SORT_COLUMNS = ["width_mm", "color", "thickness_mm", "roll_weight_kg"] as const;
const ALIASES: Record<string, string[]> = { width_mm: ["width_mm", "width"], color: ["color", "colour"], thickness_mm: ["thickness_mm", "thickness", "thickness_micron"], roll_weight_kg: ["roll_weight_kg", "weight_kg", "weight"] };

export type ArrangedAllocation = { key: string; customer_name: string | null; demand_number: string; demand_item_line_no: number; allocated_quantity: string; status?: string };
export type ArrangedLine = { key: string; line_no: number; target_spec_json: Record<string, unknown> | null; planned_quantity: string; unit: string; allocations: ArrangedAllocation[] };

function specValue(spec: Record<string, unknown> | null, column: string) {
  const name = ALIASES[column].find(key => spec?.[key] !== undefined && spec?.[key] !== null && spec?.[key] !== "");
  return name ? String(spec![name]) : "—";
}
function otherSpecs(spec: Record<string, unknown> | null) {
  const known = new Set(Object.values(ALIASES).flat());
  return Object.entries(spec ?? {}).filter(([key]) => !known.has(key)).map(([key, value]) => `${key}: ${typeof value === "object" ? JSON.stringify(value) : String(value)}`).join(" · ");
}

// One row per specification line (width -> color -> thickness -> weight), then the demands feeding it.
export function ArrangementTable({ lines, quantityCell, actionsCell, caption }: {
  lines: ArrangedLine[]; caption?: string;
  quantityCell?: (a: ArrangedAllocation, line: ArrangedLine) => ReactNode; actionsCell?: (a: ArrangedAllocation, line: ArrangedLine) => ReactNode;
}) {
  const t = useTranslations("production.allocation");
  const p = useTranslations("production.planning");
  const d = useTranslations("production.demands");
  const columns = 6 + (actionsCell ? 1 : 0);
  return <div className={s.tableWrap}><table className={s.table} aria-label={caption ?? t("arrangement")}>
    <thead><tr><th>{t("lineNo")}</th>{SORT_COLUMNS.map(c => <th key={c}>{p(`specColumns.${c}`)}</th>)}<th>{t("lineQuantity")}</th>{actionsCell && <th />}</tr></thead>
    {lines.map(line => <tbody key={line.key} className={s.lineGroup}>
      <tr className={s.lineRow}>
        <th scope="row">{line.line_no}</th>
        {SORT_COLUMNS.map(c => <td key={c}>{specValue(line.target_spec_json, c)}</td>)}
        <td><strong>{line.planned_quantity} {line.unit}</strong></td>{actionsCell && <td />}
      </tr>
      {otherSpecs(line.target_spec_json) && <tr><td /><td colSpan={columns - 1} className={s.muted}>{otherSpecs(line.target_spec_json)}</td></tr>}
      {line.allocations.map(a => <tr key={a.key} className={a.status === "released" ? s.releasedRow : undefined}>
        <td />
        <td colSpan={4}>{a.customer_name ?? "—"} · {a.demand_number} · {d("lineNo")} {a.demand_item_line_no}</td>
        <td>{quantityCell ? quantityCell(a, line) : `${a.allocated_quantity} ${line.unit}`}</td>
        {actionsCell && <td>{actionsCell(a, line)}</td>}
      </tr>)}
    </tbody>)}
  </table></div>;
}
