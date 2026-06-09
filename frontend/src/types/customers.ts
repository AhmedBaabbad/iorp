export type CustomerStatus = "active" | "inactive";

export type RelationshipStage = "lead" | "prospect" | "customer";

export type PriorityLevel = "low" | "medium" | "high";

export type CustomerListItem = {
  id: string;
  customer_code: string;
  name: string;
  sector: string | null;
  city: string | null;
  country: string | null;
  status: CustomerStatus;
  relationship_stage: RelationshipStage;
  priority_level: PriorityLevel;
};

export type CustomerDetail = CustomerListItem & {
  organization_id: string;
  opportunity_source: string | null;
  estimated_consumption: string | null;
  assigned_sales_user_id: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type CustomerCreateRequest = {
  customer_code: string;
  name: string;
  sector?: string | null;
  city?: string | null;
  country?: string | null;
  status: CustomerStatus;
  relationship_stage: RelationshipStage;
  opportunity_source?: string | null;
  estimated_consumption?: string | null;
  priority_level: PriorityLevel;
  notes?: string | null;
};
