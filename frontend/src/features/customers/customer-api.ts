import { apiClient } from "@/lib/api-client";
import type {
  CustomerCreateRequest,
  CustomerDetail,
  CustomerListItem,
} from "@/types/customers";

const CUSTOMERS_PATH = "/commercial/customers";

export function listCustomers() {
  return apiClient<CustomerListItem[]>(CUSTOMERS_PATH);
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
