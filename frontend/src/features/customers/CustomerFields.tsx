"use client";

import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";
import { CountryCityFields } from "@/components/forms/CountryCityFields";
import { ListSelect } from "@/features/masterdata";
import { getEnumLabel } from "@/i18n/enum-helpers";
import { sharedStyles } from "@/styles/shared-styles";
import type { EligibleSalesOwner } from "@/types/customers";
import type { CustomerFormValues } from "./customer-form";

const styles: Record<string, CSSProperties> = {
  formGrid: { display: "grid", gap: "18px", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" },
  required: { color: "var(--danger)", marginLeft: "2px" },
  note: { color: "var(--text-muted)", fontSize: "13px", margin: 0 },
};

export function CustomerFields({ values, onChange, disabled, canAssignOwner, eligibleOwners, loadingOwners, ownerName, autoAssigned = false }: {
  values: CustomerFormValues; onChange: (patch: Partial<CustomerFormValues>) => void; disabled: boolean;
  canAssignOwner: boolean; eligibleOwners: EligibleSalesOwner[]; loadingOwners: boolean; ownerName?: string | null; autoAssigned?: boolean;
}) {
  const t = useTranslations("commercial.customers");
  const enums = useTranslations();
  const text = (field: "name" | "key_influencer_name", label: string, required = false) => <label style={sharedStyles.field}>
    <span style={sharedStyles.label}>{label}{required && <span style={styles.required} aria-hidden="true"> *</span>}</span>
    <input style={sharedStyles.input} value={values[field]} maxLength={255} required={required} disabled={disabled}
      onChange={event => onChange({ [field]: event.target.value })} />
  </label>;
  const selection = (field: "status" | "relationship_stage" | "priority_level", label: string, category: "status" | "relationshipStage" | "priorityLevel", choices: string[]) =>
    <label style={sharedStyles.field}><span style={sharedStyles.label}>{label}</span>
      <select style={sharedStyles.input} value={values[field]} disabled={disabled}
        onChange={event => onChange({ [field]: event.target.value })}>
        {choices.map(value => <option value={value} key={value}>{getEnumLabel("customer", category, value, enums)}</option>)}
      </select>
    </label>;
  return <>
    <div style={styles.formGrid}>
      {text("name", t("fields.name"), true)}
      <label style={sharedStyles.field}><span style={sharedStyles.label}>{t("fields.sector")}</span>
        <ListSelect style={sharedStyles.input} list="sector" value={values.sector} disabled={disabled} ariaLabel={t("fields.sector")}
          onChange={sector => onChange({ sector })} />
      </label>
      <CountryCityFields value={values} onChange={onChange} disabled={disabled} />
      {selection("status", t("fields.status"), "status", ["active", "inactive", "on_hold", "archived", "blacklisted"])}
      {selection("relationship_stage", t("fields.relationshipStage"), "relationshipStage", ["lead", "contacted", "qualified", "prospect", "negotiating", "trial_customer", "active_customer", "repeat_customer", "strategic_customer"])}
      {selection("priority_level", t("fields.priority"), "priorityLevel", ["low", "medium", "high"])}
      <label style={sharedStyles.field}><span style={sharedStyles.label}>{t("fields.opportunitySource")}</span>
        <ListSelect list="opportunity_source" style={sharedStyles.input} value={values.opportunity_source} disabled={disabled}
          ariaLabel={t("fields.opportunitySource")} onChange={opportunity_source => onChange({ opportunity_source })} />
      </label>
      <label style={sharedStyles.field}><span style={sharedStyles.label}>{t("fields.salesOwner")}{canAssignOwner && <span style={styles.required} aria-hidden="true"> *</span>}</span>
        {canAssignOwner ? loadingOwners ? <p style={styles.note}>{t("loadingEligibleUsers")}</p> : eligibleOwners.length === 0 ? <p style={styles.note}>{t("noEligibleOwners")}</p> :
          <select style={sharedStyles.input} value={values.sales_owner_user_id} disabled={disabled} required
            onChange={event => onChange({ sales_owner_user_id: event.target.value })}>
            <option value="">{t("selectSalesOwner")}</option>
            {eligibleOwners.map(owner => <option key={owner.id} value={owner.id}>{owner.full_name}{owner.roles[0]?.name ? ` — ${owner.roles[0].name}` : ""}</option>)}
          </select> : <><input style={sharedStyles.input} value={ownerName ?? t("noOwner")} disabled readOnly />
            {autoAssigned && <span style={styles.note}>{t("salesOwnerAutoAssigned")}</span>}</>}
      </label>
      {text("key_influencer_name", t("fields.keyInfluencerName"))}
    </div>
    <p style={styles.note}>{t("labels.statusVsStageNote")}</p>
    <label style={sharedStyles.field}>
      <span style={sharedStyles.label}>{t("fields.notes")}</span>
      <textarea style={{...sharedStyles.textarea, minHeight: "110px"}} value={values.notes} disabled={disabled} onChange={event => onChange({ notes: event.target.value })} />
    </label>
  </>;
}
