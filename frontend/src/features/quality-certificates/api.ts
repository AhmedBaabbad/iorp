import { apiClient } from "@/lib/api-client";
import type { Page } from "@/lib/pagination";
import type { Certificate, CertificateListItem, CertificateSources, CertificateStatus, CertificateUpdate, QualitySettings } from "./types";

const PATH = "/quality/quality-certificates";

// One page of certificates (ARCH-PAGE-001): the filters plus page and page_size.
export function getCertificates(filters: { status?: CertificateStatus | ""; search?: string; quality_check_id?: string; page?: string | number; page_size?: string | number } = {}) {
  const query = new URLSearchParams(Object.entries(filters).filter(([, v]) => Boolean(v)).map(([k, v]) => [k, String(v)]));
  return apiClient<Page<CertificateListItem>>(`${PATH}${query.size ? `?${query}` : ""}`);
}
export const getCertificate = (id: string) => apiClient<Certificate>(`${PATH}/${id}`);
// Whether a closed inspection can be certified, and the customers its lot was made for.
export const getCertificateSources = (checkId: string) => apiClient<CertificateSources>(`${PATH}/sources?check_id=${checkId}`);
export const createCertificate = (body: { quality_check_id: string; customer_id?: string | null; customer_po?: string | null }) =>
  apiClient<Certificate>(PATH, { method: "POST", body });
export const updateCertificate = (id: string, body: CertificateUpdate) => apiClient<Certificate>(`${PATH}/${id}`, { method: "PATCH", body });
// Approves and numbers the certificate; it becomes final.
export const issueCertificate = (id: string) => apiClient<Certificate>(`${PATH}/${id}/issue`, { method: "POST" });
export const revokeCertificate = (id: string, reason: string) => apiClient<Certificate>(`${PATH}/${id}/revoke`, { method: "POST", body: { reason } });
// A corrected draft; issuing it revokes the certificate it supersedes.
export const replaceCertificate = (id: string) => apiClient<Certificate>(`${PATH}/${id}/replace`, { method: "POST" });

export const getQualitySettings = () => apiClient<QualitySettings>("/quality/quality-settings");
export const updateQualitySettings = (body: Partial<QualitySettings>) => apiClient<QualitySettings>("/quality/quality-settings", { method: "PATCH", body });

export async function downloadCertificate(id: string, lang: "ar" | "en") {
  const response = await apiClient<Response>(`${PATH}/${id}/document.pdf?lang=${lang}`, { raw: true });
  const disposition = response.headers.get("content-disposition") ?? "";
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = encoded ? decodeURIComponent(encoded) : `COA-${lang}.pdf`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
