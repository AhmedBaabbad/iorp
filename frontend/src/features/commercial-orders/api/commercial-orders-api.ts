import { apiClient } from "@/lib/api-client";
import type { Page } from "@/lib/pagination";
import type {
  CommercialOrderData,
  CommercialOrderListItem,
  CreateCommercialOrderRequest,
  OrderDeletionImpact,
  UpdateCommercialOrderRequest,
} from "../types";

const ORDERS_PATH = "/commercial/orders";
const CUSTOMERS_PATH = "/commercial/customers";

/** One page of sales orders, searched and filtered by the server: query = "page=2&search=PO-55&status=confirmed". */
export function listCommercialOrders(query = "") {
  return apiClient<Page<CommercialOrderListItem>>(query ? `${ORDERS_PATH}?${query}` : ORDERS_PATH);
}

export function getCommercialOrderById(orderId: string) {
  return apiClient<CommercialOrderData>(`${ORDERS_PATH}/${orderId}`);
}

export function createCommercialOrder(payload: CreateCommercialOrderRequest) {
  const { customer_id, ...body } = payload;

  return apiClient<CommercialOrderData>(`${CUSTOMERS_PATH}/${customer_id}/orders`, {
    method: "POST",
    body,
  });
}

export function updateCommercialOrder(orderId: string, payload: UpdateCommercialOrderRequest) {
  return apiClient<CommercialOrderData>(`${ORDERS_PATH}/${orderId}`, {
    method: "PATCH",
    body: payload,
  });
}

export function deleteCommercialOrder(orderId: string) {
  return apiClient<void>(`${ORDERS_PATH}/${orderId}`, { method: "DELETE" });
}

export function getOrderDeletionImpact(orderId: string) {
  return apiClient<OrderDeletionImpact>(`${ORDERS_PATH}/${orderId}/deletion-impact`);
}

/** Locks the order: production works from it from now on (SALES-001). */
export function confirmCommercialOrder(orderId: string) {
  return apiClient<CommercialOrderData>(`${ORDERS_PATH}/${orderId}/confirm`, { method: "POST" });
}

/** Back to a draft as a new revision, only while nothing of it is with production. */
export function reviseCommercialOrder(orderId: string, reason: string) {
  return apiClient<CommercialOrderData>(`${ORDERS_PATH}/${orderId}/revise`, { method: "POST", body: { reason } });
}

export function cancelCommercialOrder(orderId: string, reason: string) {
  return apiClient<CommercialOrderData>(`${ORDERS_PATH}/${orderId}/cancel`, { method: "POST", body: { reason } });
}

/** A draft sales order with the accepted quotation's lines, specifications, prices and currency. */
export function createOrderFromQuote(quoteId: string) {
  return apiClient<CommercialOrderData>(`/commercial/quotes/${quoteId}/sales-order`, { method: "POST" });
}
