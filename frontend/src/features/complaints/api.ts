import { apiClient } from '@/lib/api-client';
import type { Page } from '@/lib/pagination';

export const root = '/commercial/complaints';

/** A product of the catalogue and the properties a complaint line can name. */
export type CatalogueProperty = { key: string; name_ar: string; name_en: string; unit: string | null; kind: string };
export type Product = { key: string; name_ar: string; name_en: string; default_unit: string | null; properties: CatalogueProperty[] };

/** A sales order line or a sample of the customer; its agreed specification is copied onto the complaint line. */
export type Source = { kind: 'order' | 'sample'; id: string; label: string; product_key: string; unit: string | null; quantity: string | null;
  spec: Record<string, string> };

export type ItemProperty = { key: string; name_ar: string; name_en: string; unit: string | null; expected: string; reported: string; measured: string };
export type Item = { id: string; line_no: number; product_key: string; product_name: string; batch_reference: string | null; unit: string;
  delivered_quantity: string; reported_quantity: string; confirmed_quantity: string | null; source_kind: 'order' | 'sample' | 'manual';
  source_id: string | null; source_label: string | null; properties: ItemProperty[] };

/** A line as the forms send it: an existing line keeps its id (and so its measurements). */
export type ItemDraft = { id?: string; product_key: string; source_kind: 'order' | 'sample' | 'manual'; source_id: string | null;
  batch_reference: string; unit: string; delivered_quantity: string; reported_quantity: string;
  properties: { key: string; expected: string; reported: string }[] };

/** A decision: its facts by name (`details`) and what the person wrote (`notes`). */
export type ComplaintEvent = { id: string; action: string; notes: string; details: Record<string, unknown>; actor_name: string | null; created_at: string };

export type Complaint = { id: string; number: string; title: string; statement: string; customer_id: string; customer_name: string;
  contact: string | null; channel: string; category: string; priority: string; status: string; version: number; department: string;
  owner_name: string | null; owner_user_id: string | null; received_date: string; due_date: string | null; response_due_date: string | null;
  external_reference: string | null; finding: string; investigation: string | null; containment: string | null;
  resolution: string | null; implementation_evidence: string | null; customer_response: string | null; overdue: boolean; actions: string[];
  items: Item[]; events: ComplaintEvent[]; links: { kind: string; label: string; href: string; record_id: string }[];
  attachments: { id: string; filename: string }[] };

export const listComplaints = (query: string) => apiClient<Page<Complaint>>(`${root}?${query}`);
export const getComplaint = (id: string) => apiClient<Complaint>(`${root}/${id}`);
export const createComplaint = (body: unknown) => apiClient<Complaint>(root, { method: 'POST', body });
export const changeComplaint = (id: string, operation: string, body: unknown) => apiClient<Complaint>(`${root}/${id}/${operation}`, { method: 'POST', body });
export const saveItems = (id: string, body: unknown) => apiClient<Complaint>(`${root}/${id}/items`, { method: 'PUT', body });
export const listProducts = () => apiClient<Product[]>(`${root}/products`);
export const listSources = (customerId: string) => apiClient<Source[]>(`${root}/sources?customer_id=${encodeURIComponent(customerId)}`);
