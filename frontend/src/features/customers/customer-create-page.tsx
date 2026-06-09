"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { CSSProperties, FormEvent } from "react";
import { useState } from "react";

import { getErrorMessage } from "@/lib/errors";
import { sharedStyles } from "@/styles/shared-styles";
import { createCustomer } from "./customer-api";
import {
  defaultCustomerFormValues,
  toCustomerCreateRequest,
  type CustomerFormValues,
} from "./customer-form";
import { PageFrame } from "@/components/layout/page-frame";

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
};

export function CustomerCreatePage() {
  const router = useRouter();
  const [values, setValues] = useState<CustomerFormValues>(defaultCustomerFormValues);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function updateField<TField extends keyof CustomerFormValues>(
    field: TField,
    value: CustomerFormValues[TField],
  ) {
    setValues((current) => ({
      ...current,
      [field]: value,
    }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const createdCustomer = await createCustomer(toCustomerCreateRequest(values));
      router.replace(`/customers/${createdCustomer.id}`);
    } catch (caughtError) {
      setError(getErrorMessage(caughtError, "Unable to create customer."));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <PageFrame
      title="Create customer"
      subtitle="Add a baseline commercial customer record."
      action={
        <Link href="/customers" style={sharedStyles.secondaryButton}>
          Back to customers
        </Link>
      }
    >
      <section style={styles.panel}>
        <form style={styles.form} onSubmit={handleSubmit}>
          <div style={styles.formGrid}>
            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>
                Customer code
                <span style={styles.required} aria-hidden="true"> *</span>
              </span>
              <input
                style={sharedStyles.input}
                value={values.customer_code}
                onChange={(event) => updateField("customer_code", event.target.value)}
                maxLength={64}
                disabled={isSubmitting}
                required
              />
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>
                Name
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
              <span style={sharedStyles.label}>Sector</span>
              <input
                style={sharedStyles.input}
                value={values.sector}
                onChange={(event) => updateField("sector", event.target.value)}
                maxLength={120}
                disabled={isSubmitting}
              />
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>City</span>
              <input
                style={sharedStyles.input}
                value={values.city}
                onChange={(event) => updateField("city", event.target.value)}
                maxLength={120}
                disabled={isSubmitting}
              />
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>Country</span>
              <input
                style={sharedStyles.input}
                value={values.country}
                onChange={(event) => updateField("country", event.target.value)}
                maxLength={120}
                disabled={isSubmitting}
              />
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>Status</span>
              <select
                style={sharedStyles.input}
                value={values.status}
                onChange={(event) =>
                  updateField("status", event.target.value as CustomerFormValues["status"])
                }
                disabled={isSubmitting}
              >
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>Relationship stage</span>
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
                <option value="lead">Lead</option>
                <option value="prospect">Prospect</option>
                <option value="customer">Customer</option>
              </select>
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>Priority</span>
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
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>Opportunity source</span>
              <input
                style={sharedStyles.input}
                value={values.opportunity_source}
                onChange={(event) => updateField("opportunity_source", event.target.value)}
                maxLength={120}
                disabled={isSubmitting}
              />
            </label>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>Estimated consumption</span>
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
          </div>

          <label style={sharedStyles.field}>
            <span style={sharedStyles.label}>Notes</span>
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
              {isSubmitting ? "Creating…" : "Create customer"}
            </button>
            <Link href="/customers" style={sharedStyles.secondaryButton}>
              Cancel
            </Link>
            <span style={styles.requiredNote}>* Required</span>
          </div>
        </form>
      </section>
    </PageFrame>
  );
}
