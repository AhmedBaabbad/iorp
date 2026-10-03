// Test parameters and product specifications (QUAL-SPEC-001). Limits are decimal strings in the parameter's unit.
export type ParameterKind = "numeric" | "attribute";
export type TargetSource = "fixed" | "order_line" | "none";
export type SpecificationStatus = "draft" | "active" | "superseded";
export type SpecificationAction = "edit" | "activate" | "revise";

export const SPEC_STATUSES: SpecificationStatus[] = ["active", "draft", "superseded"];
export const TARGET_SOURCES: TargetSource[] = ["order_line", "fixed", "none"];
// Specification keys the planning screens use on order lines (a target can be taken from them).
export const ORDER_SPEC_KEYS = ["width_mm", "thickness_mm", "thickness_micron", "roll_weight_kg", "weight_kg", "length_m"];

export type TestParameter = {
  id: string; code: string; name_ar: string; name_en: string; kind: ParameterKind;
  unit: string | null; method: string | null; is_active: boolean; sort_order: number;
};

export type ParameterInput = { code: string; name_ar: string; name_en: string; kind: ParameterKind; unit?: string | null; method?: string | null; sort_order?: number };
export type ParameterUpdate = Partial<Omit<ParameterInput, "code" | "kind">> & { is_active?: boolean };

export type SpecificationLineInput = {
  parameter_id: string;
  target_source: TargetSource;
  order_spec_key: string | null;
  target_value: string | null;
  tolerance_minus: string | null;
  tolerance_plus: string | null;
  min_value: string | null;
  max_value: string | null;
  requirement: string | null;
  acceptance: string | null;
  method: string | null;
  readings_required: number;
};

export type SpecificationLine = SpecificationLineInput & {
  id: string; position: number; parameter_code: string; name_ar: string; name_en: string; kind: ParameterKind;
  unit: string | null; parameter_method: string | null;
};

export type SpecificationListItem = {
  id: string; code: string; revision: number; title: string; product_type: string; grade: string | null;
  status: SpecificationStatus; activated_at: string | null; activated_by_name: string | null; created_by_name: string | null;
  actions: SpecificationAction[]; updated_at: string;
};

export type Specification = SpecificationListItem & { notes: string | null; lines: SpecificationLine[] };

export type SpecificationInput = {
  code?: string; title: string; product_type: string; grade: string | null; notes: string | null; lines: SpecificationLineInput[];
};
