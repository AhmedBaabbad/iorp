import { apiClient } from "@/lib/api-client";
import type { Page } from "@/lib/pagination";
import type { CreateQuoteRequest, QuoteData, QuoteDeletionImpact, QuoteListItem, QuoteSampleOption, QuoteSettings, UpdateQuoteRequest } from "../types";

const QUOTES_PATH = "/commercial/quotes";
const CUSTOMERS_PATH = "/commercial/customers";

/** One page of quotations, searched and filtered by the server: query = "page=2&search=gulf&status=issued". */
export function listQuotes(query = "") {
  return apiClient<Page<QuoteListItem>>(query ? `${QUOTES_PATH}?${query}` : QUOTES_PATH);
}

export function listQuotesForCustomer(customerId: string) {
  return apiClient<QuoteListItem[]>(`${CUSTOMERS_PATH}/${customerId}/quotes`);
}

export function listSamplesForQuoteCustomer(customerId: string) {
  return apiClient<QuoteSampleOption[]>(`${CUSTOMERS_PATH}/${customerId}/samples`);
}

export function getQuoteById(quoteId: string) {
  return apiClient<QuoteData>(`${QUOTES_PATH}/${quoteId}`);
}

export function createQuote(payload: CreateQuoteRequest) {
  const { customer_id, ...body } = payload;

  return apiClient<QuoteData>(`${CUSTOMERS_PATH}/${customer_id}/quotes`, {
    method: "POST",
    body,
  });
}

export function updateQuote(quoteId: string, payload: UpdateQuoteRequest) {
  return apiClient<QuoteData>(`${QUOTES_PATH}/${quoteId}`, {
    method: "PATCH",
    body: payload,
  });
}

export function deleteQuote(quoteId: string) {
  return apiClient<{ status: string }>(`${QUOTES_PATH}/${quoteId}`, {
    method: "DELETE",
  });
}

/** issue · accept · reject (reason) · expire · revise (reason): the quotation's next step (SALES-001). */
export function quoteStep(quoteId: string, action: "issue" | "accept" | "reject" | "expire" | "revise", reason?: string) {
  return apiClient<QuoteData>(`${QUOTES_PATH}/${quoteId}/${action}`, {
    method: "POST",
    ...(reason !== undefined ? { body: { reason } } : {}),
  });
}

export function getQuoteDeletionImpact(quoteId: string) {
  return apiClient<QuoteDeletionImpact>(`${QUOTES_PATH}/${quoteId}/deletion-impact`);
}

export function getQuoteSettings() {
  return apiClient<QuoteSettings>("/commercial/quote-settings");
}

export function updateQuoteSettings(payload: QuoteSettings) {
  return apiClient<QuoteSettings>("/commercial/quote-settings", { method: "PUT", body: payload });
}

/** Downloads the quotation document (PDF) in the language of the quotation settings, named as the server suggests. */
export async function downloadQuoteDocument(quoteId: string) {
  const response = await apiClient<Response>(`${QUOTES_PATH}/${quoteId}/document.pdf`, { raw: true });
  const disposition = response.headers.get("content-disposition") ?? "";
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = encoded ? decodeURIComponent(encoded) : "quotation.pdf";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
