import { apiClient } from "@/lib/api-client";
import type {
  CreateSampleEvaluationRequest,
  SampleEvaluationListItem,
} from "../types";

function sampleEvaluationsPath(sampleId: string) {
  return `/commercial/samples/${sampleId}/evaluations`;
}

export function listSampleEvaluations(sampleId: string) {
  return apiClient<SampleEvaluationListItem[]>(sampleEvaluationsPath(sampleId));
}

/** Corrects an evaluation (commercial:evaluations:update). */
export function updateSampleEvaluation(evaluationId: string, payload: Partial<CreateSampleEvaluationRequest>) {
  return apiClient<SampleEvaluationListItem>(`/commercial/sample-evaluations/${evaluationId}`, { method: "PATCH", body: payload });
}

/** Removes an evaluation recorded by mistake (commercial:evaluations:delete). */
export function deleteSampleEvaluation(evaluationId: string) {
  return apiClient<void>(`/commercial/sample-evaluations/${evaluationId}`, { method: "DELETE" });
}

export function createSampleEvaluation(
  sampleId: string,
  payload: CreateSampleEvaluationRequest,
) {
  return apiClient<SampleEvaluationListItem>(sampleEvaluationsPath(sampleId), {
    method: "POST",
    body: payload,
  });
}
