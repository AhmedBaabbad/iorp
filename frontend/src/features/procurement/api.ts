import { apiClient } from "@/lib/api-client";
import type { Material, MaterialInput, Receipt, ReceiptInput, ReceiptListItem, ReceiptStatus, Supplier, SupplierInput, SupplierOption, SupplierStatus } from "./types";

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
export const getProcurementSettings = () => apiClient<{ receipt_prefix: string }>(`${ROOT}/settings`);
export const updateProcurementSettings = (receipt_prefix: string) =>
  apiClient<{ receipt_prefix: string }>(`${ROOT}/settings`, { method: "PATCH", body: { receipt_prefix } });

export async function downloadReceiptNote(id: string, lang: "ar" | "en") {
  const response = await apiClient<Response>(`${ROOT}/receipts/${id}/document.pdf?lang=${lang}`, { raw: true });
  const disposition = response.headers.get("content-disposition") ?? "";
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = encoded ? decodeURIComponent(encoded) : `goods-receipt-${lang}.pdf`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
