"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { createOrderFromQuote } from "@/features/commercial-orders/api/commercial-orders-api";
import { StatusHistory, salesErrorMessage } from "@/features/commercial-orders/components/sales-lifecycle";
import { ReasonDialog } from "@/features/production-demands/reason-dialog";
import s from "@/features/production-demands/demands.module.css";
import { quoteStep } from "../api/quotes-api";
import type { QuoteData } from "../types";

type Step = "issue" | "accept" | "reject" | "expire" | "revise";

/**
 * A quotation's next step (SALES-001): a draft is edited and issued; the customer accepts or rejects it; an issued,
 * rejected or expired one goes back to a draft as a new revision. An accepted quotation is final and becomes a sales order.
 */
export function QuoteLifecycle({ quote, onChange }: { quote: QuoteData; onChange: (quote: QuoteData) => void }) {
  const router = useRouter();
  const t = useTranslations("commercial.quotes.lifecycle");
  const errors = useTranslations("commercial.salesErrors");
  const messages = useTranslations("messages");
  const enums = useTranslations("enums.commercialOrder.status");
  const [dialog, setDialog] = useState<"reject" | "revise" | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const actions = quote.allowed_actions ?? [];

  async function step(action: Step, reason?: string) {
    setBusy(action); setError("");
    try { onChange(await quoteStep(quote.id, action, reason)); setDialog(null); }
    catch (e) { setError(salesErrorMessage(e, errors, messages)); } finally { setBusy(null); }
  }

  async function makeOrder() {
    setBusy("create_order"); setError("");
    try { const order = await createOrderFromQuote(quote.id); router.push(`/commercial-orders/${order.id}`); }
    catch (e) { setError(salesErrorMessage(e, errors, messages)); setBusy(null); }
  }

  const button = (action: Step, primary = false) => actions.includes(action) && (
    <button type="button" className={`${s.button} ${primary ? s.primary : ""}`} disabled={busy !== null}
      onClick={() => (action === "reject" || action === "revise" ? setDialog(action) : void step(action))}>
      {busy === action ? messages("loading.saving") : t(`actions.${action}`)}
    </button>
  );

  return (
    <>
      <section className={s.panel} aria-label={t("title")}>
        <div className={s.actions} style={{ justifyContent: "space-between" }}>
          <span className={s.actions}>
            <span className={s.badge}>{t("revision", { number: quote.revision ?? 1 })}</span>
            <span className={s.muted}>{t(`hints.${quote.status}`)}</span>
          </span>
          <span className={s.actions}>
            {actions.includes("edit") && <Link href={`/quotes/${quote.id}/edit`} className={s.button}>{t("actions.edit")}</Link>}
            {button("issue", true)}{button("accept", true)}{button("reject")}{button("expire")}{button("revise")}
            {actions.includes("create_order") && (
              <button type="button" className={`${s.button} ${s.primary}`} disabled={busy !== null} onClick={() => void makeOrder()}>
                {busy === "create_order" ? messages("loading.saving") : t("actions.create_order")}
              </button>
            )}
          </span>
        </div>
        {(quote.orders ?? []).length > 0 && (
          <p style={{ marginBottom: 0 }}>
            <strong>{t("orders")}:</strong>{" "}
            {(quote.orders ?? []).map((o, i) => (
              <span key={o.id}>{i > 0 && " · "}<Link href={`/commercial-orders/${o.id}`}><bdi>{o.order_number}</bdi></Link>
                {" "}({enums.has(o.status) ? enums(o.status) : o.status})</span>
            ))}
          </p>
        )}
        {error && <p role="alert" className={s.error} style={{ marginBottom: 0 }}>{error}</p>}
      </section>
      <StatusHistory entries={quote.history ?? []} />
      {dialog === "reject" && (
        <ReasonDialog title={t("rejectTitle")} description={t("rejectText")} confirmLabel={t("actions.reject")} danger busy={busy !== null}
          onClose={() => setDialog(null)} onConfirm={(reason) => void step("reject", reason)} />
      )}
      {dialog === "revise" && (
        <ReasonDialog title={t("reviseTitle")} description={t("reviseText")} confirmLabel={t("actions.revise")} busy={busy !== null}
          onClose={() => setDialog(null)} onConfirm={(reason) => void step("revise", reason)} />
      )}
    </>
  );
}
