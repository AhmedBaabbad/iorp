// Master data (MD-001): the organization's products with their specification templates, and its general settings.
import type { SpecTemplateProperty } from "@/lib/spec-rows";

export type ProductKind = "finished" | "material";
export const PRODUCT_KINDS: ProductKind[] = ["finished", "material"];
export type PropertyKind = SpecTemplateProperty["kind"];
export const PROPERTY_KINDS: PropertyKind[] = ["number", "text", "choice"];
export type ProductProperty = SpecTemplateProperty;

export type ProductInput = {
  key?: string | null; name_ar: string; name_en: string; kind: ProductKind; default_unit: string | null; active: boolean; notes: string | null;
  properties: ProductProperty[];
};
export type Product = Required<Omit<ProductInput, "key">> & { id: string; code: string; key: string; actions: "edit"[]; created_at: string; updated_at: string };

// A product type other modules stored as free text before the product list, where it is used and how often.
export type LegacyValue = { value: string; uses: Record<string, number>; total: number; suggested_key: string };
export type BusinessSettings = { vat_rate: string; default_currency: "SAR" | "USD"; currencies: string[] };

// Reference lists (MD-002): sectors, opportunity sources, countries and cities; a city belongs to a country.
export type ListName = "sector" | "opportunity_source" | "country" | "city" | "downtime_reason" | "waste_reason" | "workforce_skill" | "test_method" | "supplier_category" | "material_category" | "defect_category" | "rejection_reason" | "complaint_category" | "interaction_type" | "vehicle_type";
export const LIST_NAMES: ListName[] = ["sector", "opportunity_source", "country", "city", "downtime_reason", "waste_reason", "workforce_skill", "test_method", "supplier_category", "material_category", "defect_category", "rejection_reason", "complaint_category", "interaction_type", "vehicle_type"];
/** MD-003: the lists grouped by the department that uses them (the reference lists page). */
export const LIST_GROUPS: { group: string; lists: ListName[] }[] = [
  { group: "commercial", lists: ["sector", "opportunity_source", "country", "city", "complaint_category", "interaction_type"] },
  { group: "procurement", lists: ["supplier_category", "material_category"] },
  { group: "production", lists: ["downtime_reason", "waste_reason", "workforce_skill"] },
  { group: "quality", lists: ["defect_category", "rejection_reason", "test_method"] },
  { group: "shipping", lists: ["vehicle_type"] },
];
export type ListItem = { id: string; list: ListName; key: string; name_ar: string; name_en: string; parent_key: string | null; active: boolean;
  sort_order: number 
  uses?: number; protected?: boolean;  // MD-003: records storing it (deletable at 0); written by the system itself
};
export type ListItemInput = { key?: string | null; name_ar: string; name_en: string; parent_key?: string | null };
