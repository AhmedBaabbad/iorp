"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { sharedStyles } from "@/styles/shared-styles";
import { downloadQuoteDocument } from "../api/quotes-api";

/** Download the quotation document (PDF) in Arabic or English. */
export function QuoteDocumentButtons({ quoteId }: { quoteId: string }) {
  const t = useTranslations("commercial.quotes.document");
  const messages = useTranslations("messages");
  const [busy, setBusy] = useState<"ar" | "en" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function download(lang: "ar" | "en") {
    setBusy(lang); setError(null);
    try { await downloadQuoteDocument(quoteId, lang); }
    catch (caught) { setError(getApiErrorMessage(caught, messages)); }
    finally { setBusy(null); }
  }

  return (
    <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" }}>
      {(["ar", "en"] as const).map((lang) => (
        <button key={lang} type="button" style={sharedStyles.button} disabled={busy !== null} onClick={() => void download(lang)}>
          {busy === lang ? t("preparing") : t(lang === "ar" ? "downloadAr" : "downloadEn")}
        </button>
      ))}
      {error ? <span role="alert" style={{ color: "var(--danger)" }}>{error}</span> : null}
    </div>
  );
}
