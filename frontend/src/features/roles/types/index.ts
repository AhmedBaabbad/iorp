export type Permission = {
  id: string;
  code: string;
  name: string;
  module_name: string;
  action_name: string;
};

export type PermissionGroup = {
  module_name: string;
  permissions: Permission[];
};

export type RoleListItem = {
  id: string;
  name: string;
  code: string;
  description: string | null;
  permission_count: number;
  user_count: number;
  created_at: string;
};

export type RoleDetail = {
  id: string;
  organization_id: string;
  name: string;
  code: string;
  description: string | null;
  permissions: Permission[];
  created_at: string;
  updated_at: string;
};

export type RoleCreateRequest = {
  name: string;
  code: string;
  description?: string | null;
};

export type RoleUpdateRequest = {
  name?: string;
  description?: string | null;
};

export type RolePermissionAssignRequest = {
  permission_id: string;
};
