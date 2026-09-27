import { apiClient } from "@/lib/api-client";

export type DemandStatus = "draft" | "ready_for_planning" | "partially_planned" | "planned" | "cancelled";
export type DemandPriority = "low" | "normal" | "high" | "urgent";
export type Customer = { id: string; code: string; name: string };
export type Quote = { id: string; number: string; status: string };
export type AllocationStatus = "active" | "released";
export type DemandItemAllocation = { id: string; production_order_id: string; production_order_number: string; production_order_status: string; allocated_quantity: string; status: AllocationStatus; created_at: string; released_at: string | null; release_reason: string | null };
export type PlanningState = "ready_for_planning" | "partially_planned" | "planned";
export type Item = { allocated_quantity?: string; active_allocated_quantity?: string; released_allocated_quantity?: string; remaining_quantity?: string; planning_state?: PlanningState; allocations?: DemandItemAllocation[]; id?: string; line_no?: number; product_type: string | null; target_spec_json: Record<string, unknown> | null; required_quantity: string; unit: string; notes: string | null };
export type Demand = { total_required: string; total_allocated: string; total_active_allocated: string; total_released_allocated: string; total_remaining: string; allocation_percentage: string; id: string; demand_number: string; customer: Customer; quote: Quote | null; request_date: string; requested_delivery_date: string | null; priority: DemandPriority; status: DemandStatus; planning_sequence: number | null; notes: string | null; item_count: number; total_quantity: string; quantities_by_unit: Record<string, string>; created_by: string | null; created_at: string; updated_at: string; items: Item[]; spec_summary?: Record<string, unknown> | null };
export type DemandInput = { customer_id: string; quote_id: string | null; request_date: string; requested_delivery_date: string | null; priority: DemandPriority; notes: string | null; items: Item[] };
export type Page = { items: Demand[]; total: number; page: number; page_size: number };
export type ReleaseResult = { allocation: { id: string; status: AllocationStatus; released_at: string | null; release_reason: string | null }; demand: { id: string; status: DemandStatus; total_remaining: string } };
const root = "/production";
export const demandsApi = {
  list: (query: string, planning = false) => apiClient<Page>(`${root}/${planning ? "planning/demands" : "demands"}?${query}`),
  get: (id: string) => apiClient<Demand>(`${root}/demands/${id}`),
  save: (data: DemandInput, id?: string) => apiClient<Demand>(`${root}/demands${id ? `/${id}` : ""}`, { method: id ? "PATCH" : "POST", body: data }),
  status: (id: string, status: DemandStatus) => apiClient<Demand>(`${root}/demands/${id}/status`, { method: "POST", body: { status } }),
  remove: (id: string) => apiClient(`${root}/demands/${id}`, { method: "DELETE" }),
  // Gives an ACTIVE allocation back to its demand; the allocation stays as RELEASED history.
  releaseAllocation: (allocationId: string, reason: string) => apiClient<ReleaseResult>(`${root}/allocations/${allocationId}/release`, { method: "POST", body: { reason } }),
  reorder: (id: string, new_position: number) => apiClient(`${root}/planning/demands/${id}/reorder`, { method: "POST", body: { new_position } }),
  customers: (search = "") => apiClient<Customer[]>(`${root}/demand-lookups/customers?search=${encodeURIComponent(search)}`),
  quotes: (customerId: string) => apiClient<Quote[]>(`${root}/demand-lookups/quotes?customer_id=${customerId}`),
  quoteItems: (quoteId: string, customerId: string) => apiClient<Item[]>(`${root}/demand-lookups/quotes/${quoteId}/items?customer_id=${customerId}`),
};
