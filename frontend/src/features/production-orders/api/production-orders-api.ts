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
export function transitionProductionOrder(productionOrderId: string, action: OrderAction, options: { reason?: string; expectedVersion?: number } = {}) {
  return apiClient<ProductionOrderData>(`${PRODUCTION_ORDERS_PATH}/${productionOrderId}/transitions`, {
    method: "POST",
    body: { action, reason: options.reason || null, expected_version: options.expectedVersion ?? null },
  });
}

export function getProductionOrderStatusHistory(productionOrderId: string) {
  return apiClient<OrderStatusHistoryEntry[]>(`${PRODUCTION_ORDERS_PATH}/${productionOrderId}/status-history`);
}

// Draft orders only: add a demand item, or change how much of it the order takes. Lines rearrange on the server.
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
