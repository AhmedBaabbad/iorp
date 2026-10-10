import { apiClient } from "@/lib/api-client";
import type {
  CreateProductionOrderRequest,
  OrderAction,
  OrderStatusHistoryEntry,
  ProductionOrderData,
  ProductionOrderListFilters,
  ProductionOrderListItem,
} from "../types";

const PRODUCTION_ORDERS_PATH = "/production/production-orders";

export function getProductionOrders(filters: ProductionOrderListFilters = {}) {
  const query = new URLSearchParams();

  if (filters.status) {
    query.set("status", filters.status);
  }

  if (filters.priority) {
    query.set("priority", filters.priority);
  }

  if (filters.work_center_id) {
    query.set("work_center_id", filters.work_center_id);
  }

  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return apiClient<ProductionOrderListItem[]>(`${PRODUCTION_ORDERS_PATH}${suffix}`);
}

export function getProductionOrderById(productionOrderId: string) {
  return apiClient<ProductionOrderData>(
    `${PRODUCTION_ORDERS_PATH}/${productionOrderId}`,
  );
}

// The only way to change an order's status. expectedVersion guards against a concurrent change.
// zeroOutput (close only): the order produced nothing; the reason is then mandatory.
export function transitionProductionOrder(productionOrderId: string, action: OrderAction, options: { reason?: string; expectedVersion?: number; zeroOutput?: boolean } = {}) {
  return apiClient<ProductionOrderData>(`${PRODUCTION_ORDERS_PATH}/${productionOrderId}/transitions`, {
    method: "POST",
    body: { action, reason: options.reason || null, expected_version: options.expectedVersion ?? null, ...(options.zeroOutput ? { zero_output: true } : {}) },
  });
}

export function getProductionOrderStatusHistory(productionOrderId: string) {
  return apiClient<OrderStatusHistoryEntry[]>(`${PRODUCTION_ORDERS_PATH}/${productionOrderId}/status-history`);
}

// Open orders (draft, released, in progress, on hold): add a demand item, or change how much of it the order takes.
// A draft's lines rearrange on the server; an order on the floor keeps its lines and only adjusts them.
export type EligibleOrder = { id: string; production_order_number: string; status: string; work_center_name: string | null; product_type: string; unit: string; planned_quantity: string; planned_start_date: string; planned_end_date: string };

export function getEligibleOrders(demandItemId: string) {
  return apiClient<EligibleOrder[]>(`/production/planning/eligible-orders?demand_item_id=${encodeURIComponent(demandItemId)}`);
}

export function addOrderAllocation(productionOrderId: string, productionDemandItemId: string, allocatedQuantity: string) {
  return apiClient<ProductionOrderData>(`/production/orders/${productionOrderId}/allocations`, {
    method: "POST",
    body: { production_demand_item_id: productionDemandItemId, allocated_quantity: allocatedQuantity },
  });
}

export function changeAllocationQuantity(allocationId: string, allocatedQuantity: string) {
  return apiClient<ProductionOrderData>(`/production/allocations/${allocationId}`, {
    method: "PATCH",
    body: { allocated_quantity: allocatedQuantity },
  });
}

export function createProductionOrder(payload: CreateProductionOrderRequest) {
  return apiClient<ProductionOrderData>(PRODUCTION_ORDERS_PATH, {
    method: "POST",
    body: payload,
  });
}
