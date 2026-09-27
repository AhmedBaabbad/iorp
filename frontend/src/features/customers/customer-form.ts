import { optionalText } from "@/lib/utils";
import type { CustomerCreateRequest, CustomerDetail } from "@/types/customers";

export type CustomerFormValues = {
  name: string;
  sector: string;
  city: string;
  country: string;
  phone: string;
  email: string;
  status: CustomerCreateRequest["status"];
  relationship_stage: CustomerCreateRequest["relationship_stage"];
  opportunity_source: string;
  estimated_consumption: string;
  priority_level: CustomerCreateRequest["priority_level"];
  sales_owner_user_id: string;
  key_influencer_name: string;
  notes: string;
};

export const defaultCustomerFormValues: CustomerFormValues = {
  name: "",
  sector: "",
  city: "",
  country: "",
  phone: "",
  email: "",
  status: "active",
  relationship_stage: "lead",
  opportunity_source: "",
  estimated_consumption: "",
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
    name: values.name.trim(),
    sector: optionalText(values.sector),
    city: optionalText(values.city),
    country: optionalText(values.country),
    phone: optionalText(values.phone),
    email: optionalText(values.email),
    status: values.status,
    relationship_stage: values.relationship_stage,
    opportunity_source: optionalText(values.opportunity_source),
    estimated_consumption: optionalText(values.estimated_consumption),
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
    phone: customer.phone ?? "",
    email: customer.email ?? "",
    status: customer.status,
    relationship_stage: customer.relationship_stage,
    opportunity_source: customer.opportunity_source ?? "",
    estimated_consumption: customer.estimated_consumption ?? "",
    priority_level: customer.priority_level,
    sales_owner_user_id: customer.sales_owner_user_id ?? "",
    key_influencer_name: customer.key_influencer_name ?? "",
    notes: customer.notes ?? "",
  };
}
