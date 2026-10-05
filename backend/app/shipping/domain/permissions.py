"""Shipping and delivery permissions (SHIP-001, SHIP-004): the single source of every shipping permission code.

The platform catalog registers these, system roles are generated from them, and routes, services and the
frontend refer to these names only. Pure: no imports from other modules.

Who does what:
  shipments:update    prepare the note (edit, ready, reopen) and reschedule a returned one
  shipments:dispatch  the gate: goods leave the factory (with the gate weight)
  shipments:deliver   the delivery outcome: received (in full or in part), or not received and on its way back;
                      and the proof of delivery
  shipments:cancel    cancel before leaving, or close a returned note as not delivered
  returns:create      register a customer's return of delivered goods (against its delivery note)
  returns:approve     accept or reject a customer's return
  returns:receive     the warehouse receives returned goods back at the factory
  returns:cancel      withdraw a customer's return before it is received
"""

MODULE = "shipping"

# resource -> actions, in the order the roles screen shows them.
RESOURCES: dict[str, tuple[str, ...]] = {
    "shipments": ("read", "create", "update", "dispatch", "deliver", "cancel"),
    "returns": ("read", "create", "approve", "receive", "cancel"),
    "settings": ("update",),
}


def code(resource: str, action: str) -> str:
    assert action in RESOURCES[resource], f"{resource}:{action} is not a shipping permission"
    return f"{MODULE}:{resource}:{action}"


ALL: tuple[str, ...] = tuple(code(resource, action) for resource, actions in RESOURCES.items() for action in actions)

(SHIPMENTS_READ, SHIPMENTS_CREATE, SHIPMENTS_UPDATE, SHIPMENTS_DISPATCH, SHIPMENTS_DELIVER,
 SHIPMENTS_CANCEL) = (code("shipments", a) for a in RESOURCES["shipments"])
RETURNS_READ, RETURNS_CREATE, RETURNS_APPROVE, RETURNS_RECEIVE, RETURNS_CANCEL = (code("returns", a) for a in RESOURCES["returns"])
SETTINGS_UPDATE = code("settings", "update")

# action offered on a shipment -> the permission it needs.
SHIPMENT_ACTIONS: dict[str, str] = {
    "edit": SHIPMENTS_UPDATE, "ready": SHIPMENTS_UPDATE, "reopen": SHIPMENTS_UPDATE, "reschedule": SHIPMENTS_UPDATE,
    "dispatch": SHIPMENTS_DISPATCH, "deliver": SHIPMENTS_DELIVER, "fail": SHIPMENTS_DELIVER,
    "cancel": SHIPMENTS_CANCEL, "close": SHIPMENTS_CANCEL, "return": RETURNS_CREATE,
}

# action offered on a return -> the permission it needs.
RETURN_ACTIONS: dict[str, str] = {
    "approve": RETURNS_APPROVE, "reject": RETURNS_APPROVE, "receive": RETURNS_RECEIVE, "cancel": RETURNS_CANCEL,
}

# Labels where "<action> <resource>" reads badly; everything else is composed by the catalog.
LABELS: dict[str, tuple[str, str]] = {
    SHIPMENTS_DISPATCH: ("Dispatch Shipments", "إخراج الشحنات من المصنع"),
    SHIPMENTS_DELIVER: ("Record Shipment Delivery", "تسجيل نتيجة تسليم الشحنات"),
    SHIPMENTS_CANCEL: ("Cancel or Close Shipments", "إلغاء الشحنات أو إغلاقها"),
    RETURNS_READ: ("Read Returns", "عرض المرتجعات"),
    RETURNS_CREATE: ("Register Customer Returns", "تسجيل مرتجعات العملاء"),
    RETURNS_APPROVE: ("Approve or Reject Returns", "اعتماد المرتجعات أو رفضها"),
    RETURNS_RECEIVE: ("Receive Returned Goods", "استلام البضاعة المرتجعة"),
    RETURNS_CANCEL: ("Cancel Returns", "إلغاء المرتجعات"),
    SETTINGS_UPDATE: ("Update Shipping Settings", "تعديل إعدادات الشحن"),
}
