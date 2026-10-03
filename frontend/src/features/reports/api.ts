import { apiClient } from '@/lib/api-client';

export type Schema = { type?: string; enum?: string[]; default?: unknown; format?: string; title?: string; title_ar?: string; title_en?: string; widget?: string; lookup?: string; items?: Schema; anyOf?: Schema[]; $ref?: string; properties?: Record<string, Schema>; $defs?: Record<string, Schema>; required?: string[] };
export type Definition = { key: string; module?: string; audiences?: string[]; context_fields?: string[]; title_ar: string; title_en: string; default_orientation: string; params_schema: Schema; sections: { key: string; title_ar: string; title_en: string; default_enabled: boolean }[] };

export const getDefinitions = (module: string, context: Record<string, string> = {}) => apiClient<Definition[]>(`/reports/definitions?${new URLSearchParams({ module, ...context })}`);
export const getLookups = (kind: string, query: string, module: string) => apiClient<{ id: string; label: string }[]>(`/reports/${module}/lookups/${kind}?q=${encodeURIComponent(query)}`);

// Through apiClient, so an expired session refreshes exactly as for every other request.
// Errors carry the server's code as the message (e.g. REPORT_ROW_LIMIT_NARROW_FILTERS).
export async function reportRequest(key: string, format: 'preview' | 'pdf', params: Record<string, unknown>) {
  const response = await apiClient<Response>(`/reports/${key}/${format}`, { method: 'POST', body: params, raw: true });
  if (format === 'preview') return { html: await response.text() };
  const disposition = response.headers.get('content-disposition') ?? '';
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const filename = encoded ? decodeURIComponent(encoded) : 'report.pdf';
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement('a'); link.href = url; link.download = filename; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  return {};
}
