export type ProductionOrderStatus =
  | "draft"
  | "released"
  | "in_progress"
  | "on_hold"
  | "completed"
  | "closed"
  | "cancelled";

// Lifecycle order, for filters and legends. Transitions come from the server, never from here.
export const PRODUCTION_ORDER_STATUSES: ProductionOrderStatus[] = ["draft", "released", "in_progress", "on_hold", "completed", "closed", "cancelled"];

export type OrderAction = "release" | "return_to_draft" | "start" | "hold" | "resume" | "complete" | "close" | "cancel";

export type OrderLifecycle = {
  status_version: number;
  actual_start_at: string | null;
  actual_end_at: string | null;
  start_overdue: boolean;
  finish_overdue: boolean;
  terminal: boolean;
  // Only the actions valid now AND permitted for this user.
  actions: { action: OrderAction; target: ProductionOrderStatus; requires_reason: boolean; confirm: boolean }[];
};

export type OrderStatusHistoryEntry = {
  id: string;
  from_status: ProductionOrderStatus;
  to_status: ProductionOrderStatus;
  action: OrderAction;
  trigger: "manual" | "activity" | "schedule";
  actor_user_id: string | null;
  actor_name: string | null;
  reason: string | null;
  created_at: string;
};

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
  allocations: { id: string; production_demand_id: string; production_demand_item_id: string; demand_number: string; customer_name: string | null; demand_item_line_no: number; allocated_quantity: string; unit: string; status: "active" | "released"; allocated_at: string; released_at: string | null; release_reason: string | null; target_spec_json?: Record<string, unknown> | null; production_order_item_id?: string | null; order_line_no?: number | null }[];
  active_allocated_quantity?: string;
  // Specification lines, ordered width -> color -> thickness -> weight.
  lines?: { id: string; line_no: number; target_spec_json: Record<string, unknown> | null; planned_quantity: string; unit: string; allocation_ids: string[] }[];
  // Allocations can be added or changed only while the order is a draft.
  editable?: boolean;
  lifecycle?: OrderLifecycle | null;
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
