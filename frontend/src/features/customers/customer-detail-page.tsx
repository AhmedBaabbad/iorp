"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import type { CSSProperties } from "react";
import { useEffect, useState } from "react";

import { CustomerFollowUpsSection } from "@/features/followups";
import { CustomerInteractionsSection } from "@/features/interactions";
import { ApiClientError } from "@/lib/api-client";
import { getErrorMessage } from "@/lib/errors";
import { displayValue, formatDate } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import type { CustomerDetail } from "@/types/customers";
import { getCustomer } from "./customer-api";
import { PageFrame } from "@/components/layout/page-frame";

const styles: Record<string, CSSProperties> = {
  detailGrid: {
    display: "grid",
    gap: "1px",
    gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
    background: "#e4e7ec",
    borderRadius: "8px",
    overflow: "hidden",
  },
  detailItem: {
    background: "#ffffff",
    padding: "18px",
  },
  detailLabel: {
    color: "#52606d",
    fontSize: "13px",
    fontWeight: 700,
    margin: "0 0 8px",
  },
  detailValue: {
    margin: 0,
    overflowWrap: "anywhere",
  },
  relatedSections: {
    display: "grid",
    gap: "24px",
  },
};

export function CustomerDetailPage() {
  const params = useParams<{ id: string }>();
  const customerId = params.id;
  const [customer, setCustomer] = useState<CustomerDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isNotFound, setIsNotFound] = useState(false);

  useEffect(() => {
    let isMounted = true;

    async function loadCustomer() {
      try {
        setIsLoading(true);
        setError(null);
        setIsNotFound(false);
        const response = await getCustomer(customerId);

        if (isMounted) {
          setCustomer(response);
        }
      } catch (caughtError) {
        if (!isMounted) {
          return;
        }

        if (caughtError instanceof ApiClientError && caughtError.status === 404) {
          setIsNotFound(true);
          return;
        }

        setError(getErrorMessage(caughtError, "Unable to load customer."));
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadCustomer();

    return () => {
      isMounted = false;
    };
  }, [customerId]);

  return (
    <PageFrame
      title={customer?.name ?? "Customer detail"}
      subtitle={customer ? customer.customer_code : "View baseline customer information."}
      action={
        <Link href="/customers" style={sharedStyles.secondaryButton}>
          Back to customers
        </Link>
      }
    >
      {isLoading ? (
        <div style={{ ...sharedStyles.state, background: "#ffffff" }}>Loading customer...</div>
      ) : null}

      {!isLoading && isNotFound ? (
        <section style={{ ...sharedStyles.state, background: "#ffffff" }}>
          <h2 style={{ margin: "0 0 8px", fontSize: "20px" }}>Customer not found</h2>
          <p style={{ margin: "0 0 18px" }}>The customer may have been removed or is unavailable.</p>
          <Link href="/customers" style={sharedStyles.button}>
            Return to customers
          </Link>
        </section>
      ) : null}

      {!isLoading && error ? (
        <div style={sharedStyles.error} role="alert">
          {error}
        </div>
      ) : null}

      {!isLoading && !error && !isNotFound && customer ? (
        <div style={styles.relatedSections}>
          <section style={styles.detailGrid} aria-label="Customer details">
            <DetailItem label="Customer code" value={customer.customer_code} />
            <DetailItem label="Name" value={customer.name} />
            <DetailItem label="Sector" value={customer.sector} />
            <DetailItem label="City" value={customer.city} />
            <DetailItem label="Country" value={customer.country} />
            <DetailItem label="Status" value={customer.status} />
            <DetailItem label="Relationship stage" value={customer.relationship_stage} />
            <DetailItem label="Priority" value={customer.priority_level} />
            <DetailItem label="Opportunity source" value={customer.opportunity_source} />
            <DetailItem label="Estimated consumption" value={customer.estimated_consumption} />
            <DetailItem label="Assigned sales user" value={customer.assigned_sales_user_id} />
            <DetailItem label="Created" value={formatDate(customer.created_at)} />
            <DetailItem label="Updated" value={formatDate(customer.updated_at)} />
            <DetailItem label="Notes" value={customer.notes} />
          </section>

          <CustomerInteractionsSection customerId={customer.id} />
          <CustomerFollowUpsSection customerId={customer.id} />
        </div>
      ) : null}
    </PageFrame>
  );
}

function DetailItem({ label, value }: { label: string; value: string | number | null }) {
  return (
    <div style={styles.detailItem}>
      <p style={styles.detailLabel}>{label}</p>
      <p style={styles.detailValue}>{displayValue(value)}</p>
    </div>
  );
}
