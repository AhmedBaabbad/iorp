import { apiClient } from "@/lib/api-client";
import type {
  CustomerCreateRequest,
  CustomerDeletionImpact,
  CustomerDetail,
  CustomerListItem,
  CustomerUpdateRequest,
  EligibleSalesOwner,
} from "@/types/customers";

const CUSTOMERS_PATH = "/commercial/customers";

export function listCustomers() {
  return apiClient<CustomerListItem[]>(CUSTOMERS_PATH);
}

export function getEligibleSalesOwners() {
  return apiClient<EligibleSalesOwner[]>(`${CUSTOMERS_PATH}/eligible-sales-owners`);
}

export function reassignCustomersByOwner(fromUserId: string, toUserId: string) {
  return apiClient<{ from_user_id: string; to_user_id: string; reassigned_count: number }>(
    `${CUSTOMERS_PATH}/reassign-by-owner`,
    { method: "POST", body: { from_user_id: fromUserId, to_user_id: toUserId } },
  );
}

export function getCustomer(customerId: string) {
  return apiClient<CustomerDetail>(`${CUSTOMERS_PATH}/${customerId}`);
}

export function createCustomer(payload: CustomerCreateRequest) {
  return apiClient<CustomerDetail>(CUSTOMERS_PATH, {
    method: "POST",
    body: payload,
  });
}

export function updateCustomer(customerId: string, payload: CustomerUpdateRequest) {
  return apiClient<CustomerDetail>(`${CUSTOMERS_PATH}/${customerId}`, {
    method: "PATCH",
    body: payload,
  });
}

export function getCustomerDeletionImpact(customerId: string) {
  return apiClient<CustomerDeletionImpact>(`${CUSTOMERS_PATH}/${customerId}/deletion-impact`);
}

export function deleteCustomer(customerId: string) {
  return apiClient<{ status: string }>(`${CUSTOMERS_PATH}/${customerId}`, {
    method: "DELETE",
  });
}
