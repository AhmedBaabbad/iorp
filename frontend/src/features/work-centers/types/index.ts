export type WorkCenterType =
  | "extrusion"
  | "rewinding"
  | "packing"
  | "quality_station"
  | "generic";

export type WorkCenterStatus = "active" | "inactive" | "under_maintenance";

export type WorkCenterListItem = {
  id: string;
  organization_id: string;
  code: string;
  name: string;
  center_type: WorkCenterType;
  status: WorkCenterStatus;
  location: string | null;
  commissioned_date: string | null;
  created_at: string;
  updated_at: string;
};

export type WorkCenterData = WorkCenterListItem & {
  notes: string | null;
};

export type CreateWorkCenterRequest = {
  name: string;
  center_type: WorkCenterType;
  status: WorkCenterStatus;
  location?: string | null;
  commissioned_date?: string | null;
  notes?: string | null;
};

export type UpdateWorkCenterRequest = {
  name?: string;
  center_type?: WorkCenterType;
  status?: WorkCenterStatus;
  location?: string | null;
  commissioned_date?: string | null;
  notes?: string | null;
};

export type WorkCenterDeleteSummary = {
  production_orders_count: number;
  shifts_count: number;
  shift_reports_count: number;
  downtime_records_count: number;
  waste_records_count: number;
  production_outputs_count: number;
};
