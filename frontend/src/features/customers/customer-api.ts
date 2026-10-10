import { apiClient } from "@/lib/api-client";
import type {
  CustomerCreateRequest,
  CustomerDeletionImpact,
  CustomerDetail,
  CustomerListItem,
  CustomerUpdateRequest,
  CustomerOption,
  EligibleSalesOwner,
} from "@/types/customers";
import type { Page } from "@/lib/pagination";

const CUSTOMERS_PATH = "/commercial/customers";

/** One page of customers, searched and filtered by the server: query = "page=2&page_size=50&search=gulf&status=active". */
export function listCustomers(query = "") {
  return apiClient<Page<CustomerListItem>>(query ? `${CUSTOMERS_PATH}?${query}` : CUSTOMERS_PATH);
}

/** The first customers whose code or name matches, for choosing one (never the whole list). */
export function lookupCustomers(search: string, limit = 20) {
  const query = new URLSearchParams({ limit: String(limit), ...(search.trim() ? { search: search.trim() } : {}) });
  return apiClient<CustomerOption[]>(`${CUSTOMERS_PATH}/lookup?${query}`);
}

/** The named customers (to show their names on a list), 100 per request. */
export async function customersByIds(ids: string[]) {
  const unique = [...new Set(ids.filter(Boolean))];
  const chunks = Array.from({ length: Math.ceil(unique.length / 100) }, (_, i) => unique.slice(i * 100, i * 100 + 100));
  const answers = await Promise.all(chunks.map((chunk) =>
    apiClient<CustomerOption[]>(`${CUSTOMERS_PATH}/lookup?${new URLSearchParams(chunk.map((id) => ["ids", id]))}`)));
  return answers.flat();
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
