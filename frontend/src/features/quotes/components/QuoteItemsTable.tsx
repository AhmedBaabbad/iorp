"use client";

import type { CSSProperties } from "react";
import { useTranslations } from "next-intl";

import { useFormatter } from "@/hooks/useFormatter";
import { displayValue } from "@/lib/utils";
import type { QuoteItem } from "../types";

type QuoteItemsTableProps = {
  items: QuoteItem[];
  currency: string;
};

const styles: Record<string, CSSProperties> = {
  panel: {
    background: "var(--surface)",
    border: "1px solid var(--border-strong)",
    borderRadius: "8px",
    overflow: "hidden",
  },
  tableWrap: {
    overflowX: "auto",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
  },
  th: {
    borderBottom: "1px solid var(--border)",
    color: "var(--text-muted)",
    fontSize: "13px",
    padding: "14px 16px",
  },
  td: {
    borderBottom: "1px solid var(--border)",
    padding: "14px 16px",
    verticalAlign: "top",
  },
  spec: {
    background: "var(--surface-muted)",
    border: "1px solid var(--border)",
    borderRadius: "6px",
    color: "var(--text)",
    fontSize: "12px",
    margin: "8px 0 0",
    maxWidth: "420px",
    overflowX: "auto",
    padding: "10px",
    whiteSpace: "pre-wrap",
  },
};

export function QuoteItemsTable({ items, currency }: QuoteItemsTableProps) {
  const fmt = useFormatter();
  const t = useTranslations("commercial.quotes");
  void currency;

  return (
    <section style={styles.panel} aria-label={t("items.sectionTitle")}>
      <div style={styles.tableWrap}>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={{ ...styles.th, textAlign: "center", width: "8%" }}>
                {t("items.fields.lineNo")}
              </th>
              <th style={{ ...styles.th, textAlign: "start", width: "34%" }}>
                {t("items.fields.productType")}
              </th>
              <th style={{ ...styles.th, textAlign: "center", width: "12%" }}>
                {t("items.fields.quantity")}
              </th>
              <th style={{ ...styles.th, textAlign: "start", width: "12%" }}>
                {t("items.fields.unit")}
              </th>
              <th style={{ ...styles.th, textAlign: "end", width: "17%" }}>
                {t("items.fields.unitPrice")}
              </th>
              <th style={{ ...styles.th, textAlign: "end", width: "17%" }}>
                {t("items.fields.lineTotal")}
              </th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={`${item.line_no}-${item.product_type}`}>
                <td style={{ ...styles.td, textAlign: "center" }}>{item.line_no}</td>
                <td style={{ ...styles.td, textAlign: "start" }}>
                  {item.product_type}
                  {item.requested_spec_json ? (
                    <pre style={styles.spec}>
                      {JSON.stringify(item.requested_spec_json, null, 2)}
                    </pre>
                  ) : null}
                </td>
                <td style={{ ...styles.td, textAlign: "center" }}>{fmt.number(item.quantity)}</td>
                <td style={{ ...styles.td, textAlign: "start" }}>{displayValue(item.unit)}</td>
                <td style={{ ...styles.td, textAlign: "end" }}>{fmt.decimal(item.unit_price)}</td>
                <td style={{ ...styles.td, textAlign: "end" }}>{fmt.decimal(item.line_total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
