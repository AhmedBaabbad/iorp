import { apiClient } from "@/lib/api-client";
import type { Material, MaterialInput, OpenOrder, Order, OrderInput, OrderListItem, OrderStatus, ProcurementSettings, Receipt, ReceiptInput, ReceiptListItem,
  ReceiptStatus, Supplier, SupplierInput, SupplierOption, SupplierStatus } from "./types";

const ROOT = "/procurement";

const query = (filters: Record<string, string | boolean | undefined>) => {
  const q = new URLSearchParams(Object.entries(filters).filter(([, v]) => Boolean(v)).map(([k, v]) => [k, String(v)]));
  return q.size ? `?${q}` : "";
};

// Suppliers and their standing on the approved list.
export type SupplierFilters = { status?: SupplierStatus | ""; category?: string; search?: string };
export const getSuppliers = (filters: SupplierFilters = {}) => apiClient<Supplier[]>(`${ROOT}/suppliers${query(filters)}`);
export const getSupplier = (id: string) => apiClient<Supplier>(`${ROOT}/suppliers/${id}`);
export const getSupplierOptions = (search = "") => apiClient<SupplierOption[]>(`${ROOT}/suppliers/lookup?q=${encodeURIComponent(search)}`);
export const createSupplier = (body: SupplierInput) => apiClient<Supplier>(`${ROOT}/suppliers`, { method: "POST", body });
export const updateSupplier = (id: string, body: Partial<SupplierInput>) => apiClient<Supplier>(`${ROOT}/suppliers/${id}`, { method: "PATCH", body });
export const setSupplierStatus = (id: string, status: Exclude<SupplierStatus, "pending">, reason: string | null) =>
  apiClient<Supplier>(`${ROOT}/suppliers/${id}/status`, { method: "POST", body: { status, reason } });

export const getMaterials = (filters: { category?: string; search?: string; active_only?: boolean } = {}) =>
  apiClient<Material[]>(`${ROOT}/materials${query(filters)}`);
export const createMaterial = (body: MaterialInput) => apiClient<Material>(`${ROOT}/materials`, { method: "POST", body });
export const updateMaterial = (id: string, body: Partial<MaterialInput>) => apiClient<Material>(`${ROOT}/materials/${id}`, { method: "PATCH", body });

// Goods receipts: draft, received (final), cancelled.
export type ReceiptFilters = { status?: ReceiptStatus | ""; supplier_id?: string; date_from?: string; date_to?: string; search?: string };
export const getReceipts = (filters: ReceiptFilters = {}) => apiClient<ReceiptListItem[]>(`${ROOT}/receipts${query(filters)}`);
export const getReceipt = (id: string) => apiClient<Receipt>(`${ROOT}/receipts/${id}`);
export const createReceipt = (body: ReceiptInput) => apiClient<Receipt>(`${ROOT}/receipts`, { method: "POST", body });
export const updateReceipt = (id: string, body: Partial<ReceiptInput>) => apiClient<Receipt>(`${ROOT}/receipts/${id}`, { method: "PATCH", body });
export const receiveReceipt = (id: string) => apiClient<Receipt>(`${ROOT}/receipts/${id}/receive`, { method: "POST" });
export const cancelReceipt = (id: string, reason: string) => apiClient<Receipt>(`${ROOT}/receipts/${id}/cancel`, { method: "POST", body: { reason } });
export const getProcurementSettings = () => apiClient<ProcurementSettings>(`${ROOT}/settings`);
export const updateProcurementSettings = (body: Partial<ProcurementSettings>) =>
  apiClient<ProcurementSettings>(`${ROOT}/settings`, { method: "PATCH", body });

async function download(path: string, fallback: string) {
  const response = await apiClient<Response>(path, { raw: true });
  const disposition = response.headers.get("content-disposition") ?? "";
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = encoded ? decodeURIComponent(encoded) : fallback;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const downloadReceiptNote = (id: string, lang: "ar" | "en") => download(`${ROOT}/receipts/${id}/document.pdf?lang=${lang}`, `goods-receipt-${lang}.pdf`);

// Purchase orders (PROC-003): draft, approved, sent, partially received, received; closed or cancelled with a reason.
export type OrderFilters = { status?: OrderStatus | ""; supplier_id?: string; date_from?: string; date_to?: string; search?: string };
export const getOrders = (filters: OrderFilters = {}) => apiClient<OrderListItem[]>(`${ROOT}/purchase-orders${query(filters)}`);
export const getOrder = (id: string) => apiClient<Order>(`${ROOT}/purchase-orders/${id}`);
export const createOrder = (body: OrderInput) => apiClient<Order>(`${ROOT}/purchase-orders`, { method: "POST", body });
export const updateOrder = (id: string, body: Partial<OrderInput>) => apiClient<Order>(`${ROOT}/purchase-orders/${id}`, { method: "PATCH", body });
const orderStep = (id: string, name: string, body?: unknown) => apiClient<Order>(`${ROOT}/purchase-orders/${id}/${name}`, { method: "POST", body });
export const approveOrder = (id: string) => orderStep(id, "approve");
export const sendOrder = (id: string) => orderStep(id, "send");
export const closeOrder = (id: string, reason: string) => orderStep(id, "close", { reason });
export const cancelOrder = (id: string, reason: string) => orderStep(id, "cancel", { reason });
export const getOpenOrders = (supplierId: string) => apiClient<OpenOrder[]>(`${ROOT}/purchase-orders/open-for-receipt?supplier_id=${supplierId}`);
export const downloadOrder = (id: string, lang: "ar" | "en") => download(`${ROOT}/purchase-orders/${id}/document.pdf?lang=${lang}`, `purchase-order-${lang}.pdf`);
