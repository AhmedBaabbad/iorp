import { apiClient } from "@/lib/api-client";

export type DemandStatus = "draft" | "ready_for_planning" | "partially_planned" | "planned" | "cancelled";
export type DemandPriority = "low" | "normal" | "high" | "urgent";
export type Customer = { id: string; code: string; name: string };
export type Quote = { id: string; number: string; status: string };
export type AllocationStatus = "active" | "released";
export type DemandItemAllocation = { id: string; production_order_id: string; production_order_number: string; production_order_status: string; allocated_quantity: string; status: AllocationStatus; created_at: string; released_at: string | null; release_reason: string | null };
// SALES-001: a confirmed sales order with what each line still has for production.
export type SalesOrderLine = { id: string; line_no: number; product_type: string; target_spec_json: Record<string, unknown> | null; unit: string;
  ordered_quantity: string; transferred_quantity: string; remaining_quantity: string };
export type SalesOrderOption = { id: string; number: string; quote_id: string | null; requested_delivery_date: string | null; lines: SalesOrderLine[] };
export type FromSalesOrderInput = { sales_order_id: string; transfer_key: string; lines: { order_item_id: string; quantity: string }[];
  requested_delivery_date: string | null; priority: DemandPriority; notes: string | null };
export type PlanningState = "ready_for_planning" | "partially_planned" | "planned";
export type Item = { allocated_quantity?: string; active_allocated_quantity?: string; released_allocated_quantity?: string; remaining_quantity?: string; planning_state?: PlanningState; allocations?: DemandItemAllocation[]; source_order_item_id?: string | null; id?: string; line_no?: number; product_type: string | null; target_spec_json: Record<string, unknown> | null; required_quantity: string; unit: string; notes: string | null };
export type Demand = { total_required: string; total_allocated: string; total_active_allocated: string; total_released_allocated: string; total_remaining: string; allocation_percentage: string; id: string; demand_number: string; customer: Customer; quote: Quote | null; sales_order?: { id: string; number: string | null } | null; request_date: string; requested_delivery_date: string | null; priority: DemandPriority; status: DemandStatus; planning_sequence: number | null; notes: string | null; item_count: number; total_quantity: string; quantities_by_unit: Record<string, string>; created_by: string | null; created_at: string; updated_at: string; items: Item[]; spec_summary?: Record<string, unknown> | null };
export type DemandInput = { customer_id: string; quote_id: string | null; request_date: string; requested_delivery_date: string | null; priority: DemandPriority; notes: string | null; items: Item[] };
export type Page = { items: Demand[]; total: number; page: number; page_size: number; pages?: number; hidden_by_status?: number | null };
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
  salesOrders: (customerId: string) => apiClient<SalesOrderOption[]>(`${root}/demand-lookups/sales-orders?customer_id=${customerId}`),
  fromSalesOrder: (data: FromSalesOrderInput) => apiClient<Demand>(`${root}/demands/from-sales-order`, { method: "POST", body: data }),
  // A line taken from a sales order keeps its product, specification and unit; only its quantity changes.
  saveHeader: (id: string, data: Omit<DemandInput, "items" | "customer_id" | "quote_id">) => apiClient<Demand>(`${root}/demands/${id}`, { method: "PATCH", body: data }),
  setItemQuantity: (id: string, itemId: string, required_quantity: string, notes: string | null) =>
    apiClient<Item>(`${root}/demands/${id}/items/${itemId}`, { method: "PATCH", body: { required_quantity, notes } }),
  quoteItems: (quoteId: string, customerId: string) => apiClient<Item[]>(`${root}/demand-lookups/quotes/${quoteId}/items?customer_id=${customerId}`),
};
