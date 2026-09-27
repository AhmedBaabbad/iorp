export type AccessScope = "own" | "team" | "organization";

export type AdminPermission = {
  id?: string;
  code: string;
  name: string;
  module_name?: string;
  action_name?: string;
  scope: AccessScope;
  scopable: boolean;
};

export type AdminPermissionGroup = {
  module: string;
  module_name?: string;
  permissions: AdminPermission[];
};

export type AdminRoleListItem = {
  id: string;
  name: string;
  code: string;
  description: string | null;
  is_system: boolean;
  is_protected: boolean;
  is_editable: boolean;
  permission_count: number;
  user_count: number;
  permissions_count: number;
  users_count: number;
  created_at: string;
};

export type AdminRoleDetail = {
  id: string;
  organization_id: string;
  name: string;
  code: string;
  description: string | null;
  is_system: boolean;
  is_protected: boolean;
  is_editable: boolean;
  permission_count: number;
  user_count: number;
  permissions: AdminPermissionGroup[];
  created_at: string;
  updated_at: string;
};

export type AdminRoleCreateRequest = {
  name: string;
  code: string;
  description?: string | null;
};

export type AdminRoleUpdateRequest = {
  name?: string;
  code?: string;
  description?: string | null;
};

export type AdminRolePermissionAssignRequest = {
  permission_code: string;
  scope?: AccessScope;
};
