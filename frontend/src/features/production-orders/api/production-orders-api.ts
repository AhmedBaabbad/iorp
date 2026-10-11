import { apiClient } from "@/lib/api-client";
import type { Page } from "@/lib/pagination";
import type {
  CreateProductionOrderRequest,
  OrderAction,
  OrderStatusHistoryEntry,
  ProductionOrderData,
  ProductionOrderListItem,
} from "../types";

const PRODUCTION_ORDERS_PATH = "/production/production-orders";

// One page of orders (ARCH-PAGE-001): `query` carries page, page_size, search and the filters (useListQuery().apiQuery()).
export function getProductionOrders(query = "") {
  return apiClient<Page<ProductionOrderListItem>>(`${PRODUCTION_ORDERS_PATH}${query ? `?${query}` : ""}`);
}

// Orders for a picker: searched on the server (number or product), at most `limit`; `ids` names the chosen ones.
export function lookupProductionOrders({ search = "", statuses = [], ids = [], limit = 20 }: { search?: string; statuses?: string[]; ids?: string[]; limit?: number } = {}) {
  const query = new URLSearchParams([["search", search], ["limit", String(limit)], ...statuses.map(s => ["statuses", s]), ...ids.map(id => ["ids", id])]);
  return apiClient<ProductionOrderListItem[]>(`${PRODUCTION_ORDERS_PATH}/lookup?${query}`);
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

// Demand items an open order may take, searched on the server (demand number or customer), at most `limit`:
// never a first page of demands filtered in the browser.
export type EligibleDemandItem = { production_demand_item_id: string; production_demand_id: string; demand_number: string; customer_name: string | null;
  line_no: number; product_type: string | null; unit: string; target_spec_json: Record<string, unknown> | null; required_quantity: string;
  remaining_quantity: string; priority: string | null; requested_delivery_date: string | null };

export function getEligibleDemandItems(productionOrderId: string, search = "", limit = 20) {
  const query = new URLSearchParams([["search", search], ["limit", String(limit)]]);
  return apiClient<EligibleDemandItem[]>(`/production/orders/${productionOrderId}/eligible-demand-items?${query}`);
}

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
