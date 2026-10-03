"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import type { CSSProperties, ReactNode } from "react";
import { useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { getCustomer } from "@/features/customers";
import { getSampleById } from "@/features/samples";
import { useFormatter } from "@/hooks/useFormatter";
import type { Locale } from "@/i18n/config";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { ApiClientError } from "@/lib/api-client";
import { displayValue } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import { getQuoteById } from "../api/quotes-api";
import type { QuoteData } from "../types";
import { QuoteItemsTable } from "./QuoteItemsTable";
import { QuoteDocumentButtons } from "./QuoteDocumentButtons";
import { QuoteStatusBadge } from "./QuoteStatusBadge";
import { QuoteTotals } from "./QuoteTotals";
import { formatCommercialCurrency } from "./quote-utils";

const styles: Record<string, CSSProperties> = {
  detailGrid: {
    display: "grid",
    gap: "1px",
    gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
    background: "var(--border)",
    borderRadius: "8px",
    overflow: "hidden",
  },
  detailItem: {
    background: "var(--surface)",
    padding: "18px",
  },
  detailLabel: {
    color: "var(--text-muted)",
    fontSize: "13px",
    fontWeight: 700,
    margin: "0 0 8px",
  },
  detailValue: {
    margin: 0,
    overflowWrap: "anywhere",
  },
  sections: {
    display: "grid",
    gap: "24px",
  },
};

export function QuoteDetail() {
  const messages = useTranslations("messages");
  const t = useTranslations("commercial.quotes");
  const locale = useLocale() as Locale;
  const fmt = useFormatter();
  const params = useParams<{ id: string }>();
  const quoteId = params.id;
  const [quote, setQuote] = useState<QuoteData | null>(null);
  const [customerName, setCustomerName] = useState<string | null>(null);
  const [sampleCode, setSampleCode] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isNotFound, setIsNotFound] = useState(false);

  useEffect(() => {
    let isMounted = true;

    async function loadQuote() {
      try {
        setIsLoading(true);
        setError(null);
        setIsNotFound(false);
        const response = await getQuoteById(quoteId);

        if (isMounted) {
          setQuote(response);
        }

        const secondaryFetches: Promise<void>[] = [
          getCustomer(response.customer_id)
            .then((customer) => {
              if (isMounted) {
                setCustomerName(customer.name);
              }
            })
            .catch(() => undefined),
        ];

        if (response.sample_id) {
          secondaryFetches.push(
            getSampleById(response.sample_id)
              .then((sample) => {
                if (isMounted) {
                  setSampleCode(sample.sample_code);
                }
              })
              .catch(() => undefined),
          );
        }

        await Promise.all(secondaryFetches);
      } catch (caughtError) {
        if (!isMounted) {
          return;
        }

        if (caughtError instanceof ApiClientError && caughtError.status === 404) {
          setIsNotFound(true);
          return;
        }

        setError(getApiErrorMessage(caughtError, messages));
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadQuote();

    return () => {
      isMounted = false;
    };
  }, [quoteId]);

  return (
    <PageFrame
      title={quote?.quote_number ?? t("detailTitle")}
      subtitle={
        quote
          ? formatCommercialCurrency(fmt.currency(quote.total_amount, quote.currency), quote.currency, locale)
          : t("detailSubtitle")
      }
      action={
        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
          {quote ? <QuoteDocumentButtons quoteId={quote.id} /> : null}
          <Link href="/quotes" style={sharedStyles.secondaryButton}>
            {t("backToList")}
          </Link>
        </div>
      }
    >
      {isLoading ? (
        <div style={{ ...sharedStyles.state, background: "var(--surface)" }}>{messages("loading.default")}</div>
      ) : null}

      {!isLoading && isNotFound ? (
        <section style={{ ...sharedStyles.state, background: "var(--surface)" }}>
          <h2 style={{ margin: "0 0 8px", fontSize: "20px" }}>{t("notFound")}</h2>
          <p style={{ margin: "0 0 18px" }}>{t("notFoundDescription")}</p>
          <Link href="/quotes" style={sharedStyles.button}>
            {t("returnToList")}
          </Link>
        </section>
      ) : null}

      {!isLoading && error ? (
        <div style={sharedStyles.error} role="alert">
          {error}
        </div>
      ) : null}

      {!isLoading && !error && !isNotFound && quote ? (
        <div style={styles.sections}>
          <section style={styles.detailGrid} aria-label={t("detailsAria")}>
            <DetailItem
              label={t("fields.quoteNumber")}
              value={`${quote.quote_number} (${t("autoGeneratedNumber")})`}
            />
            <DetailItem
              label={t("fields.status")}
              value={<QuoteStatusBadge status={quote.status} />}
            />
            <DetailItem
              label={t("fields.customer")}
              value={
                <Link href={`/customers/${quote.customer_id}`} style={{ color: "var(--accent-strong)" }}>
                  {customerName ?? quote.customer_id}
                </Link>
              }
            />
            <DetailItem
              label={t("fields.sample")}
              value={
                quote.sample_id ? (
                  <Link href={`/samples/${quote.sample_id}`} style={{ color: "var(--accent-strong)" }}>
                    {sampleCode ?? quote.sample_id}
                  </Link>
                ) : null
              }
            />
            <DetailItem label={t("fields.quoteDate")} value={fmt.date(quote.issue_date)} />
            <DetailItem label={t("fields.validUntil")} value={fmt.date(quote.valid_until)} />
            <DetailItem label={t("fields.currency")} value={quote.currency} />
            <DetailItem label={t("document.attention")} value={quote.attention ?? null} />
            <DetailItem label={t("document.subject")} value={quote.subject ?? null} />
            <DetailItem label={t("fields.notes")} value={quote.notes} />
          </section>

          <QuoteItemsTable items={quote.items} currency={quote.currency} />

          <QuoteTotals
            totals={{
              subtotal: quote.subtotal_amount,
              discount: quote.discount_amount,
              tax: quote.tax_amount,
              total: quote.total_amount,
              currency: quote.currency,
            }}
          />
        </div>
      ) : null}
    </PageFrame>
  );
}

function DetailItem({
  label,
  value,
}: {
  label: string;
  value: string | number | null | ReactNode;
}) {
  return (
    <div style={styles.detailItem}>
      <p style={styles.detailLabel}>{label}</p>
      <p style={styles.detailValue}>
        {typeof value === "string" || typeof value === "number" || value === null
          ? displayValue(value)
          : value}
      </p>
    </div>
  );
}
