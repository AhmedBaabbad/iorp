import { apiClient } from "@/lib/api-client";
import type { CreateQuoteRequest, QuoteData, QuoteDeletionImpact, QuoteListItem, QuoteSampleOption, UpdateQuoteRequest } from "../types";

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
