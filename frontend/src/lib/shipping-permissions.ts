// Shipping permission codes (SHIP-001, SHIP-004), mirroring backend/app/shipping/domain/permissions.py.
// Screens refer to these names only; tests/shipping-permissions.test.mjs keeps both lists identical.
// The server enforces every permission; the screens use them only to hide what a user cannot do.

const code = <R extends string, A extends string>(resource: R, action: A) => `shipping:${resource}:${action}` as const;

export const S = {
  SHIPMENTS_READ: code("shipments", "read"),
  SHIPMENTS_CREATE: code("shipments", "create"),
  SHIPMENTS_UPDATE: code("shipments", "update"),
  SHIPMENTS_DISPATCH: code("shipments", "dispatch"),
  SHIPMENTS_DELIVER: code("shipments", "deliver"),
  SHIPMENTS_CANCEL: code("shipments", "cancel"),
  RETURNS_READ: code("returns", "read"),
  RETURNS_CREATE: code("returns", "create"),
  RETURNS_APPROVE: code("returns", "approve"),
  RETURNS_RECEIVE: code("returns", "receive"),
  RETURNS_CANCEL: code("returns", "cancel"),
  SETTINGS_UPDATE: code("settings", "update"),
} as const;
