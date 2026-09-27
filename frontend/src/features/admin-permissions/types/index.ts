export type AdminPermission = {
  id: string;
  code: string;
  module: string;
  resource: string;
  action: string;
  name: string;
  description: string;
  name_en: string;
  name_ar: string;
  description_en: string;
  description_ar: string;
  scopable: boolean;
  owner_field: string | null;
};

export type AdminPermissionGroup = {
  module: string;
  module_name_en: string;
  module_name_ar: string;
  permissions: AdminPermission[];
};

export type AdminPermissionCatalog = {
  total: number;
  modules: AdminPermissionGroup[];
};
