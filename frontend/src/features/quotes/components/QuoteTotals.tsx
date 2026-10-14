"use client";

import type { CSSProperties } from "react";
import { useLocale, useTranslations } from "next-intl";

import { useFormatter } from "@/hooks/useFormatter";
import type { Locale } from "@/i18n/config";
import { sharedStyles } from "@/styles/shared-styles";
import type { QuoteTotalsData } from "../types";
import { formatCommercialCurrency } from "./quote-utils";

type QuoteTotalsProps = {
  totals: QuoteTotalsData;
};

const styles: Record<string, CSSProperties> = {
  panel: {
    background: "var(--surface)",
    border: "1px solid var(--border-strong)",
    borderRadius: "8px",
    display: "grid",
    gap: "10px",
    marginLeft: "auto",
    maxWidth: "360px",
    padding: "18px",
    width: "100%",
  },
  row: {
    display: "flex",
    justifyContent: "space-between",
    gap: "16px",
  },
  totalRow: {
    borderTop: "1px solid var(--border)",
    fontWeight: 800,
    paddingTop: "12px",
  },
};

export function QuoteTotals({ totals }: QuoteTotalsProps) {
  const fmt = useFormatter();
  const locale = useLocale() as Locale;
  const t = useTranslations("commercial.quotes");

  return (
    <section style={styles.panel} aria-label={t("summary.sectionTitle")}>
      {Number(totals.discount) > 0 ? (
        <>
          <TotalsRow label={t("discount.subtotalBefore")} value={fmt.decimal(totals.subtotal)} />
          <TotalsRow label={t("discount.total")} value={`- ${fmt.decimal(totals.discount)}`} />
          <TotalsRow label={t("discount.subtotalAfter")} value={fmt.decimal(Number(totals.subtotal) - Number(totals.discount))} />
        </>
      ) : (
        <TotalsRow label={t("fields.subtotal")} value={fmt.decimal(totals.subtotal)} />
      )}
      <TotalsRow label={t("fields.tax")} value={fmt.decimal(totals.tax)} />
      <TotalsRow
        label={t("summary.totalLabel")}
        value={formatCommercialCurrency(fmt.currency(totals.total, totals.currency), totals.currency, locale)}
        isTotal
      />
    </section>
  );
}

function TotalsRow({
  label,
  value,
  isTotal = false,
}: {
  label: string;
  value: string;
  isTotal?: boolean;
}) {
  return (
    <div style={{ ...styles.row, ...(isTotal ? styles.totalRow : {}) }}>
      <span style={sharedStyles.meta}>{label}</span>
      <span>{value}</span>
    </div>
  );
}
