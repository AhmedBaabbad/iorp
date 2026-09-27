export type SampleStatus =
  | "requested"
  | "in_preparation"
  | "delivered"
  | "evaluated"
  | "cancelled";

export type SampleDecision = "pending" | "accepted" | "rejected";

export type RequestedSpec = Record<string, unknown>;

export type SampleListItem = {
  id: string;
  customer_id: string;
  sample_code: string;
  product_type: string;
  requested_spec_json: RequestedSpec | null;
  is_sample_requested: boolean;
  requested_sample_quantity: string | null;
  unit: string | null;
  request_date: string;
  status: SampleStatus;
  sample_decision: SampleDecision | null;
  created_by_user_id: string;
  created_by_name: string | null;
  created_at: string;
  updated_at: string;
};

export type SampleData = SampleListItem & {
  notes: string | null;
};

export type CreateSampleRequest = {
  customer_id: string;
  product_type: string;
  status?: SampleStatus;
  is_sample_requested: boolean;
  requested_sample_quantity?: number | null;
  unit?: string | null;
  request_date: string;
  requested_spec_json?: RequestedSpec | null;
  notes?: string | null;
};

export type UpdateSampleRequest = {
  product_type?: string;
  is_sample_requested?: boolean;
  requested_sample_quantity?: number | null;
  unit?: string | null;
  request_date?: string;
  requested_spec_json?: RequestedSpec | null;
  status?: SampleStatus;
  sample_decision?: SampleDecision | null;
  notes?: string | null;
};

export type SampleDeletionImpact = {
  evaluations: number;
  quotes: number;
  is_blocked: boolean;
};
