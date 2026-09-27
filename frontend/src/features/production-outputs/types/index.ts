export type ProductionOutputStatus = "recorded" | "verified" | "posted";

export type ProductionOutputListFilters = {
  production_order_id?: string;
  shift_report_id?: string;
  work_center_id?: string;
  output_date?: string;
  output_status?: ProductionOutputStatus;
};

export type ProductionOutputListItem = {
  id: string;
  organization_id: string;
  production_order_id: string;
  work_center_id: string;
  shift_report_id: string | null;
  production_order_item_id: string | null;
  output_date: string;
  recorded_at: string | null;
  quantity_produced: string;
  unit: string;
  output_status: ProductionOutputStatus;
  created_by_user_id: string;
  created_at: string;
  updated_at: string;
};

export type ProductionOutputData = ProductionOutputListItem & {
  notes: string | null;
};

export type CreateProductionOutputRequest = {
  production_order_id: string;
  work_center_id: string;
  shift_report_id?: string | null;
  production_order_item_id?: string | null;
  output_date: string;
  recorded_at?: string | null;
  quantity_produced: number;
  unit: string;
  notes?: string | null;
};
