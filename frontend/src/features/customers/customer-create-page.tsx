"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";
import { useEffect, useState } from "react";

import { AccessDeniedMessage } from "@/components/AccessDeniedMessage";
import { SuccessModal } from "@/components/ui/SuccessModal";
import { useAuth, usePermission } from "@/features/auth";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { sharedStyles } from "@/styles/shared-styles";
import type { EligibleSalesOwner } from "@/types/customers";
import { createCustomer, getEligibleSalesOwners } from "./customer-api";
import {
  defaultCustomerFormValues,
  hasPrimaryContact,
  toCustomerCreateRequest,
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

export function CustomerCreatePage() {
  const router = useRouter();
  const t = useTranslations("commercial.customers");
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const { user } = useAuth();
  const canAssignOwner = usePermission("commercial:customers:assign_owner");
  const hasCustomerRead = usePermission("commercial:customers:read");
  const hasCustomerUpdate = usePermission("commercial:customers:update");
  const isEligibleOwner = hasCustomerRead && hasCustomerUpdate;
  const [values, setValues] = useState<CustomerFormValues>(defaultCustomerFormValues);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successRedirect, setSuccessRedirect] = useState<string | null>(null);
  const [eligibleOwners, setEligibleOwners] = useState<EligibleSalesOwner[]>([]);
  const [isLoadingOwners, setIsLoadingOwners] = useState(canAssignOwner);

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
      const createdCustomer = await createCustomer(toCustomerCreateRequest(values, canAssignOwner));
      setSuccessRedirect(`/customers/${createdCustomer.id}`);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError, messages));
    } finally {
      setIsSubmitting(false);
    }
  }

  if (!canAssignOwner && !isEligibleOwner) {
    return <AccessDeniedMessage message={t("notEligibleToCreate")} />;
  }

  return (
    <>
    {successRedirect ? (
      <SuccessModal
        message={t("createSuccess")}
        okLabel={common("actions.ok")}
        onOk={() => router.replace(successRedirect)}
      />
    ) : null}
    <PageFrame
      title={t("createTitle")}
      subtitle={t("createSubtitle")}
      action={
        <Link href="/customers" style={sharedStyles.secondaryButton}>
          {t("backToList")}
        </Link>
      }
    >
      <section style={styles.panel}>
        <form style={styles.form} onSubmit={handleSubmit}>
          <CustomerFields values={values} onChange={patch => setValues(current => ({ ...current, ...patch }))}
            disabled={isSubmitting} canAssignOwner={canAssignOwner} eligibleOwners={eligibleOwners} loadingOwners={isLoadingOwners}
            creating ownerName={user?.full_name} autoAssigned={isEligibleOwner} />

          {error ? (
            <div style={sharedStyles.error} role="alert">
              {error}
            </div>
          ) : null}

          <div style={styles.actions}>
            <button style={sharedStyles.button} type="submit" disabled={isSubmitting || (hasPrimaryContact(values) && !values.contact_name.trim())}>
              {isSubmitting ? `${common("actions.create")}...` : t("createButton")}
            </button>
            <Link href="/customers" style={sharedStyles.secondaryButton}>
              {common("actions.cancel")}
            </Link>
            <span style={styles.requiredNote}>* {common("labels.required")}</span>
          </div>
        </form>
      </section>
    </PageFrame>
    </>
  );
}
