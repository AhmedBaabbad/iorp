// Specification lines in words (QUAL-SPEC-001). Pure: no React.
import type { SpecificationLineInput } from "./types";

type Translate = (key: string, values?: Record<string, string>) => string;

const plain = (value: string | null) => (value === null || value === "" ? null : String(Number(value)));

/** The target, as the specification states it: a value, "from the order line (width_mm)", or nothing. */
export function targetText(line: SpecificationLineInput, t: Translate) {
  if (line.target_source === "fixed") return plain(line.target_value) ?? "—";
  if (line.target_source === "order_line") return t("lineText.fromOrder", { key: line.order_spec_key ?? "" });
  return "—";
}

/** The acceptance limits: explicit minimum and maximum win over the tolerances around the target. */
export function limitsText(line: SpecificationLineInput, t: Translate) {
  const min = plain(line.min_value), max = plain(line.max_value);
  const minus = line.target_source !== "none" ? plain(line.tolerance_minus) : null;
  const plus = line.target_source !== "none" ? plain(line.tolerance_plus) : null;
  const parts = [
    min !== null ? t("lineText.min", { value: min }) : minus !== null ? t("lineText.minus", { value: minus }) : null,
    max !== null ? t("lineText.max", { value: max }) : plus !== null ? t("lineText.plus", { value: plus }) : null,
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : "—";
}

export function emptyLine(parameterId: string): SpecificationLineInput {
  return { parameter_id: parameterId, target_source: "none", order_spec_key: null, target_value: null, tolerance_minus: null, tolerance_plus: null,
    min_value: null, max_value: null, requirement: null, acceptance: null, method: null, readings_required: 1 };
}
