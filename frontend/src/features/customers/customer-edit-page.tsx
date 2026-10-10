"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";
import { useEffect, useState } from "react";

import { SuccessModal } from "@/components/ui/SuccessModal";
import { usePermission } from "@/features/auth";
import { getEnumLabel } from "@/i18n/enum-helpers";
import { ApiClientError } from "@/lib/api-client";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { ListSelect } from "@/features/masterdata";
import { sharedStyles } from "@/styles/shared-styles";
import type {
  CustomerStatus,
  EligibleSalesOwner,
  PriorityLevel,
  RelationshipStage,
} from "@/types/customers";
import { getCustomer, getEligibleSalesOwners, updateCustomer } from "./customer-api";
import {
  defaultCustomerFormValues,
  toCustomerCreateRequest,
  toCustomerFormValues,
  type CustomerFormValues,
} from "./customer-form";
import { PageFrame } from "@/components/layout/page-frame";

function formatOwnerOption(owner: EligibleSalesOwner): string {
  const roleName = owner.roles[0]?.name;
  return roleName ? `${owner.full_name} — ${roleName}` : owner.full_name;
}

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

const customerStatusOptions: CustomerStatus[] = [
  "active",
  "inactive",
  "on_hold",
  "archived",
  "blacklisted",
];

const relationshipStageOptions: RelationshipStage[] = [
  "lead",
  "contacted",
  "qualified",
  "prospect",
  "negotiating",
  "trial_customer",
  "active_customer",
  "repeat_customer",
  "strategic_customer",
];

const priorityOptions: PriorityLevel[] = ["low", "medium", "high"];

export function CustomerEditPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const t = useTranslations("commercial.customers");
  const tEnums = useTranslations();
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

  function updateField<TField extends keyof CustomerFormValues>(
    field: TField,
    value: CustomerFormValues[TField],
  ) {
    setValues((current) => ({
      ...current,
      [field]: value,
    }));
  }

  async function handleSubmit(event: { preventDefault(): void }) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const updatedCustomer = await updateCustomer(
        customerId,
        toCustomerCreateRequest(values, canAssignOwner),
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
            <div style={styles.formGrid}>
              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>
                  {t("fields.name")}
                  <span style={styles.required} aria-hidden="true"> *</span>
                </span>
                <input
                  style={sharedStyles.input}
                  value={values.name}
                  onChange={(event) => updateField("name", event.target.value)}
                  maxLength={255}
                  disabled={isSubmitting}
                  required
                />
              </label>

              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>{t("fields.sector")}</span>
                <ListSelect style={sharedStyles.input} list="sector" value={values.sector} disabled={isSubmitting} ariaLabel={t("fields.sector")}
                  onChange={(key) => updateField("sector", key)} />
              </label>

              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>{t("fields.city")}</span>
                <ListSelect style={sharedStyles.input} list="city" value={values.city} parent={values.country} disabled={isSubmitting} ariaLabel={t("fields.city")}
                  onChange={(key) => updateField("city", key)} />
              </label>

              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>{t("fields.country")}</span>
                <ListSelect style={sharedStyles.input} list="country" value={values.country} disabled={isSubmitting} ariaLabel={t("fields.country")}
                  onChange={(key) => updateField("country", key)} />
              </label>

              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>{t("fields.phone")}</span>
                <input
                  style={sharedStyles.input}
                  value={values.phone}
                  onChange={(event) => updateField("phone", event.target.value)}
                  maxLength={50}
                  disabled={isSubmitting}
                />
              </label>

              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>{t("fields.email")}</span>
                <input
                  style={sharedStyles.input}
                  type="email"
                  value={values.email}
                  onChange={(event) => updateField("email", event.target.value)}
                  maxLength={255}
                  disabled={isSubmitting}
                />
              </label>

              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>{t("fields.status")}</span>
                <select
                  style={sharedStyles.input}
                  value={values.status}
                  onChange={(event) =>
                    updateField("status", event.target.value as CustomerFormValues["status"])
                  }
                  disabled={isSubmitting}
                >
                  {customerStatusOptions.map((status) => (
                    <option key={status} value={status}>
                      {getEnumLabel("customer", "status", status, tEnums)}
                    </option>
                  ))}
                </select>
              </label>

              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>{t("fields.relationshipStage")}</span>
                <select
                  style={sharedStyles.input}
                  value={values.relationship_stage}
                  onChange={(event) =>
                    updateField(
                      "relationship_stage",
                      event.target.value as CustomerFormValues["relationship_stage"],
                    )
                  }
                  disabled={isSubmitting}
                >
                  {relationshipStageOptions.map((stage) => (
                    <option key={stage} value={stage}>
                      {getEnumLabel("customer", "relationshipStage", stage, tEnums)}
                    </option>
                  ))}
                </select>
              </label>

              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>{t("fields.priority")}</span>
                <select
                  style={sharedStyles.input}
                  value={values.priority_level}
                  onChange={(event) =>
                    updateField(
                      "priority_level",
                      event.target.value as CustomerFormValues["priority_level"],
                    )
                  }
                  disabled={isSubmitting}
                >
                  {priorityOptions.map((priority) => (
                    <option key={priority} value={priority}>
                      {getEnumLabel("customer", "priorityLevel", priority, tEnums)}
                    </option>
                  ))}
                </select>
              </label>

              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>{t("fields.opportunitySource")}</span>
                <ListSelect style={sharedStyles.input} list="opportunity_source" value={values.opportunity_source} disabled={isSubmitting} ariaLabel={t("fields.opportunitySource")}
                  onChange={(key) => updateField("opportunity_source", key)} />
              </label>

              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>{t("fields.estimatedConsumption")}</span>
                <input
                  style={sharedStyles.input}
                  type="number"
                  step="0.01"
                  min="0"
                  value={values.estimated_consumption}
                  onChange={(event) => updateField("estimated_consumption", event.target.value)}
                  disabled={isSubmitting}
                />
              </label>

              {canAssignOwner ? (
                <label style={sharedStyles.field}>
                  <span style={sharedStyles.label}>
                    {t("fields.salesOwner")}
                    <span style={styles.required} aria-hidden="true"> *</span>
                  </span>
                  {isLoadingOwners ? (
                    <p style={styles.note}>{t("loadingEligibleUsers")}</p>
                  ) : eligibleOwners.length === 0 ? (
                    <p style={styles.note}>{t("noEligibleOwners")}</p>
                  ) : (
                    <select
                      style={sharedStyles.input}
                      value={values.sales_owner_user_id}
                      onChange={(event) => updateField("sales_owner_user_id", event.target.value)}
                      disabled={isSubmitting}
                      required
                    >
                      <option value="">{t("selectSalesOwner")}</option>
                      {eligibleOwners.map((owner) => (
                        <option key={owner.id} value={owner.id}>
                          {formatOwnerOption(owner)}
                        </option>
                      ))}
                    </select>
                  )}
                </label>
              ) : (
                <label style={sharedStyles.field}>
                  <span style={sharedStyles.label}>{t("fields.salesOwner")}</span>
                  <input
                    style={sharedStyles.input}
                    value={currentOwnerName ?? t("noOwner")}
                    disabled
                    readOnly
                  />
                </label>
              )}

              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>{t("fields.keyInfluencerName")}</span>
                <input
                  style={sharedStyles.input}
                  value={values.key_influencer_name}
                  onChange={(event) => updateField("key_influencer_name", event.target.value)}
                  maxLength={255}
                  disabled={isSubmitting}
                />
              </label>
            </div>

            <p style={styles.note}>{t("labels.statusVsStageNote")}</p>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>{t("fields.notes")}</span>
              <textarea
                style={{ ...sharedStyles.textarea, minHeight: "110px" }}
                value={values.notes}
                onChange={(event) => updateField("notes", event.target.value)}
                disabled={isSubmitting}
              />
            </label>

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
