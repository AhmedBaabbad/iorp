// Operational waste records (PROD-WASTE-001). Quantities are decimal strings, as the API sends them.
export type WasteCategory =
  | "startup_setup" | "changeover" | "process" | "material_defect"
  | "machine_fault" | "handling_damage" | "contamination" | "other";

export type WasteAction = "edit" | "delete";

export type WasteRecordListFilters = {
  production_order_id?: string;
  production_run_id?: string;
  work_center_id?: string;
  waste_category?: WasteCategory;
  date_from?: string;
  date_to?: string;
};

export type WasteRecordListItem = {
  id: string;
  organization_id: string;
  production_order_id: string;
  production_order_item_id: string | null;
  production_run_id: string | null;
  work_center_id: string;
  waste_date: string;
  quantity_wasted: string;
  // A code of the central unit list (src/lib/units.ts); on a record flagged at migration, the text as written.
  unit: string;
  // The unit as written before units became codes; unit_needs_review: it matched no code and must be chosen again.
  legacy_unit_text?: string | null;
  unit_needs_review?: boolean;
  waste_category: WasteCategory;
  reason_code: string | null;
  created_by_user_id: string;
  updated_by_user_id: string | null;
  created_at: string;
  updated_at: string;
  labels?: {
    order_number: string | null; order_status: string | null; line_no: number | null; work_center_name: string | null;
    run_date: string | null; created_by_name: string | null;
    // What this user may do now; the server enforces the same rules.
    actions: WasteAction[];
  } | null;
};

export type WasteRecordData = WasteRecordListItem & { notes: string | null };

export type WasteRecordInput = {
  production_order_id: string;
  production_order_item_id?: string | null;
  production_run_id?: string | null;
  work_center_id?: string | null;
  waste_date: string;
  quantity_wasted: string;
  unit: string;
  waste_category: WasteCategory;
  reason_code?: string | null;
  notes?: string | null;
};

export type WasteRecordUpdate = Partial<Omit<WasteRecordInput, "production_order_id">>;

export type WasteSummary = {
  order: { id: string; number: string; status: string; unit: string };
  available: boolean;
  locked: boolean;
  totals: { unit: string; quantity: string; count: number }[];
  by_category: { category: WasteCategory; unit: string; quantity: string; count: number }[];
  actions: "create"[];
};
