"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";
import { useEffect, useState } from "react";

import { SuccessModal } from "@/components/ui/SuccessModal";
import { usePermission } from "@/features/auth";
import { ApiClientError } from "@/lib/api-client";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { sharedStyles } from "@/styles/shared-styles";
import type { EligibleSalesOwner } from "@/types/customers";
import { getCustomer, getEligibleSalesOwners, updateCustomer } from "./customer-api";
import {
  defaultCustomerFormValues,
  toCustomerCreateRequest,
  toCustomerFormValues,
  type CustomerFormValues,
} from "./customer-form";
import { PageFrame } from "@/components/layout/page-frame";
import { CustomerFields } from "./CustomerFields";

const styles: Record<string, CSSProperties> = {
  panel: {
    background: "var(--surface)",
    border: "1px solid var(--border-strong)",
    borderRadius: "8px",
    boxShadow: "0 16px 40px rgba(31, 41, 51, 0.06)",
  },
  form: {
    display: "grid",
    gap: "18px",
    padding: "24px",
  },
  formGrid: {
    display: "grid",
    gap: "18px",
    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  },
  actions: {
    display: "flex",
    flexWrap: "wrap",
    gap: "12px",
    alignItems: "center",
  },
  required: {
    color: "var(--danger)",
    marginLeft: "2px",
  },
  requiredNote: {
    color: "var(--text-muted)",
    fontSize: "13px",
    marginLeft: "auto",
  },
  note: {
    color: "var(--text-muted)",
    fontSize: "13px",
    margin: 0,
  },
};

export function CustomerEditPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const t = useTranslations("commercial.customers");
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const customerId = params.id;
  const canAssignOwner = usePermission("commercial:customers:assign_owner");
  const [values, setValues] = useState<CustomerFormValues>(defaultCustomerFormValues);
  const [customerCode, setCustomerCode] = useState<string | null>(null);
  const [currentOwnerName, setCurrentOwnerName] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isNotFound, setIsNotFound] = useState(false);
  const [successRedirect, setSuccessRedirect] = useState<string | null>(null);
  const [eligibleOwners, setEligibleOwners] = useState<EligibleSalesOwner[]>([]);
  const [isLoadingOwners, setIsLoadingOwners] = useState(canAssignOwner);

  useEffect(() => {
    let isMounted = true;

    async function loadCustomer() {
      try {
        setIsLoading(true);
        setError(null);
        setIsNotFound(false);
        const response = await getCustomer(customerId);
        if (isMounted) {
          setValues(toCustomerFormValues(response));
          setCustomerCode(response.customer_code);
          setCurrentOwnerName(response.sales_owner?.full_name ?? null);
        }
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

    void loadCustomer();

    return () => {
      isMounted = false;
    };
  }, [customerId, messages]);

  useEffect(() => {
    if (!canAssignOwner) {
      return;
    }

    let cancelled = false;
    setIsLoadingOwners(true);
    getEligibleSalesOwners()
      .then((data) => {
        if (!cancelled) {
          setEligibleOwners(data);
        }
      })
      .catch(() => {
        // Per-field "no eligible owners" state handles this; no page error needed.
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoadingOwners(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [canAssignOwner]);

  async function handleSubmit(event: { preventDefault(): void }) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const updatedCustomer = await updateCustomer(
        customerId,
        toCustomerCreateRequest(values, canAssignOwner, false),
      );
      setSuccessRedirect(`/customers/${updatedCustomer.id}`);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError, messages));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <>
    {successRedirect ? (
      <SuccessModal
        message={t("updateSuccess")}
        okLabel={common("actions.ok")}
        onOk={() => router.replace(successRedirect)}
      />
    ) : null}
    <PageFrame
      title={t("editTitle")}
      subtitle={customerCode ?? t("detailSubtitle")}
      action={
        <Link href={`/customers/${customerId}`} style={sharedStyles.secondaryButton}>
          {t("backToDetail")}
        </Link>
      }
    >
      {isLoading ? (
        <div style={{ ...sharedStyles.state, background: "var(--surface)" }}>{t("loadingDetail")}</div>
      ) : null}

      {!isLoading && isNotFound ? (
        <section style={{ ...sharedStyles.state, background: "var(--surface)" }}>
          <h2 style={{ margin: "0 0 8px", fontSize: "20px" }}>{t("notFound")}</h2>
          <p style={{ margin: "0 0 18px" }}>{t("notFoundDescription")}</p>
          <Link href="/customers" style={sharedStyles.button}>
            {t("backToList")}
          </Link>
        </section>
      ) : null}

      {!isLoading && !isNotFound ? (
        <section style={styles.panel}>
          <form style={styles.form} onSubmit={handleSubmit}>
            <CustomerFields values={values} onChange={patch => setValues(current => ({ ...current, ...patch }))}
            disabled={isSubmitting} canAssignOwner={canAssignOwner} eligibleOwners={eligibleOwners} loadingOwners={isLoadingOwners}
            creating={false} ownerName={currentOwnerName} />

          {error ? (
              <div style={sharedStyles.error} role="alert">
                {error}
              </div>
            ) : null}

            <div style={styles.actions}>
              <button style={sharedStyles.button} type="submit" disabled={isSubmitting}>
                {isSubmitting ? `${common("actions.save")}...` : t("updateButton")}
              </button>
              <Link href={`/customers/${customerId}`} style={sharedStyles.secondaryButton}>
                {common("actions.cancel")}
              </Link>
              <span style={styles.requiredNote}>* {common("labels.required")}</span>
            </div>
          </form>
        </section>
      ) : null}
    </PageFrame>
    </>
  );
}
