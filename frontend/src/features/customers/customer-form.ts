import { optionalText } from "@/lib/utils";
import type { CustomerCreateRequest } from "@/types/customers";

export type CustomerFormValues = {
  customer_code: string;
  name: string;
  sector: string;
  city: string;
  country: string;
  status: CustomerCreateRequest["status"];
  relationship_stage: CustomerCreateRequest["relationship_stage"];
  opportunity_source: string;
  estimated_consumption: string;
  priority_level: CustomerCreateRequest["priority_level"];
  notes: string;
};

export const defaultCustomerFormValues: CustomerFormValues = {
  customer_code: "",
  name: "",
  sector: "",
  city: "",
  country: "",
  status: "active",
  relationship_stage: "lead",
  opportunity_source: "",
  estimated_consumption: "",
  priority_level: "medium",
  notes: "",
};

export function toCustomerCreateRequest(values: CustomerFormValues): CustomerCreateRequest {
  return {
    customer_code: values.customer_code.trim(),
    name: values.name.trim(),
    sector: optionalText(values.sector),
    city: optionalText(values.city),
    country: optionalText(values.country),
    status: values.status,
    relationship_stage: values.relationship_stage,
    opportunity_source: optionalText(values.opportunity_source),
    estimated_consumption: optionalText(values.estimated_consumption),
    priority_level: values.priority_level,
    notes: optionalText(values.notes),
  };
}
