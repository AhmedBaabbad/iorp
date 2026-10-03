import { apiClient } from "@/lib/api-client";
import type { CreateQuoteRequest, QuoteData, QuoteDeletionImpact, QuoteListItem, QuoteSampleOption, QuoteSettings, UpdateQuoteRequest } from "../types";

const QUOTES_PATH = "/commercial/quotes";
const CUSTOMERS_PATH = "/commercial/customers";

export function listQuotes() {
  return apiClient<QuoteListItem[]>(QUOTES_PATH);
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

export function getQuoteDeletionImpact(quoteId: string) {
  return apiClient<QuoteDeletionImpact>(`${QUOTES_PATH}/${quoteId}/deletion-impact`);
}

export function getQuoteSettings() {
  return apiClient<QuoteSettings>("/commercial/quote-settings");
}

export function updateQuoteSettings(payload: QuoteSettings) {
  return apiClient<QuoteSettings>("/commercial/quote-settings", { method: "PUT", body: payload });
}

/** Downloads the quotation document (PDF) in the chosen language, named as the server suggests. */
export async function downloadQuoteDocument(quoteId: string, lang: "ar" | "en") {
  const response = await apiClient<Response>(`${QUOTES_PATH}/${quoteId}/document.pdf?lang=${lang}`, { raw: true });
  const disposition = response.headers.get("content-disposition") ?? "";
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = encoded ? decodeURIComponent(encoded) : `quotation-${lang}.pdf`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
