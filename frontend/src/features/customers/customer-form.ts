import { optionalText } from "@/lib/utils";
import type { CustomerCreateRequest, CustomerDetail } from "@/types/customers";

export type CustomerFormValues = {
  name_ar: string;
  name_en: string;
  sector: string;
  city: string;
  country: string;
  city_other: string;
  status: CustomerCreateRequest["status"];
  relationship_stage: CustomerCreateRequest["relationship_stage"];
  opportunity_source: string;
  priority_level: CustomerCreateRequest["priority_level"];
  sales_owner_user_id: string;
  key_influencer_name: string;
  notes: string;
};

export const defaultCustomerFormValues: CustomerFormValues = {
  name_ar: "",
  name_en: "",
  sector: "",
  city: "",
  country: "sa",
  city_other: "",
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
): CustomerCreateRequest {
  return {
    name_ar: optionalText(values.name_ar),
    name_en: optionalText(values.name_en),
    sector: optionalText(values.sector),
    city: optionalText(values.city),
    country: optionalText(values.country),
    city_other: values.city.endsWith("_other") ? optionalText(values.city_other) : null,
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
    name_ar: customer.name_ar ?? "",
    name_en: customer.name_en ?? "",
    sector: customer.sector ?? "",
    city: customer.city ?? "",
    country: customer.country ?? "",
    city_other: customer.city_other ?? "",
    status: customer.status,
    relationship_stage: customer.relationship_stage,
    opportunity_source: customer.opportunity_source ?? "",
    priority_level: customer.priority_level,
    sales_owner_user_id: customer.sales_owner_user_id ?? "",
    key_influencer_name: customer.key_influencer_name ?? "",
    notes: customer.notes ?? "",
  };
}

export function hasCustomerName(values: Pick<CustomerFormValues, "name_ar" | "name_en">): boolean {
  return Boolean(values.name_ar.trim() || values.name_en.trim());
}
