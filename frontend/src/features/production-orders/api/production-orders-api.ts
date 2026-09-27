import { apiClient } from "@/lib/api-client";
import type {
  CreateProductionOrderRequest,
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

// Cancels a pre-execution order and releases all of its ACTIVE allocations in one transaction.
export function cancelProductionOrder(productionOrderId: string, reason: string) {
  return apiClient<ProductionOrderData>(`${PRODUCTION_ORDERS_PATH}/${productionOrderId}/cancel`, {
    method: "POST",
    body: { reason },
  });
}

export function createProductionOrder(payload: CreateProductionOrderRequest) {
  return apiClient<ProductionOrderData>(PRODUCTION_ORDERS_PATH, {
    method: "POST",
    body: payload,
  });
}
