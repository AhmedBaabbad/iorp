export type CustomerStatus = "active" | "inactive" | "on_hold" | "archived" | "blacklisted";

export type RelationshipStage =
  | "lead"
  | "contacted"
  | "qualified"
  | "prospect"
  | "negotiating"
  | "trial_customer"
  | "active_customer"
  | "repeat_customer"
  | "strategic_customer";

export type PriorityLevel = "low" | "medium" | "high";

export type RoleSummary = {
  id: string;
  code: string;
  name: string;
};

export type WorkforceSummary = {
  id: string;
  employee_code: string;
  worker_type: string;
  display_name: string | null;
};

export type SalesOwnerSummary = {
  id: string;
  full_name: string;
  email: string;
  roles: RoleSummary[];
  workforce: WorkforceSummary | null;
};

export type CreatedBySummary = {
  id: string;
  full_name: string;
};

export type EligibleSalesOwner = {
  id: string;
  full_name: string;
  email: string;
  status: string;
  roles: RoleSummary[];
  workforce: WorkforceSummary | null;
};

export type CustomerListItem = {
  id: string;
  customer_code: string;
  name: string;
  sector: string | null;
  city: string | null;
  country: string | null;
  phone: string | null;
  email: string | null;
  status: CustomerStatus;
  relationship_stage: RelationshipStage;
  priority_level: PriorityLevel;
  sales_owner_user_id: string | null;
  sales_owner: SalesOwnerSummary | null;
  created_by: CreatedBySummary | null;
};

export type CustomerDetail = CustomerListItem & {
  organization_id: string;
  opportunity_source: string | null;
  estimated_consumption: string | null;
  key_influencer_name: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type CustomerCreateRequest = {
  name: string;
  sector?: string | null;
  city?: string | null;
  country?: string | null;
  phone?: string | null;
  email?: string | null;
  status: CustomerStatus;
  relationship_stage: RelationshipStage;
  opportunity_source?: string | null;
  estimated_consumption?: string | null;
  priority_level: PriorityLevel;
  sales_owner_user_id?: string | null;
  key_influencer_name?: string | null;
  notes?: string | null;
};

export type CustomerUpdateRequest = Partial<CustomerCreateRequest>;

export type CustomerDeletionImpact = {
  production_demands: number;
  interactions: number;
  follow_ups: number;
  samples: number;
  quotes: number;
  orders: number;
  is_blocked: boolean;
};
