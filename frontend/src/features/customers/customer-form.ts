import { optionalText } from "@/lib/utils";
import type { CustomerCreateRequest, CustomerDetail } from "@/types/customers";

export type CustomerFormValues = {
  name: string;
  sector: string;
  city: string;
  country: string;
  city_other: string;
  contact_name: string;
  contact_phone: string;
  contact_email: string;
  contact_role: string;
  status: CustomerCreateRequest["status"];
  relationship_stage: CustomerCreateRequest["relationship_stage"];
  opportunity_source: string;
  priority_level: CustomerCreateRequest["priority_level"];
  sales_owner_user_id: string;
  key_influencer_name: string;
  notes: string;
};

export const defaultCustomerFormValues: CustomerFormValues = {
  name: "",
  sector: "",
  city: "",
  country: "sa",
  city_other: "",
  contact_name: "",
  contact_phone: "",
  contact_email: "",
  contact_role: "",
  status: "active",
  relationship_stage: "lead",
  opportunity_source: "",
  priority_level: "medium",
  sales_owner_user_id: "",
  key_influencer_name: "",
  notes: "",
};

/**
 * `includeSalesOwner` controls whether sales_owner_user_id is sent at all:
 * Scenario B/edit-without-assign_owner callers must omit the field entirely
 * (not send null/empty) so the backend never sees an attempted change.
 */
export function toCustomerCreateRequest(
  values: CustomerFormValues,
  includeSalesOwner: boolean,
  includePrimaryContact = true,
): CustomerCreateRequest {
  return {
    name: values.name.trim(),
    sector: optionalText(values.sector),
    city: optionalText(values.city),
    country: optionalText(values.country),
    city_other: values.city.endsWith("_other") ? optionalText(values.city_other) : null,
    ...(includePrimaryContact && hasPrimaryContact(values) ? { primary_contact: {
      name: values.contact_name.trim(), phone: optionalText(values.contact_phone),
      email: optionalText(values.contact_email), role: optionalText(values.contact_role),
    } } : {}),
    status: values.status,
    relationship_stage: values.relationship_stage,
    opportunity_source: optionalText(values.opportunity_source),
    priority_level: values.priority_level,
    ...(includeSalesOwner ? { sales_owner_user_id: optionalText(values.sales_owner_user_id) } : {}),
    key_influencer_name: optionalText(values.key_influencer_name),
    notes: optionalText(values.notes),
  };
}

export function toCustomerFormValues(customer: CustomerDetail): CustomerFormValues {
  return {
    name: customer.name,
    sector: customer.sector ?? "",
    city: customer.city ?? "",
    country: customer.country ?? "",
    city_other: customer.city_other ?? "",
    contact_name: "",
    contact_phone: "",
    contact_email: "",
    contact_role: "",
    status: customer.status,
    relationship_stage: customer.relationship_stage,
    opportunity_source: customer.opportunity_source ?? "",
    priority_level: customer.priority_level,
    sales_owner_user_id: customer.sales_owner_user_id ?? "",
    key_influencer_name: customer.key_influencer_name ?? "",
    notes: customer.notes ?? "",
  };
}

export function hasPrimaryContact(values: CustomerFormValues): boolean {
  return [values.contact_name, values.contact_phone, values.contact_email, values.contact_role].some(value => value.trim() !== "");
}
