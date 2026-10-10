import { apiClient } from "@/lib/api-client";
import type { BusinessSettings, LegacyValue, ListItem, ListItemInput, ListName, Product, ProductInput } from "./types";

const ROOT = "/masterdata";

const query = (filters: Record<string, string | boolean | undefined>) => {
  const q = new URLSearchParams(Object.entries(filters).filter(([, v]) => Boolean(v)).map(([k, v]) => [k, String(v)]));
  return q.size ? `?${q}` : "";
};

export const getProducts = (filters: { search?: string; kind?: string; active_only?: boolean } = {}) => apiClient<Product[]>(`${ROOT}/products${query(filters)}`);
export const getProduct = (id: string) => apiClient<Product>(`${ROOT}/products/${id}`);
export const createProduct = (body: ProductInput) => apiClient<Product>(`${ROOT}/products`, { method: "POST", body });
export const updateProduct = (id: string, body: Partial<Omit<ProductInput, "key">>) => apiClient<Product>(`${ROOT}/products/${id}`, { method: "PATCH", body });
export const getLegacyValues = () => apiClient<LegacyValue[]>(`${ROOT}/products/legacy`);
export const mapLegacyValue = (value: string, product_id: string) =>
  apiClient<{ value: string; key: string; changed: Record<string, number> }>(`${ROOT}/products/legacy/map`, { method: "POST", body: { value, product_id } });
export const getBusinessSettings = () => apiClient<BusinessSettings>(`${ROOT}/settings`);
export const updateBusinessSettings = (body: Partial<Pick<BusinessSettings, "vat_rate" | "default_currency">>) =>
  apiClient<BusinessSettings>(`${ROOT}/settings`, { method: "PATCH", body });

// Reference lists (MD-002).
export const getListItems = (list?: ListName) => apiClient<ListItem[]>(`${ROOT}/lists${list ? `?list=${list}` : ""}`);
export const createListItem = (list: ListName, body: ListItemInput) => apiClient<ListItem>(`${ROOT}/lists/${list}`, { method: "POST", body });
export const updateListItem = (id: string, body: Partial<Omit<ListItem, "id" | "list" | "key">>) =>
  apiClient<ListItem>(`${ROOT}/lists/items/${id}`, { method: "PATCH", body });
export const addStandardItems = (list: ListName) => apiClient<ListItem[]>(`${ROOT}/lists/${list}/standard`, { method: "POST" });
export const getListLegacy = (list: ListName) => apiClient<LegacyValue[]>(`${ROOT}/lists/${list}/legacy`);
export const mapListLegacy = (list: ListName, value: string, item_id: string) =>
  apiClient<{ value: string; key: string; changed: Record<string, number> }>(`${ROOT}/lists/${list}/legacy/map`, { method: "POST", body: { value, item_id } });
