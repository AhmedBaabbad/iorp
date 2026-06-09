"use client";

import Link from "next/link";
import type { CSSProperties } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import { getErrorMessage } from "@/lib/errors";
import { displayValue } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import type { CustomerListItem, PriorityLevel, RelationshipStage } from "@/types/customers";
import { listCustomers } from "./customer-api";
import { PageFrame } from "@/components/layout/page-frame";

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

export function CustomersListPage() {
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
        setError(getErrorMessage(caughtError, "Unable to load customers."));
      }
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
    void loadCustomers();
    return () => {
      isMountedRef.current = false;
    };
  }, [loadCustomers]);

  return (
    <PageFrame
      title="Customers"
      subtitle="Manage baseline customer records for the commercial domain."
      action={
        <Link href="/customers/new" style={sharedStyles.button}>
          New customer
        </Link>
      }
    >
      {isLoading ? (
        <div style={{ ...sharedStyles.state, background: "#ffffff" }}>Loading customers...</div>
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
            Try again
          </button>
        </div>
      ) : null}

      {!isLoading && !error && customers.length === 0 ? (
        <section style={{ ...sharedStyles.state, background: "#ffffff" }}>
          <h2 style={{ margin: "0 0 8px", fontSize: "20px" }}>No customers yet</h2>
          <p style={{ margin: "0 0 18px" }}>Create the first customer to start the slice.</p>
          <Link href="/customers/new" style={sharedStyles.button}>
            Create customer
          </Link>
        </section>
      ) : null}

      {!isLoading && !error && customers.length > 0 ? (
        <section style={styles.panel} aria-label="Customers list">
          <div style={styles.tableWrap}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>Code</th>
                  <th style={styles.th}>Name</th>
                  <th style={styles.th}>Sector</th>
                  <th style={styles.th}>Stage</th>
                  <th style={styles.th}>Priority</th>
                  <th style={styles.th}>Status</th>
                </tr>
              </thead>
              <tbody>
                {customers.map((customer) => (
                  <tr key={customer.id}>
                    <td style={styles.td}>{customer.customer_code}</td>
                    <td style={styles.td}>
                      <Link href={`/customers/${customer.id}`} style={styles.link}>
                        {customer.name}
                      </Link>
                    </td>
                    <td style={styles.td}>{displayValue(customer.sector)}</td>
                    <td style={styles.td}>
                      <span style={stageBadgeStyle(customer.relationship_stage)}>
                        {customer.relationship_stage}
                      </span>
                    </td>
                    <td style={styles.td}>
                      <span style={priorityBadgeStyle(customer.priority_level)}>
                        {customer.priority_level}
                      </span>
                    </td>
                    <td style={styles.td}>
                      <span style={statusBadgeStyle(customer.status)}>{customer.status}</span>
                    </td>
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

function statusBadgeStyle(status: CustomerListItem["status"]) {
  return {
    ...sharedStyles.badge,
    background: status === "active" ? "#dcfce7" : "#f3f4f6",
    color: status === "active" ? "#166534" : "#4b5563",
  };
}

function stageBadgeStyle(stage: RelationshipStage) {
  const colors: Record<RelationshipStage, { background: string; color: string }> = {
    lead: { background: "#f3f4f6", color: "#4b5563" },
    prospect: { background: "#dbeafe", color: "#1e40af" },
    customer: { background: "#dcfce7", color: "#166534" },
  };
  return { ...sharedStyles.badge, ...colors[stage] };
}

function priorityBadgeStyle(priority: PriorityLevel) {
  const colors: Record<PriorityLevel, { background: string; color: string }> = {
    low: { background: "#f3f4f6", color: "#4b5563" },
    medium: { background: "#fef3c7", color: "#92400e" },
    high: { background: "#fee2e2", color: "#991b1b" },
  };
  return { ...sharedStyles.badge, ...colors[priority] };
}
