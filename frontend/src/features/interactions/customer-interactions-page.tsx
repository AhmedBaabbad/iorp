"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { listCustomers } from "@/features/customers";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { displayValue } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import type { CustomerListItem } from "@/types/customers";

const styles: Record<string, CSSProperties> = {
  panel: {
    background: "#ffffff",
    border: "1px solid #d9dee7",
    borderRadius: "8px",
    boxShadow: "0 16px 40px rgba(31, 41, 51, 0.06)",
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
    textAlign: "left",
  },
  td: {
    borderBottom: "1px solid #eef1f5",
    padding: "14px 16px",
    verticalAlign: "middle",
  },
  link: {
    color: "#1d4ed8",
    fontWeight: 700,
    textDecoration: "none",
  },
};

export function CustomerInteractionsPage() {
  const t = useTranslations("commercial.interactions");
  const customersT = useTranslations("commercial.customers");
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const [customers, setCustomers] = useState<CustomerListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const isMountedRef = useRef(true);

  const loadCustomers = useCallback(async () => {
    if (!isMountedRef.current) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await listCustomers();
      if (isMountedRef.current) {
        setCustomers(response);
      }
    } catch (caughtError) {
      if (isMountedRef.current) {
        setError(getApiErrorMessage(caughtError, messages));
      }
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    }
  }, [messages]);

  useEffect(() => {
    isMountedRef.current = true;
    void loadCustomers();
    return () => {
      isMountedRef.current = false;
    };
  }, [loadCustomers]);

  return (
    <PageFrame title={t("listTitle")} subtitle={t("sectionDescription")} section="Commercial">
      {isLoading ? (
        <div style={{ ...sharedStyles.state, background: "#ffffff" }}>
          {messages("loading.default")}
        </div>
      ) : null}

      {!isLoading && error ? (
        <div style={{ display: "grid", gap: "12px" }}>
          <div style={sharedStyles.error} role="alert">
            {error}
          </div>
          <button
            style={{ ...sharedStyles.secondaryButton, width: "fit-content" }}
            type="button"
            onClick={() => void loadCustomers()}
          >
            {common("actions.retry")}
          </button>
        </div>
      ) : null}

      {!isLoading && !error && customers.length === 0 ? (
        <div style={{ ...sharedStyles.state, background: "#ffffff" }}>
          {messages("empty.noRecords")}
        </div>
      ) : null}

      {!isLoading && !error && customers.length > 0 ? (
        <section style={styles.panel} aria-label={t("listTitle")}>
          <div style={styles.tableWrap}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>{customersT("fields.customerCode")}</th>
                  <th style={styles.th}>{customersT("fields.name")}</th>
                  <th style={styles.th}>{customersT("fields.sector")}</th>
                  <th style={styles.th}>{customersT("fields.phone")}</th>
                  <th style={styles.th}>{customersT("fields.email")}</th>
                </tr>
              </thead>
              <tbody>
                {customers.map((customer) => (
                  <tr key={customer.id}>
                    <td style={styles.td}>{customer.customer_code}</td>
                    <td style={styles.td}>
                      <Link href={`/customers/${customer.id}#interactions-title`} style={styles.link}>
                        {customer.name}
                      </Link>
                    </td>
                    <td style={styles.td}>{displayValue(customer.sector)}</td>
                    <td style={styles.td}>{displayValue(customer.phone)}</td>
                    <td style={styles.td}>{displayValue(customer.email)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </PageFrame>
  );
}
