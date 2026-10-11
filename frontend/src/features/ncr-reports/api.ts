import { apiClient } from "@/lib/api-client";
import type { Page } from "@/lib/pagination";
import type { CapaAlerts, CorrectiveAction, NcrAttachment, NcrCreateInput, NcrHeader, NcrItemInput, NcrListItem, NcrReport, NcrSeverity, NcrSourceType, NcrStatus,
  UserOption } from "./types";

const PATH = "/quality/non-conformance-reports";

const query = (filters: Record<string, string | boolean | undefined>) => {
  const q = new URLSearchParams(Object.entries(filters).filter(([, v]) => Boolean(v)).map(([k, v]) => [k, String(v)]));
  return q.size ? `?${q}` : "";
};

export type NcrFilters = { status?: NcrStatus | ""; source_type?: NcrSourceType | ""; severity?: NcrSeverity | ""; open_only?: boolean; search?: string;
  date_from?: string; date_to?: string };
// One page of reports (ARCH-PAGE-001): the filters plus page and page_size.
export const getNcrReports = (filters: NcrFilters & Record<string, string | boolean | undefined> = {}) => apiClient<Page<NcrListItem>>(`${PATH}${query(filters)}`);
export const getNcrReport = (id: string) => apiClient<NcrReport>(`${PATH}/${id}`);
export const createNcrReport = (body: NcrCreateInput) => apiClient<NcrReport>(PATH, { method: "POST", body });
export const updateNcrReport = (id: string, body: Partial<NcrHeader>) => apiClient<NcrReport>(`${PATH}/${id}`, { method: "PATCH", body });
export const getNcrSuppliers = (search = "") =>
  apiClient<{ id: string; supplier_code: string; name: string; status: string }[]>(`${PATH}/lookups/suppliers?q=${encodeURIComponent(search)}`);
export const getNcrUsers = (search = "") => apiClient<UserOption[]>(`${PATH}/lookups/users?q=${encodeURIComponent(search)}`);

// Stages: contained, root cause found (then actions, or closed when none is needed), actions finished, verified, cancelled.
const step = <B,>(id: string, name: string, body?: B) => apiClient<NcrReport>(`${PATH}/${id}/${name}`, { method: "POST", body });
export const containNcr = (id: string, containment: string) => step(id, "contain", { containment });
export type InvestigateBody = { root_cause_category: string; root_cause_method: string | null; root_cause: string; action_required: boolean;
  no_action_justification: string | null };
export const investigateNcr = (id: string, body: InvestigateBody) => step(id, "investigate", body);
export const submitNcr = (id: string) => step(id, "submit");
export const verifyNcr = (id: string, effective: boolean, notes: string | null, review_days = 0) => step(id, "verify", { effective, notes, review_days });
// Some time after closing: the problem did not come back (effective), or it did and the report reopens to its actions.
export const reviewNcrEffectiveness = (id: string, effective: boolean, notes: string | null) => step(id, "review-effectiveness", { effective, notes });
export const cancelNcr = (id: string, reason: string) => step(id, "cancel", { reason });

export const addNcrItem = (id: string, body: NcrItemInput) => apiClient<NcrReport>(`${PATH}/${id}/items`, { method: "POST", body });
export const updateNcrItem = (id: string, itemId: string, body: Partial<NcrItemInput>) =>
  apiClient<NcrReport>(`${PATH}/${id}/items/${itemId}`, { method: "PATCH", body });
export const removeNcrItem = (id: string, itemId: string) => apiClient<NcrReport>(`${PATH}/${id}/items/${itemId}`, { method: "DELETE" });

export type ActionBody = { kind: string; description: string; owner_user_id: string | null; owner_name: string | null; due_date: string | null };
export const addNcrAction = (id: string, body: ActionBody) => apiClient<NcrReport>(`${PATH}/${id}/actions`, { method: "POST", body });
export const completeNcrAction = (id: string, actionId: string, evidence: string) =>
  apiClient<NcrReport>(`${PATH}/${id}/actions/${actionId}/complete`, { method: "POST", body: { evidence } });
export const cancelNcrAction = (id: string, actionId: string, reason: string) =>
  apiClient<NcrReport>(`${PATH}/${id}/actions/${actionId}/cancel`, { method: "POST", body: { reason } });

// Corrective actions across reports (the CAPA list).
export type ActionFilters = { status?: "open" | "done" | "cancelled" | ""; mine?: boolean; overdue?: boolean; search?: string };
export const getCorrectiveActions = (filters: ActionFilters & Record<string, string | boolean | undefined> = {}) =>
  apiClient<Page<CorrectiveAction>>(`/quality/ncr-actions${query(filters)}`);
export const getCapaAlerts = () => apiClient<CapaAlerts>("/quality/ncr-actions/alerts");

export function uploadNcrAttachment(id: string, file: File) {
  const body = new FormData();
  body.append("file", file);
  return apiClient<NcrAttachment[]>(`${PATH}/${id}/attachments`, { method: "POST", body });
}
export const removeNcrAttachment = (id: string, attachmentId: string) =>
  apiClient<NcrAttachment[]>(`${PATH}/${id}/attachments/${attachmentId}`, { method: "DELETE" });
export async function openNcrAttachment(id: string, attachment: NcrAttachment) {
  const response = await apiClient<Response>(`${PATH}/${id}/attachments/${attachment.id}`, { raw: true });
  const url = URL.createObjectURL(await response.blob());
  window.open(url, "_blank", "noopener");
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}
export async function downloadNcrDocument(id: string, lang: "ar" | "en") {
  const response = await apiClient<Response>(`${PATH}/${id}/document.pdf?lang=${lang}`, { raw: true });
  const disposition = response.headers.get("content-disposition") ?? "";
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = encoded ? decodeURIComponent(encoded) : `ncr-${lang}.pdf`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
