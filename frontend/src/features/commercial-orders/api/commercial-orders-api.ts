import { apiClient } from "@/lib/api-client";
import type {
  CommercialOrderData,
  CommercialOrderListItem,
  CreateCommercialOrderRequest,
  OrderDeletionImpact,
  UpdateCommercialOrderRequest,
} from "../types";

const ORDERS_PATH = "/commercial/orders";
const CUSTOMERS_PATH = "/commercial/customers";

export function listCommercialOrders() {
  return apiClient<CommercialOrderListItem[]>(ORDERS_PATH);
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
