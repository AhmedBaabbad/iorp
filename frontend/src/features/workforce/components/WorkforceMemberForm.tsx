"use client";
import { ReferenceTextSelect } from "@/features/reference-directory/ReferenceTextSelect";


import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";
import { useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { SuccessModal } from "@/components/ui/SuccessModal";
import { useEnumLabel } from "@/i18n/enum-helpers";
import { ApiClientError } from "@/lib/api-client";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { optionalText } from "@/lib/utils";
import { sharedStyles } from "@/styles/shared-styles";
import {
  createWorkforceMember,
  getWorkforceMemberById,
  updateWorkforceMember,
} from "../api/workforce-api";
import type {
  CreateWorkforceMemberRequest,
  EmploymentType,
  UpdateWorkforceMemberRequest,
  WorkforceMember,
  WorkforceMemberStatus,
  WorkerType,
} from "../types";

type Mode = "create" | "edit";

type FormValues = {
  full_name: string;
  display_name: string;
  worker_type: WorkerType;
  employment_type: EmploymentType;
  status: WorkforceMemberStatus;
  phone: string;
  email: string;
  national_id: string;
  primary_skill: string;
  notes: string;
};

const styles: Record<string, CSSProperties> = {
  panel: {
    background: "var(--surface)",
    border: "1px solid var(--border-strong)",
    borderRadius: "8px",
    boxShadow: "0 16px 40px rgba(31, 41, 51, 0.06)",
  },
  form: { display: "grid", gap: "18px", padding: "24px" },
  formGrid: {
    display: "grid",
    gap: "18px",
    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  },
  actions: { display: "flex", flexWrap: "wrap", gap: "12px", alignItems: "center" },
  required: { color: "var(--danger)", marginLeft: "2px" },
  requiredNote: { color: "var(--text-muted)", fontSize: "13px", marginLeft: "auto" },
};

const workerTypes: WorkerType[] = [
  "driver",
  "factory_manager",
  "production_manager",
  "supervisor",
  "operator",
  "technician",
  "maintenance_technician",
  "helper",
  "quality_inspector",
  "warehouse_staff",
  "logistics_coordinator",
  "sales_manager",
  "sales_rep",
  "procurement_officer",
  "hr_officer",
  "accountant",
  "safety_officer",
  "admin_support",
];
const employmentTypes: EmploymentType[] = ["employee", "contractor", "temporary"];
const statuses: WorkforceMemberStatus[] = ["active", "inactive", "suspended", "terminated"];

const defaultValues: FormValues = {
  full_name: "",
  display_name: "",
  worker_type: "operator",
  employment_type: "employee",
  status: "active",
  phone: "",
  email: "",
  national_id: "",
  primary_skill: "",
  notes: "",
};

export function WorkforceMemberForm({ mode }: { mode: Mode }) {
  const params = useParams<{ id: string }>();
  const memberId = params.id;
  const router = useRouter();
  const t = useTranslations("workforce.members");
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const enumLabel = useEnumLabel();
  const [values, setValues] = useState<FormValues>(defaultValues);
  const [member, setMember] = useState<WorkforceMember | null>(null);
  const [isLoading, setIsLoading] = useState(mode === "edit");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isNotFound, setIsNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successRedirect, setSuccessRedirect] = useState<string | null>(null);

  useEffect(() => {
    if (mode !== "edit") return;
    let isMounted = true;

    async function loadMember() {
      try {
        setIsLoading(true);
        setError(null);
        setIsNotFound(false);
        const response = await getWorkforceMemberById(memberId);
        if (!isMounted) return;
        setMember(response);
        setValues(fromMember(response));
      } catch (caughtError) {
        if (!isMounted) return;
        if (caughtError instanceof ApiClientError && caughtError.status === 404) {
          setIsNotFound(true);
          return;
        }
        setError(getApiErrorMessage(caughtError, messages));
      } finally {
        if (isMounted) setIsLoading(false);
      }
    }

    void loadMember();
    return () => {
      isMounted = false;
    };
  }, [memberId, mode, messages]);

  function updateField<TField extends keyof FormValues>(field: TField, value: FormValues[TField]) {
    setValues((current) => ({ ...current, [field]: value }));
  }

  async function handleSubmit(event: { preventDefault(): void }) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      if (mode === "create") {
        const created = await createWorkforceMember(toCreateRequest(values));
        setSuccessRedirect(`/workforce/${created.id}`);
      } else {
        const updated = await updateWorkforceMember(memberId, toUpdateRequest(values));
        setSuccessRedirect(`/workforce/${updated.id}`);
      }
    } catch (caughtError) {
      setError(caughtError instanceof ApiClientError && caughtError.status === 409 && caughtError.message === "WORKFORCE_NATIONAL_ID_EXISTS"
        ? t("nationalIdExists") : getApiErrorMessage(caughtError, messages));
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isLoading) {
    return (
      <PageFrame section="Workforce" title={t(mode === "create" ? "createTitle" : "editTitle")}>
        <div style={{ ...sharedStyles.state, background: "var(--surface)" }}>
          {messages("loading.default")}
        </div>
      </PageFrame>
    );
  }

  if (isNotFound) {
    return (
      <PageFrame section="Workforce" title={t("notFound")}>
        <section style={{ ...sharedStyles.state, background: "var(--surface)" }}>
          <h2 style={{ margin: "0 0 8px", fontSize: "20px" }}>{t("notFound")}</h2>
          <p style={{ margin: "0 0 18px" }}>{t("notFoundDescription")}</p>
          <Link href="/workforce" style={sharedStyles.button}>{t("returnToList")}</Link>
        </section>
      </PageFrame>
    );
  }

  return (
    <>
      {successRedirect ? (
        <SuccessModal
          message={t(mode === "create" ? "createSuccess" : "updateSuccess")}
          okLabel={common("actions.ok")}
          onOk={() => router.replace(successRedirect)}
        />
      ) : null}
      <PageFrame
        section="Workforce"
        title={t(mode === "create" ? "createTitle" : "editTitle")}
        subtitle={t(mode === "create" ? "createSubtitle" : "editSubtitle")}
        action={
          <Link
            href={mode === "edit" && member ? `/workforce/${member.id}` : "/workforce"}
            style={sharedStyles.secondaryButton}
          >
            {mode === "edit" ? t("backToDetail") : t("backToList")}
          </Link>
        }
      >
        <section style={styles.panel}>
          <form style={styles.form} onSubmit={handleSubmit}>
            <div style={styles.formGrid}>
              {mode === "edit" && member ? (
                <label style={sharedStyles.field}>
                  <span style={sharedStyles.label}>{t("fields.employeeCode")}</span>
                  <input style={sharedStyles.input} value={member.employee_code} disabled readOnly />
                </label>
              ) : null}

              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>
                  {t("fields.fullName")}
                  <span style={styles.required} aria-hidden="true"> *</span>
                </span>
                <input
                  style={sharedStyles.input}
                  value={values.full_name}
                  onChange={(event) => updateField("full_name", event.target.value)}
                  maxLength={255}
                  disabled={isSubmitting}
                  required
                />
              </label>

              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>{t("fields.displayName")}</span>
                <input
                  style={sharedStyles.input}
                  value={values.display_name}
                  onChange={(event) => updateField("display_name", event.target.value)}
                  maxLength={255}
                  disabled={isSubmitting}
                />
              </label>

              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>
                  {t("fields.workerType")}
                  <span style={styles.required} aria-hidden="true"> *</span>
                </span>
                <select
                  style={sharedStyles.input}
                  value={values.worker_type}
                  onChange={(event) => updateField("worker_type", event.target.value as WorkerType)}
                  disabled={isSubmitting}
                  required
                >
                  {workerTypes.map((value) => (
                    <option key={value} value={value}>
                      {enumLabel("workforceMember", "workerType", value)}
                    </option>
                  ))}
                </select>
              </label>

              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>
                  {t("fields.employmentType")}
                  <span style={styles.required} aria-hidden="true"> *</span>
                </span>
                <select
                  style={sharedStyles.input}
                  value={values.employment_type}
                  onChange={(event) =>
                    updateField("employment_type", event.target.value as EmploymentType)
                  }
                  disabled={isSubmitting}
                  required
                >
                  {employmentTypes.map((value) => (
                    <option key={value} value={value}>
                      {enumLabel("workforceMember", "employmentType", value)}
                    </option>
                  ))}
                </select>
              </label>

              {mode === "edit" ? (
                <label style={sharedStyles.field}>
                  <span style={sharedStyles.label}>{t("fields.status")}</span>
                  <select
                    style={sharedStyles.input}
                    value={values.status}
                    onChange={(event) => updateField("status", event.target.value as WorkforceMemberStatus)}
                    disabled={isSubmitting}
                  >
                    {statuses.map((value) => (
                      <option key={value} value={value}>
                        {enumLabel("workforceMember", "status", value)}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}

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
                <span style={sharedStyles.label}>{t("fields.nationalId")}</span>
                <input style={sharedStyles.input} value={values.national_id} maxLength={40}
                  onChange={event => updateField("national_id", event.target.value)} disabled={isSubmitting} />
              </label>
              <label style={sharedStyles.field}>
                <span style={sharedStyles.label}>{t("fields.primarySkill")}</span>
                <ReferenceTextSelect list="workforce_skill" value={values.primary_skill} onChange={v=>updateField("primary_skill",v)} disabled={isSubmitting}/>
              </label>
            </div>

            <label style={sharedStyles.field}>
              <span style={sharedStyles.label}>{t("fields.notes")}</span>
              <textarea
                style={{ ...sharedStyles.textarea, minHeight: "110px" }}
                value={values.notes}
                onChange={(event) => updateField("notes", event.target.value)}
                disabled={isSubmitting}
              />
            </label>

            {error ? <div style={sharedStyles.error} role="alert">{error}</div> : null}

            <div style={styles.actions}>
              <button style={sharedStyles.button} type="submit" disabled={isSubmitting}>
                {isSubmitting
                  ? messages("loading.saving")
                  : t(mode === "create" ? "createButton" : "updateButton")}
              </button>
              <Link href="/workforce" style={sharedStyles.secondaryButton}>
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

function fromMember(member: WorkforceMember): FormValues {
  return {
    full_name: member.full_name,
    display_name: member.display_name ?? "",
    worker_type: member.worker_type,
    employment_type: member.employment_type,
    status: member.status,
    phone: member.phone ?? "",
    email: member.email ?? "",
    national_id: member.national_id ?? "",
    primary_skill: member.primary_skill ?? "",
    notes: member.notes ?? "",
  };
}

function toCreateRequest(values: FormValues): CreateWorkforceMemberRequest {
  return {
    full_name: values.full_name,
    worker_type: values.worker_type,
    employment_type: values.employment_type,
    display_name: optionalText(values.display_name) ?? null,
    phone: optionalText(values.phone) ?? null,
    email: optionalText(values.email) ?? null,
    national_id: optionalText(values.national_id) ?? null,
    primary_skill: optionalText(values.primary_skill) ?? null,
    notes: optionalText(values.notes) ?? null,
  };
}

function toUpdateRequest(values: FormValues): UpdateWorkforceMemberRequest {
  return {
    ...toCreateRequest(values),
    status: values.status,
  };
}
