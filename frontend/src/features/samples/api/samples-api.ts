import { apiClient } from "@/lib/api-client";
import type { Page } from "@/lib/pagination";
import type { CreateSampleRequest, SampleData, SampleDeletionImpact, SampleListItem, UpdateSampleRequest, SampleProductDefinition } from "../types";

const SAMPLES_PATH = "/commercial/samples";
const CUSTOMERS_PATH = "/commercial/customers";
export const getSampleProducts = () => apiClient<SampleProductDefinition[]>(`${SAMPLES_PATH}/product-options`);

/** One page of samples, searched and filtered by the server: query = "page=2&search=gulf&status=requested". */
export function listSamples(query = "") {
  return apiClient<Page<SampleListItem>>(query ? `${SAMPLES_PATH}?${query}` : SAMPLES_PATH);
}

export function getSampleById(sampleId: string) {
  return apiClient<SampleData>(`${SAMPLES_PATH}/${sampleId}`);
}

export function createSample(payload: CreateSampleRequest) {
  const { customer_id, ...body } = payload;

  return apiClient<SampleData>(`${CUSTOMERS_PATH}/${customer_id}/samples`, {
    method: "POST",
    body,
  });
}

export function updateSample(sampleId: string, payload: UpdateSampleRequest) {
  return apiClient<SampleData>(`${SAMPLES_PATH}/${sampleId}`, {
    method: "PATCH",
    body: payload,
  });
}

export function deleteSample(sampleId: string) {
  return apiClient<{ status: string }>(`${SAMPLES_PATH}/${sampleId}`, {
    method: "DELETE",
  });
}

export function getSampleDeletionImpact(sampleId: string) {
  return apiClient<SampleDeletionImpact>(`${SAMPLES_PATH}/${sampleId}/deletion-impact`);
}
