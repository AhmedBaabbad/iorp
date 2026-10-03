export type DefectCategory =
  | "dimension"
  | "thickness"
  | "surface"
  | "color"
  | "strength"
  | "winding"
  | "weight"
  | "packaging"
  | "labeling"
  | "finish"
  | "other";

export type DefectSeverity = "minor" | "major" | "critical";

export type QualityDefectListItem = {
  id: string;
  organization_id: string;
  quality_check_id: string;
  production_order_id: string | null;
  production_order_item_id: string | null;
  defect_date: string;
  defect_category: DefectCategory;
  severity: DefectSeverity;
  defect_count: number;
  description: string;
  created_at: string;
  updated_at: string;
};

export type QualityDefectData = QualityDefectListItem & {
  notes: string | null;
  detected_by_user_id: string;
};

export type CreateQualityDefectRequest = {
  production_order_id?: string | null;
  defect_date: string;
  defect_category: DefectCategory;
  severity: DefectSeverity;
  defect_count: number;
  description: string;
  notes?: string | null;
};
