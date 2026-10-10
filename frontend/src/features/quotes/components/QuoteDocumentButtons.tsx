"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { sharedStyles } from "@/styles/shared-styles";
import { downloadQuoteDocument } from "../api/quotes-api";

/** Download the quotation document (PDF), printed in the language chosen in the quotation settings. */
export function QuoteDocumentButtons({ quoteId }: { quoteId: string }) {
  const t = useTranslations("commercial.quotes.document");
  const messages = useTranslations("messages");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function download() {
    setBusy(true); setError(null);
    try { await downloadQuoteDocument(quoteId); }
    catch (caught) { setError(getApiErrorMessage(caught, messages)); }
    finally { setBusy(false); }
  }

  return (
    <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" }}>
      <button type="button" style={sharedStyles.button} disabled={busy} onClick={() => void download()}>{busy ? t("preparing") : t("download")}</button>
      {error ? <span role="alert" style={{ color: "var(--danger)" }}>{error}</span> : null}
    </div>
  );
}
