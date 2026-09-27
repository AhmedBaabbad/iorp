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

export function createSampleEvaluation(
  sampleId: string,
  payload: CreateSampleEvaluationRequest,
) {
  return apiClient<SampleEvaluationListItem>(sampleEvaluationsPath(sampleId), {
    method: "POST",
    body: payload,
  });
}
