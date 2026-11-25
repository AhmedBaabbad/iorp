import type {Page} from "@/lib/pagination";
import {queryString, type PageQuery} from "@/lib/page-response";
import { apiClient } from "@/lib/api-client";
import type {
  CreateQualityDefectRequest,
  QualityDefectData,
  QualityDefectListItem,
} from "../types";

function qualityCheckDefectsPath(qualityCheckId: string) {
  return `/quality/quality-checks/${qualityCheckId}/defects`;
}

export function getDefectsByCheck(qualityCheckId:string,filters:PageQuery):Promise<Page<QualityDefectListItem>>;
export function getDefectsByCheck(qualityCheckId:string):Promise<QualityDefectListItem[]>;
export function getDefectsByCheck(qualityCheckId:string,filters?:PageQuery){return apiClient<QualityDefectListItem[]|Page<QualityDefectListItem>>(`${qualityCheckDefectsPath(qualityCheckId)}${queryString(filters)}`);}

export function createDefect(
  qualityCheckId: string,
  payload: CreateQualityDefectRequest,
) {
  return apiClient<QualityDefectData>(qualityCheckDefectsPath(qualityCheckId), {
    method: "POST",
    body: payload,
  });
}

// Several defects of one inspection at once: all are recorded or none (each defect type once per inspection).
export function createDefects(qualityCheckId: string, defects: CreateQualityDefectRequest[]) {
  return apiClient<QualityDefectData[]>(`${qualityCheckDefectsPath(qualityCheckId)}/batch`, { method: "POST", body: { defects } });
}

export function getDefectById(defectId: string) {
  return apiClient<QualityDefectData>(`/quality/quality-defects/${defectId}`);
}
