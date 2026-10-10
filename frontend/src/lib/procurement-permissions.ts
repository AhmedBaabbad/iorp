// Procurement permission codes (PROC-001), mirroring backend/app/procurement/domain/permissions.py.
// Screens refer to these names only; tests/procurement-permissions.test.mjs keeps both lists identical.
// The server enforces every permission; the screens use them only to hide what a user cannot do.

const code = <R extends string, A extends string>(resource: R, action: A) => `procurement:${resource}:${action}` as const;

export const PR = {
  SUPPLIERS_READ: code("suppliers", "read"),
  SUPPLIERS_CREATE: code("suppliers", "create"),
  SUPPLIERS_UPDATE: code("suppliers", "update"),
  SUPPLIERS_APPROVE: code("suppliers", "approve"),
  MATERIALS_READ: code("materials", "read"),
  MATERIALS_CREATE: code("materials", "create"),
  MATERIALS_UPDATE: code("materials", "update"),
  RECEIPTS_READ: code("receipts", "read"),
  RECEIPTS_CREATE: code("receipts", "create"),
  RECEIPTS_UPDATE: code("receipts", "update"),
  RECEIPTS_RECEIVE: code("receipts", "receive"),
  RECEIPTS_CANCEL: code("receipts", "cancel"),
  SETTINGS_UPDATE: code("settings", "update"),
  PO_READ: code("purchase_orders", "read"),
  PO_CREATE: code("purchase_orders", "create"),
  PO_UPDATE: code("purchase_orders", "update"),
  PO_APPROVE: code("purchase_orders", "approve"),
  PO_CANCEL: code("purchase_orders", "cancel"),
  PO_SEND: code("purchase_orders", "send"),
  PO_CLOSE: code("purchase_orders", "close"),
} as const;
