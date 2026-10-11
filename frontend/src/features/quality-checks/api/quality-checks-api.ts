import { apiClient } from "@/lib/api-client";
import type { Page } from "@/lib/pagination";
import type {
  AwaitingReceipt, AwaitingReturn, BatchShipment, LotDecisionRequest, ReturnDecisionRequest, CloseQualityCheckRequest, CreateQualityCheckRequest, InspectableOrder, MeasurementInput, PlanCandidate, QualityCheckData, QualityCheckListFilters,
  QualityCheckListItem, SampleOption, UpdateQualityCheckRequest,
} from "../types";

const PATH = "/quality/quality-checks";

// One page of inspections (ARCH-PAGE-001): the filters plus page and page_size.
export function getQualityChecks(filters: QualityCheckListFilters & { page?: string | number; page_size?: string | number } = {}) {
  const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => Boolean(value)).map(([k, v]) => [k, String(v)]));
  return apiClient<Page<QualityCheckListItem>>(`${PATH}${query.size ? `?${query}` : ""}`);
}

export function getQualityCheckById(id: string) {
  return apiClient<QualityCheckData>(`${PATH}/${id}`);
}

// Opens an inspection; a production lot needs its order running, held or completed.
export function createQualityCheck(body: CreateQualityCheckRequest) {
  return apiClient<QualityCheckData>(PATH, { method: "POST", body });
}

export function updateQualityCheck(id: string, body: UpdateQualityCheckRequest) {
  return apiClient<QualityCheckData>(`${PATH}/${id}`, { method: "PATCH", body });
}

export function startQualityCheck(id: string) {
  return apiClient<QualityCheckData>(`${PATH}/${id}/start`, { method: "POST" });
}

// Result and quantities; a rejected quantity opens a rejection awaiting a decision.
export function closeQualityCheck(id: string, body: CloseQualityCheckRequest) {
  return apiClient<QualityCheckData>(`${PATH}/${id}/close`, { method: "POST", body });
}

export function cancelQualityCheck(id: string, reason: string) {
  return apiClient<QualityCheckData>(`${PATH}/${id}/cancel`, { method: "POST", body: { reason } });
}

// Orders a check of this type can be opened on: a reinspection also lists closed orders (retained samples).
export function getInspectableOrders(search = "", checkType?: string) {
  return apiClient<InspectableOrder[]>(`${PATH}/lookups/orders?q=${encodeURIComponent(search)}${checkType ? `&check_type=${checkType}` : ""}`);
}

export function getInspectableSamples(search = "") {
  return apiClient<SampleOption[]>(`${PATH}/lookups/samples?q=${encodeURIComponent(search)}`);
}

// QUAL-SPEC-001: the specifications in force for the inspected product, applying one as the plan, and recording a measurement.
// Every specification in force, those for the order's product first, with the lot values each still needs.
export function getPlanCandidates(id: string) {
  return apiClient<PlanCandidate[]>(`${PATH}/${id}/specifications`);
}

export function applyPlan(id: string, specificationId: string, lotValues?: Record<string, string>) {
  return apiClient<QualityCheckData>(`${PATH}/${id}/plan`, { method: "POST",
    body: { specification_id: specificationId, lot_values: lotValues && Object.keys(lotValues).length ? lotValues : null } });
}

export function recordMeasurement(id: string, measurementId: string, body: MeasurementInput) {
  return apiClient<QualityCheckData>(`${PATH}/${id}/measurements/${measurementId}`, { method: "PUT", body });
}

// QUAL-RET-001: returned goods received for quality, an inspection per returned line, the split decision, containment.
export function getAwaitingReturns(search = "") {
  return apiClient<AwaitingReturn[]>(`/quality/returns/awaiting?q=${encodeURIComponent(search)}`);
}

export function openReturnInspection(returnLineId: string) {
  return apiClient<QualityCheckData>(`/quality/returns/lines/${returnLineId}/inspection`, { method: "POST" });
}

export function decideReturn(id: string, body: ReturnDecisionRequest) {
  return apiClient<QualityCheckData>(`${PATH}/${id}/return-decision`, { method: "POST", body });
}

export function getBatchShipments(id: string) {
  return apiClient<BatchShipment[]>(`${PATH}/${id}/batch-shipments`);
}

// QUAL-INC-001: received lots awaiting inspection, an inspection per lot, the lot decision.
export function getAwaitingLots(search = "") {
  return apiClient<AwaitingReceipt[]>(`/quality/incoming/awaiting?q=${encodeURIComponent(search)}`);
}

export function openIncomingInspection(receiptLineId: string) {
  return apiClient<QualityCheckData>(`/quality/incoming/lines/${receiptLineId}/inspection`, { method: "POST" });
}

export function decideLot(id: string, body: LotDecisionRequest) {
  return apiClient<QualityCheckData>(`${PATH}/${id}/lot-decision`, { method: "POST", body });
}
