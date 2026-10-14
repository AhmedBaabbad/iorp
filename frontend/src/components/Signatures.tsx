"use client";
/**
 * The signed approval steps of a document (PROJECT-GOV-004): who signed each, when, and on whose behalf when it was
 * signed under a delegation. Read from the server, which shows them only to who may read the document itself.
 */
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { useFormatter } from "@/hooks/useFormatter";
import { apiClient } from "@/lib/api-client";

type Signature = { step: string; signer_name: string; authority_name: string; delegated: boolean; signed_at: string; notes: string | null };

/** `version` changes when the document changes (its status), so a new signature shows at once. */
export function Signatures({ resourceType, id, version }: { resourceType: string; id: string; version?: unknown }) {
  const t = useTranslations("administration.signatures");
  const fmt = useFormatter();
  const [rows, setRows] = useState<Signature[]>([]);
  useEffect(() => {
    let live = true;
    Promise.resolve().then(() => apiClient<Signature[]>(`/approvals/${resourceType}/${id}`))
      .then((r) => { if (live) setRows(Array.isArray(r) ? r : []); }).catch(() => { if (live) setRows([]); });
    return () => { live = false; };
  }, [resourceType, id, version]);
  if (!rows.length) return null;
  return <section aria-label={t("title")} style={{ background: "var(--surface)", border: "1px solid var(--border-strong)", borderRadius: 8, padding: 16, marginTop: 16 }}>
    <h2 style={{ margin: "0 0 8px", fontSize: 16 }}>{t("title")}</h2>
    <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "grid", gap: 6 }}>
      {rows.map((s, n) => <li key={n} style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        <strong>{t.has(`steps.${s.step}`) ? t(`steps.${s.step}`) : s.step}:</strong>
        <span>{s.delegated ? t("onBehalfOf", { signer: s.signer_name, authority: s.authority_name }) : t("signedBy", { signer: s.signer_name })}</span>
        <span style={{ color: "var(--text-muted)" }}>{fmt.dateTime(s.signed_at)}</span>
      </li>)}
    </ul>
  </section>;
}
