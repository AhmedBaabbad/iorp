// Master data permission codes (MD-001), mirroring backend/app/masterdata/domain/permissions.py.
// Screens refer to these names only; tests/masterdata-permissions.test.mjs keeps both lists identical.
// The server enforces every permission; the screens use them only to hide what a user cannot do.

const code = <R extends string, A extends string>(resource: R, action: A) => `masterdata:${resource}:${action}` as const;

export const MD = {
  PRODUCTS_READ: code("products", "read"),
  PRODUCTS_CREATE: code("products", "create"),
  PRODUCTS_UPDATE: code("products", "update"),
  PRODUCTS_MAP_LEGACY: code("products", "map_legacy"),
  SETTINGS_READ: code("settings", "read"),
  SETTINGS_UPDATE: code("settings", "update"),
  LISTS_READ: code("lists", "read"),
  LISTS_UPDATE: code("lists", "update"),
  LISTS_MAP_LEGACY: code("lists", "map_legacy"),
} as const;
