export type SampleStatus =
  | "requested"
  | "in_preparation"
  | "delivered"
  | "evaluated"
  | "cancelled";

export type SampleDecision = "pending" | "accepted" | "rejected";

export type RequestedSpec = Record<string, unknown>;
export type SampleProductDefinition = {
  key: string; name_ar: string; name_en: string; active: boolean; default_unit: string | null;
  properties: import('@/lib/spec-rows').SpecTemplateProperty[];
};

export type SampleListItem = {
  id: string;
  customer_id: string;
  /** On a list page: the customer, read once for the page. */
  customer_name?: string | null;
  customer_code?: string | null;
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
  property_values: RequestedSpec | null;
  product_definition: SampleProductDefinition | null;
};

export type CreateSampleRequest = {
  customer_id: string;
  product_type: string;
  status?: SampleStatus;
  is_sample_requested: boolean;
  requested_sample_quantity?: number | null;
  unit?: string | null;
  request_date: string;
  property_values?: RequestedSpec | null;
  notes?: string | null;
};

export type UpdateSampleRequest = {
  product_type?: string;
  is_sample_requested?: boolean;
  requested_sample_quantity?: number | null;
  unit?: string | null;
  request_date?: string;
  property_values?: RequestedSpec | null;
  status?: SampleStatus;
  sample_decision?: SampleDecision | null;
  notes?: string | null;
};

export type SampleDeletionImpact = {
  evaluations: number;
  quotes: number;
  is_blocked: boolean;
};
