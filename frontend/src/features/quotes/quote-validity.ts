"use client";
import { useEffect, useState } from "react";
import { apiClient, ApiClientError } from "@/lib/api-client";
import { toDatetimeLocalValue } from "@/lib/utils";

export function quoteValidUntil(issue: string, days: number): string {
  const date = new Date(issue);
  return Number.isNaN(date.getTime()) ? "" : toDatetimeLocalValue(new Date(date.getTime() + days * 86400000));
}
export function useQuoteValidity() {
  const [days, setDays] = useState(10);
  const [documentLanguage, setDocumentLanguage] = useState<"ar" | "en" | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    let live = true;
    apiClient<{ quote_validity_days: number; document_language: "ar" | "en" }>("/commercial/quote-settings/validity").then(data => {
      if (live) { setDays(data.quote_validity_days ?? 10); setDocumentLanguage(data.document_language); setLoaded(true); }
    }).catch(error => { if (live) setError(error); });
    return () => { live = false; };
  }, []);
  return { days, error, loaded, documentLanguage };
}
export function quoteValidityError(error: unknown): number | null {
  if (!(error instanceof ApiClientError)) return null;
  const body = error.details as { detail?: { code?: string; quote_validity_days?: number } } | undefined;
  return body?.detail?.code === "QUOTE_VALIDITY_EXCEEDED" ? body.detail.quote_validity_days ?? 10 : null;
}
