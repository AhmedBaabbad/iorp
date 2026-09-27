export type WasteCategory =
  | "startup_loss"
  | "trim_loss"
  | "setup_loss"
  | "rejected_output"
  | "breakage"
  | "rewinding_loss"
  | "end_of_roll_loss"
  | "material_loss"
  | "contamination_loss"
  | "other";

export type WasteRecordListFilters = {
  production_order_id?: string;
  shift_report_id?: string;
  work_center_id?: string;
  waste_category?: WasteCategory;
  waste_date?: string;
};

export type WasteRecordListItem = {
  id: string;
  organization_id: string;
  production_order_id: string;
  work_center_id: string;
  shift_report_id: string | null;
  production_order_item_id: string | null;
  waste_date: string;
  quantity_wasted: string;
  unit: string;
  waste_category: WasteCategory;
  reason_code: string | null;
  created_by_user_id: string;
  created_at: string;
  updated_at: string;
};

export type WasteRecordData = WasteRecordListItem & {
  notes: string | null;
};

export type CreateWasteRecordRequest = {
  production_order_id: string;
  work_center_id: string;
  shift_report_id?: string | null;
  production_order_item_id?: string | null;
  waste_date: string;
  quantity_wasted: number;
  unit: string;
  waste_category: WasteCategory;
  reason_code?: string | null;
  notes?: string | null;
};
