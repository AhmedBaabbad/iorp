"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";
import { useEffect, useState } from "react";

import { AccessDeniedMessage } from "@/components/AccessDeniedMessage";
import { SuccessModal } from "@/components/ui/SuccessModal";
import { useAuth, usePermission } from "@/features/auth";
import { getEnumLabel } from "@/i18n/enum-helpers";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { sharedStyles } from "@/styles/shared-styles";
import type {
  CustomerStatus,
  EligibleSalesOwner,
  PriorityLevel,
  RelationshipStage,
} from "@/types/customers";
import { createCustomer, getEligibleSalesOwners } from "./customer-api";
import {
  defaultCustomerFormValues,
  toCustomerCreateRequest,
  type CustomerFormValues,
} from "./customer-form";
import { PageFrame } from "@/components/layout/page-frame";

function formatOwnerOption(owner: EligibleSalesOwner): string {
  const roleName = owner.roles[0]?.name;
  return roleName ? `${owner.full_name} — ${roleName}` : owner.full_name;
}

const styles: Record<string, CSSProperties> = {
  panel: {
    background: "#ffffff",
    border: "1px solid #d9dee7",
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
    color: "#be123c",
    marginLeft: "2px",
  },
  requiredNote: {
    color: "#52606d",
    fontSize: "13px",
    marginLeft: "auto",
  },
  note: {
    color: "#52606d",
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

export function CustomerCreatePage() {
  const router = useRouter();
  const t = useTranslations("commercial.customers");
  const tEnums = useTranslations();
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
              <input
                style={sharedStyles.input}
                value={values.sector}
                onChange={(event) => updateField("sector", event.target.value)}
                maxLength={120}
                disabled={isSubmitting}
              />
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>{t("fields.city")}</span>
              <input
                style={sharedStyles.input}
                value={values.city}
                onChange={(event) => updateField("city", event.target.value)}
                maxLength={120}
                disabled={isSubmitting}
              />
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>{t("fields.country")}</span>
              <input
                style={sharedStyles.input}
                value={values.country}
                onChange={(event) => updateField("country", event.target.value)}
                maxLength={120}
                disabled={isSubmitting}
              />
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
              <input
                style={sharedStyles.input}
                value={values.opportunity_source}
                onChange={(event) => updateField("opportunity_source", event.target.value)}
                maxLength={120}
                disabled={isSubmitting}
              />
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
            ) : isEligibleOwner ? (
              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>{t("fields.salesOwner")}</span>
                <input style={sharedStyles.input} value={user?.full_name ?? ""} disabled readOnly />
                <span style={styles.note}>{t("salesOwnerAutoAssigned")}</span>
              </label>
            ) : null}

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
