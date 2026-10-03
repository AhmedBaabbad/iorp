import { apiClient } from "@/lib/api-client";
import type { ParameterInput, ParameterUpdate, Specification, SpecificationInput, SpecificationListItem, SpecificationStatus, TestParameter } from "./types";

const PARAMS = "/quality/quality-test-parameters";
const SPECS = "/quality/quality-specifications";

export const getParameters = (active = false) => apiClient<TestParameter[]>(`${PARAMS}${active ? "?active=true" : ""}`);
export const createParameter = (body: ParameterInput) => apiClient<TestParameter>(PARAMS, { method: "POST", body });
export const updateParameter = (id: string, body: ParameterUpdate) => apiClient<TestParameter>(`${PARAMS}/${id}`, { method: "PATCH", body });
// Width, thickness, weight, length, strength, elongation and the visual checks; codes already present are left alone.
export const addStandardParameters = () => apiClient<TestParameter[]>(`${PARAMS}/standard`, { method: "POST" });

export function getSpecifications(filters: { status?: SpecificationStatus | ""; search?: string } = {}) {
  const query = new URLSearchParams(Object.entries(filters).filter(([, v]) => Boolean(v)) as [string, string][]);
  return apiClient<SpecificationListItem[]>(`${SPECS}${query.size ? `?${query}` : ""}`);
}
export const getSpecification = (id: string) => apiClient<Specification>(`${SPECS}/${id}`);
export const createSpecification = (body: SpecificationInput) => apiClient<Specification>(SPECS, { method: "POST", body });
export const updateSpecification = (id: string, body: Omit<SpecificationInput, "code">) => apiClient<Specification>(`${SPECS}/${id}`, { method: "PATCH", body });
// Puts the draft into force; the revision in force with the same code becomes superseded.
export const activateSpecification = (id: string) => apiClient<Specification>(`${SPECS}/${id}/activate`, { method: "POST" });
// A new draft revision copying the lines.
export const reviseSpecification = (id: string) => apiClient<Specification>(`${SPECS}/${id}/revise`, { method: "POST" });
