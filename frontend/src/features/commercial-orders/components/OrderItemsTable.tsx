"use client";

import type { CSSProperties } from "react";
import { useTranslations } from "next-intl";

import { useFormatter } from "@/hooks/useFormatter";
import { displayValue } from "@/lib/utils";
import type { CommercialOrderItem } from "../types";

type OrderItemsTableProps = {
  items: CommercialOrderItem[];
  currency?: string;
};

const styles: Record<string, CSSProperties> = {
  panel: {
    background: "#ffffff",
    border: "1px solid #d9dee7",
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
    borderBottom: "1px solid #e4e7ec",
    color: "#52606d",
    fontSize: "13px",
    padding: "14px 16px",
  },
  td: {
    borderBottom: "1px solid #eef1f5",
    padding: "14px 16px",
    verticalAlign: "top",
  },
  spec: {
    background: "#f9fafb",
    border: "1px solid #e4e7ec",
    borderRadius: "6px",
    color: "#1f2933",
    fontSize: "12px",
    margin: "8px 0 0",
    maxWidth: "420px",
    overflowX: "auto",
    padding: "10px",
    whiteSpace: "pre-wrap",
  },
};

export function OrderItemsTable({ items, currency = "" }: OrderItemsTableProps) {
  const fmt = useFormatter();
  const t = useTranslations("commercial.commercialOrders");
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
                <td style={{ ...styles.td, textAlign: "end" }}>{fmt.decimal(item.agreed_unit_price)}</td>
                <td style={{ ...styles.td, textAlign: "end" }}>{fmt.decimal(item.line_total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
