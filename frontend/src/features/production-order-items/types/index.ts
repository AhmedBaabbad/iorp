export type ProductionOrderItemListItem = {
  id: string;
  production_order_id: string;
  line_no: number;
  target_spec_json: Record<string, unknown> | null;
  planned_quantity: string;
  unit: string;
  created_at: string;
  updated_at: string;
  notes?: string | null;
};

export type CreateProductionOrderItemRequest = {
  target_spec_json?: Record<string, unknown> | null;
  planned_quantity: number;
  unit: string;
  notes?: string | null;
};
