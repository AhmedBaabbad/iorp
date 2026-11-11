"use client";

import { useTranslations } from "next-intl";
import { FormSection } from "@/components/forms/FormSection";
import { CountryCityFields } from "@/components/forms/CountryCityFields";
import { ListSelect } from "@/features/masterdata";
import { getEnumLabel } from "@/i18n/enum-helpers";
import { sharedStyles } from "@/styles/shared-styles";
import type { EligibleSalesOwner } from "@/types/customers";
import { hasPrimaryContact, type CustomerFormValues } from "./customer-form";

export function CustomerFields({ values, onChange, disabled, creating, canAssignOwner, eligibleOwners, loadingOwners, ownerName, autoAssigned = false }: {
  values: CustomerFormValues; onChange: (patch: Partial<CustomerFormValues>) => void; disabled: boolean; creating: boolean;
  canAssignOwner: boolean; eligibleOwners: EligibleSalesOwner[]; loadingOwners: boolean; ownerName?: string | null; autoAssigned?: boolean;
}) {
  const t = useTranslations("commercial.customers");
  const enums = useTranslations();
  const text = (field: "name" | "key_influencer_name", label: string, required = false) => <label style={sharedStyles.field}>
    <span style={sharedStyles.label}>{label}{required ? " *" : ""}</span>
    <input style={sharedStyles.input} value={values[field]} maxLength={255} required={required} disabled={disabled}
      onChange={event => onChange({ [field]: event.target.value })} />
  </label>;
  const selection = (field: "status" | "relationship_stage" | "priority_level", label: string, category: "status" | "relationshipStage" | "priorityLevel", choices: string[]) =>
    <label style={sharedStyles.field}><span style={sharedStyles.label}>{label}</span>
      <select style={sharedStyles.input} value={values[field]} disabled={disabled} required
        onChange={event => onChange({ [field]: event.target.value })}>
        {choices.map(value => <option value={value} key={value}>{getEnumLabel("customer", category, value, enums)}</option>)}
      </select>
    </label>;
  return <>
    <FormSection title={t("sections.basic")}>
      {text("name", t("fields.name"), true)}
      <label style={sharedStyles.field}><span style={sharedStyles.label}>{t("fields.sector")}</span>
        <ListSelect style={sharedStyles.input} list="sector" value={values.sector} disabled={disabled} ariaLabel={t("fields.sector")}
          onChange={sector => onChange({ sector })} />
      </label>
      <CountryCityFields value={values} onChange={onChange} disabled={disabled} />
    </FormSection>
    <FormSection title={t("sections.classification")}>
      {selection("status", t("fields.status"), "status", ["active", "inactive", "on_hold", "archived", "blacklisted"])}
      {selection("relationship_stage", t("fields.relationshipStage"), "relationshipStage", ["lead", "contacted", "qualified", "prospect", "negotiating", "trial_customer", "active_customer", "repeat_customer", "strategic_customer"])}
      {selection("priority_level", t("fields.priority"), "priorityLevel", ["low", "medium", "high"])}
      <label style={sharedStyles.field}><span style={sharedStyles.label}>{t("fields.opportunitySource")}</span>
        <ListSelect list="opportunity_source" style={sharedStyles.input} value={values.opportunity_source} disabled={disabled}
          ariaLabel={t("fields.opportunitySource")} onChange={opportunity_source => onChange({ opportunity_source })} />
      </label>
      <label style={sharedStyles.field}><span style={sharedStyles.label}>{t("fields.salesOwner")}{canAssignOwner ? " *" : ""}</span>
        {canAssignOwner ? loadingOwners ? <p>{t("loadingEligibleUsers")}</p> : eligibleOwners.length === 0 ? <p>{t("noEligibleOwners")}</p> :
          <select style={sharedStyles.input} value={values.sales_owner_user_id} disabled={disabled} required
            onChange={event => onChange({ sales_owner_user_id: event.target.value })}>
            <option value="">{t("selectSalesOwner")}</option>
            {eligibleOwners.map(owner => <option key={owner.id} value={owner.id}>{owner.full_name}{owner.roles[0]?.name ? ` — ${owner.roles[0].name}` : ""}</option>)}
          </select> : <><input style={sharedStyles.input} value={ownerName ?? t("noOwner")} disabled readOnly />
            {autoAssigned && <small>{t("salesOwnerAutoAssigned")}</small>}</>}
      </label>
      {text("key_influencer_name", t("fields.keyInfluencerName"))}
      <p style={{ gridColumn: "1 / -1", margin: 0, color: "var(--text-muted)", fontSize: "var(--label-size)" }}>{t("labels.statusVsStageNote")}</p>
    </FormSection>
    {creating && <FormSection title={t("sections.primaryContact")} description={t("primaryContactHint")}>
      {(["contact_name", "contact_phone", "contact_email", "contact_role"] as const).map(field => <label key={field} style={sharedStyles.field}>
        <span style={sharedStyles.label}>{t(`fields.${field}`)}</span>
        <input style={sharedStyles.input} value={values[field]} disabled={disabled} type={field === "contact_email" ? "email" : field === "contact_phone" ? "tel" : "text"}
          maxLength={field === "contact_name" ? 200 : field === "contact_phone" ? 50 : field === "contact_role" ? 120 : 255}
          required={field === "contact_name" && hasPrimaryContact(values)} onChange={event => onChange({ [field]: event.target.value })} />
      </label>)}
    </FormSection>}
    <FormSection title={t("sections.notes")}><label style={{ ...sharedStyles.field, gridColumn: "1 / -1" }}>
      <span style={sharedStyles.label}>{t("fields.notes")}</span>
      <textarea style={sharedStyles.textarea} value={values.notes} disabled={disabled} onChange={event => onChange({ notes: event.target.value })} />
    </label></FormSection>
  </>;
}
