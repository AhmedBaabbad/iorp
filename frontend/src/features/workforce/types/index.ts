export type WorkforceMemberStatus = "active" | "inactive" | "suspended" | "terminated";

export type EmploymentType = "employee" | "contractor" | "temporary";

export type WorkerType =
  | "driver"
  | "factory_manager"
  | "production_manager"
  | "supervisor"
  | "operator"
  | "technician"
  | "maintenance_technician"
  | "helper"
  | "quality_inspector"
  | "warehouse_staff"
  | "logistics_coordinator"
  | "sales_manager"
  | "sales_rep"
  | "procurement_officer"
  | "hr_officer"
  | "accountant"
  | "safety_officer"
  | "admin_support";

export type LinkedUser = {
  id: string;
  full_name: string;
  email: string;
  status: string;
  roles: string[];
};

export type WorkforceMember = {
  id: string;
  organization_id: string;
  employee_code: string;
  full_name: string;
  display_name: string | null;
  phone: string | null;
  email: string | null;
  national_id: string | null;
  worker_type: WorkerType;
  employment_type: EmploymentType;
  status: WorkforceMemberStatus;
  is_system_user: boolean;
  user_id: string | null;
  linked_user: LinkedUser | null;
  primary_skill: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type WorkforceMemberListItem = {
  id: string;
  employee_code: string;
  full_name: string;
  worker_type: WorkerType;
  employment_type: EmploymentType;
  status: WorkforceMemberStatus;
  is_system_user: boolean;
  user_id: string | null;
  phone: string | null;
};

export type CreateWorkforceMemberRequest = {
  full_name: string;
  worker_type: WorkerType;
  employment_type: EmploymentType;
  display_name?: string | null;
  phone?: string | null;
  email?: string | null;
  national_id?: string | null;
  primary_skill?: string | null;
  notes?: string | null;
};

export type UpdateWorkforceMemberRequest = Partial<CreateWorkforceMemberRequest> & {
  status?: WorkforceMemberStatus;
};

export type LinkUserRequest = {
  user_id: string;
};

export type WorkforceMemberDeletionImpact = {
  is_blocked: boolean;
};

export type WorkforceMemberDeleteResult = {
  id: string;
  deleted: boolean;
};

export type WorkforceMemberFilters = {
  worker_type?: WorkerType | "";
  status?: WorkforceMemberStatus | "";
  employment_type?: EmploymentType | "";
};
