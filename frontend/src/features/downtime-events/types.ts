// Machine downtime (PROD-DOWNTIME-001). Durations are decimal minutes as strings, as the API sends them.
export type DowntimeCategory =
  | "planned_maintenance" | "break_meeting" | "no_orders"
  | "changeover_setup" | "breakdown" | "material_shortage" | "waiting_labor" | "quality_issue" | "utilities" | "other";
export type DowntimeStatus = "open" | "closed";
export type DowntimeAction = "close" | "edit" | "delete";

export type DowntimeFilters = {
  work_center_id?: string;
  production_order_id?: string;
  production_run_id?: string;
  category?: DowntimeCategory;
  planned?: "true" | "false";
  status?: DowntimeStatus;
  date_from?: string;
  date_to?: string;
};

export type DowntimeEvent = {
  id: string;
  organization_id: string;
  work_center_id: string;
  production_order_id: string | null;
  production_run_id: string | null;
  start_time: string;
  end_time: string | null;
  duration_minutes: string | null;
  category: DowntimeCategory;
  // Derived from the category: planned stops do not reduce availability.
  planned: boolean;
  reason_code: string | null;
  status: DowntimeStatus;
  created_by_user_id: string;
  closed_by_user_id: string | null;
  updated_by_user_id: string | null;
  created_at: string;
  updated_at: string;
  notes?: string | null;
  labels?: {
    work_center_name: string | null; order_number: string | null; order_status: string | null; run_date: string | null;
    created_by_name: string | null; closed_by_name: string | null;
    elapsed_minutes: string | null;
    actions: DowntimeAction[];
  } | null;
};

export type DowntimeInput = {
  work_center_id?: string | null;
  production_order_id?: string | null;
  production_run_id?: string | null;
  start_time: string;
  end_time?: string | null;
  category: DowntimeCategory;
  reason_code?: string | null;
  notes?: string | null;
};

export type DowntimeSummary = {
  count: number;
  total_minutes: string;
  planned_minutes: string;
  unplanned_minutes: string;
  open_count: number;
  open_minutes_so_far: string;
  mttr_minutes: string | null;
  by_category: { category: DowntimeCategory; planned: boolean; count: number; minutes: string }[];
  by_work_center: { work_center_id: string; work_center_name: string | null; count: number; minutes: string; unplanned_minutes: string }[];
};
