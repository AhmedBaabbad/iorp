import { apiClient } from "@/lib/api-client";
import type { CreateSampleRequest, SampleData, SampleDeletionImpact, SampleListItem, UpdateSampleRequest } from "../types";

const SAMPLES_PATH = "/commercial/samples";
const CUSTOMERS_PATH = "/commercial/customers";

export function listSamples() {
  return apiClient<SampleListItem[]>(SAMPLES_PATH);
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
