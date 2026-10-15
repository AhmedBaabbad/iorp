import type { OrganizationInput } from "./organization-provisioning";

export type PlatformLoginRequest = {
  mfa_code?: string;
  email: string;
  password: string;
};

export type PlatformLoginResponse = {
  access_token: string;
  token_type: string;
  expires_in?: number;
};

export type PlatformAccount = {
  mfa_enrollment_required?: boolean;
  id: string;
  full_name: string;
  email: string;
  is_root: boolean;
  role: "root" | "admin";
  permissions: string[];
};

export type PlatformAdministrator = {
  id: string;
  full_name: string;
  email: string;
  role: "root" | "admin";
  status: "active" | "inactive";
  is_root: boolean;
  is_bootstrap_root: boolean;
  last_login_at: string | null;
  password_changed_at?: string | null;
  created_at: string;
  updated_at?: string;
  /** SEC-003: the activation link not used yet. */
  activation_pending?: boolean;
  /** On creation only: whether the activation e-mail went out. */
  invitation_sent?: boolean | null;
};

export type PlatformAdministratorCreate = {
  full_name: string;
  email: string;
  role: "root" | "admin";
};

export type PlatformAuthState = {
  account: PlatformAccount | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
};

export type ChangePlatformPasswordRequest = {
  current_password: string;
  new_password: string;
  password_confirmation: string;
};

export type PlatformOrganizationSummary = {
  id: string;
  name: string;
  code: string;
  status: OrganizationLifecycleStatus;
  status_changed_at: string | null;
  status_changed_by: string | null;
  status_changed_by_name: string | null;
  status_change_reason: string | null;
  allowed_transitions?: OrganizationLifecycleStatus[];
  industry_type: string | null;
  timezone: string;
  default_locale: string;
  user_count: number;
  admin_email: string | null;
  root_user_email: string | null;
  has_logo: boolean;
  logo_url: string | null;
  created_at: string;
  updated_at: string;
};

export type OrganizationLifecycleStatus = "provisioning" | "active" | "suspended" | "inactive" | "archived";
export type OrganizationLifecycleAction = "suspend" | "activate" | "deactivate" | "archive";

export type PlatformOrganizationDetail = PlatformOrganizationSummary & {
  root_user: {
    id: string;
    full_name: string;
    email: string;
    status: string;
    last_login_at: string | null;
    activation_pending?: boolean;
  } | null;
  roles: Array<{ id: string; code: string; user_count: number }>;
};

export type CreateOrganizationRequest = {
  organization: OrganizationInput;
  /** SEC-003: no password — the root receives an activation link and chooses their own. */
  organization_admin: { full_name: string; email: string; phone?: string | null };
};

export type CreateOrganizationResponse = {
  message: string;
  organization: {
    id: string; name: string; code: string; status: OrganizationLifecycleStatus;
    default_locale: string; timezone: string; has_logo: boolean; created_at: string;
  };
  root_user: { id: string; full_name: string; email: string; is_organization_root: boolean };
  roles_created: string[];
  organization_admin_email: string;
  invitation_sent?: boolean;
};

export type ResetOrganizationRootPasswordResponse = {
  message: string;
  organization_id: string;
  root_user_email: string;
  sessions_invalidated: boolean;
};
