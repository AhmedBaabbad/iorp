"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { listCustomers } from "@/features/customers";
import { Pagination } from "@/components/pagination/Pagination";
import { useListQuery, type Page } from "@/lib/pagination";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { displayValue } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import type { CustomerListItem } from "@/types/customers";
import { useListName } from "@/features/masterdata";

const styles: Record<string, CSSProperties> = {
  panel: {
    background: "var(--surface)",
    border: "1px solid var(--border-strong)",
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
    borderBottom: "1px solid var(--border)",
    color: "var(--text-muted)",
    fontSize: "13px",
    padding: "14px 16px",
    textAlign: "left",
  },
  td: {
    borderBottom: "1px solid var(--border)",
    padding: "14px 16px",
    verticalAlign: "middle",
  },
  link: {
    color: "var(--accent-strong)",
    fontWeight: 700,
    textDecoration: "none",
  },
};

export function CustomerInteractionsPage() {
  const t = useTranslations("commercial.interactions");
  const customersT = useTranslations("commercial.customers");
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const sectorName = useListName("sector");  // MD-002: the name, not the key
  // ARCH-PAGE-001: one page of customers at a time, searched by the server.
  const list = useListQuery(["search"] as const);
  const apiQuery = list.apiQuery();
  const [searchText, setSearchText] = useState(list.filters.search);
  const [data, setData] = useState<Page<CustomerListItem> | null>(null);
  const customers = data?.items ?? [];
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
      const response = await listCustomers(apiQuery);
      if (isMountedRef.current) {
        setData(response);
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
  }, [messages, apiQuery]);

  useEffect(() => {
    if (searchText === list.filters.search) return;
    const timer = setTimeout(() => list.setFilter("search", searchText.trim()), 350);
    return () => clearTimeout(timer);
  }, [searchText]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    isMountedRef.current = true;
    void loadCustomers();
    return () => {
      isMountedRef.current = false;
    };
  }, [loadCustomers]);

  return (
    <PageFrame title={t("listTitle")} subtitle={t("sectionDescription")} section="Commercial">
      <label style={{ ...sharedStyles.field, maxWidth: "420px", marginBottom: "16px" }}>
        <span style={sharedStyles.label}>{customersT("listFilters.search")}</span>
        <input type="search" style={sharedStyles.input} value={searchText} placeholder={customersT("listFilters.searchHint")}
          onChange={(event) => setSearchText(event.target.value)} />
      </label>

      {isLoading && !data ? (
        <div style={{ ...sharedStyles.state, background: "var(--surface)" }}>
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
        <div style={{ ...sharedStyles.state, background: "var(--surface)" }}>
          {messages("empty.noRecords")}
        </div>
      ) : null}

      {!error && customers.length > 0 ? (
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
                    <td style={styles.td}>{displayValue(customer.sector ? sectorName(customer.sector) : customer.sector)}</td>
                    <td style={styles.td}>{displayValue(customer.phone)}</td>
                    <td style={styles.td}>{displayValue(customer.email)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {data ? <Pagination page={data.page} pageSize={data.page_size} total={data.total} pages={data.pages} disabled={isLoading}
            onPage={list.setPage} onPageSize={list.setPageSize} /> : null}
        </section>
      ) : null}
    </PageFrame>
  );
}
