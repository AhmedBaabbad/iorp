export type DowntimeCategory =
  | "machine"
  | "material"
  | "manpower"
  | "quality"
  | "utilities"
  | "setup"
  | "other";

export type DowntimeStatus = "open" | "closed";

export type DowntimeEventListFilters = {
  work_center_id?: string;
  production_order_id?: string;
  status?: DowntimeStatus;
  category?: DowntimeCategory;
};

export type DowntimeEventListItem = {
  id: string;
  organization_id: string;
  work_center_id: string;
  production_order_id: string | null;
  start_time: string;
  end_time: string | null;
  duration_minutes: number | null;
  category: DowntimeCategory;
  reason_code: string | null;
  status: DowntimeStatus;
  created_by_user_id: string;
  created_at: string;
  updated_at: string;
};

export type DowntimeEventData = DowntimeEventListItem & {
  notes: string | null;
};

export type CreateDowntimeEventRequest = {
  work_center_id: string;
  production_order_id?: string | null;
  start_time: string;
  end_time?: string | null;
  category: DowntimeCategory;
  reason_code?: string | null;
  notes?: string | null;
};

export type EndDowntimeEventRequest = {
  end_time: string;
};
