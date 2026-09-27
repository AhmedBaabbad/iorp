export type ShiftType = "morning" | "evening" | "night" | "custom";

export type ShiftStatus = "active" | "inactive";

export type ShiftListItem = {
  id: string;
  organization_id: string;
  code: string;
  name: string;
  shift_type: ShiftType;
  start_time: string;
  end_time: string;
  duration_hours: string;
  crosses_midnight: boolean;
  status: ShiftStatus;
  created_at: string;
  updated_at: string;
};

export type ShiftData = ShiftListItem & {
  notes: string | null;
};

export type CreateShiftRequest = {
  code: string;
  name: string;
  shift_type: ShiftType;
  start_time: string;
  end_time: string;
  status: ShiftStatus;
  notes?: string | null;
};

export type UpdateShiftRequest = {
  code?: string;
  name?: string;
  shift_type?: ShiftType;
  start_time?: string;
  end_time?: string;
  status?: ShiftStatus;
  notes?: string | null;
};

export type ShiftDeletionImpact = {
  shift_reports: number;
  production_orders: number;
  is_blocked: boolean;
};
