export type ProductionOrderStatus =
  | "draft"
  | "released"
  | "in_progress"
  | "completed"
  | "cancelled";

export type ProductionOrderPriority = "urgent" | "high" | "normal" | "low";

export type ProductionOrderListFilters = {
  status?: ProductionOrderStatus;
  priority?: ProductionOrderPriority;
  work_center_id?: string;
};

export type ProductionOrderListItem = {
  id: string;
  organization_id: string;
  production_order_number: string;
  work_center_id: string;
  product_type: string;
  planned_quantity: string;
  unit: string;
  priority: ProductionOrderPriority;
  status: ProductionOrderStatus;
  planned_start_date: string;
  planned_end_date: string;
  created_by_user_id: string;
  created_at: string;
  updated_at: string;
};

export type ProductionOrderData = ProductionOrderListItem & {
  allocations: { id: string; production_demand_id: string; production_demand_item_id: string; demand_number: string; customer_name: string | null; demand_item_line_no: number; allocated_quantity: string; unit: string; status: "active" | "released"; allocated_at: string; released_at: string | null; release_reason: string | null }[];
  active_allocated_quantity?: string;
  target_spec_json: Record<string, unknown> | null;
  notes: string | null;
};

export type CreateProductionOrderRequest = {
  allocations: { production_demand_item_id: string; allocated_quantity: string }[];
  work_center_id: string;
  priority: ProductionOrderPriority;
  planned_start_date: string;
  planned_end_date: string;
  notes?: string | null;
};
