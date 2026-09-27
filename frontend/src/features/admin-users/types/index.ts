export type UserStatus = "active" | "inactive" | "locked";

export type AdminUserRoleRef = {
  id: string;
  name: string;
  code: string;
};

export type AdminUserListItem = {
  id: string;
  full_name: string;
  email: string;
  phone: string | null;
  preferred_locale: "ar" | "en" | null;
  status: UserStatus;
  is_organization_root: boolean;
  roles: AdminUserRoleRef[];
  created_at: string;
};

export type AdminUserDetail = AdminUserListItem & {
  organization_id: string;
  last_login_at: string | null;
  failed_login_attempts: number;
  auto_locked_until: string | null;
  last_failed_login_at: string | null;
  permissions: string[];
  updated_at: string;
};

export type AdminUserCreateRequest = {
  full_name: string;
  email: string;
  phone?: string | null;
  password: string;
  status?: UserStatus;
  role_codes?: string[];
  preferred_locale?: "ar" | "en" | null;
};

export type AdminUserUpdateRequest = {
  full_name?: string;
  email?: string;
  phone?: string | null;
  preferred_locale?: "ar" | "en" | null;
};

export type AdminUserRoleAssignRequest = {
  role_id: string;
};

export type AssignedRole = AdminUserRoleRef & {
  is_system: boolean;
  is_protected: boolean;
  assigned_by: { id: string; full_name: string } | null;
  assigned_at: string;
};

export type UserRolesResponse = { roles: AssignedRole[] };

export type AssignableRole = AdminUserRoleRef & {
  is_system: boolean;
  is_protected: boolean;
  permission_count: number;
};

export type AssignableRolesResponse = {
  assignable_roles: AssignableRole[];
  target_user_id: string;
  is_self: boolean;
  restricted_count: number;
  message: string | null;
};

export type RoleAssignmentResponse = {
  message: string;
  user_id: string;
  role: AdminUserRoleRef;
  assigned_by: { id: string; full_name: string };
  assigned_at: string;
};

export type RoleRemovalResponse = { message: string; user_id: string; role_id: string };

export type UserDeactivationImpact = {
  user_id: string;
  user_full_name: string;
  can_deactivate: boolean;
  dependencies: {
    open_follow_ups: number;
    assigned_customers: number;
    active_workforce_link: boolean;
  };
  total_blocking_items: number;
  message: string;
};

export type EffectiveAccessRoleSource = {
  role_id: string; role_code: string; role_name: string;
  scope: "own" | "team" | "organization";
};

export type EffectivePermission = {
  code: string; module: string; resource: string; action: string;
  name: string; description: string;
  effective_scope: "own" | "team" | "organization";
  scopable: boolean; scope_label: string;
  granted_by_roles: EffectiveAccessRoleSource[]; is_root_bypass: boolean;
};

export type EffectiveAccessReport = {
  user_id: string; user_full_name: string; user_email: string;
  is_organization_root: boolean; total_permissions: number; total_roles: number;
  roles: Array<AdminUserRoleRef & { is_system: boolean }>;
  permissions_by_module: Record<string, EffectivePermission[]>;
  missing_permissions_count: number;
  missing_permissions: Array<{ code: string; module: string; name: string }>;
  generated_at: string;
};
