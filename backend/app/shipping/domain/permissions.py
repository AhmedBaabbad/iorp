"""Shipping and delivery permissions (SHIP-001, SHIP-004): the single source of every shipping permission code.

The platform catalog registers these, system roles are generated from them, and routes, services and the
frontend refer to these names only. Pure: no imports from other modules.

Who does what:
  shipments:update    edit the note; ready, reopen and reschedule have separate permissions
  shipments:dispatch  the gate: goods leave the factory (with the gate weight)
  shipments:deliver   the delivery outcome: received (in full or in part), or not received and on its way back;
                      and the proof of delivery
  shipments:fail      record that the customer did not receive the goods (they come back)
  shipments:cancel    cancel a shipment before it leaves
  shipments:close     close a note whose goods came back, as not delivered
  returns:create      register a customer's return of delivered goods (against its delivery note)
  returns:approve     accept a customer's return
  returns:reject      refuse a customer's return (with the reason)
  returns:receive     the warehouse receives returned goods back at the factory
  returns:cancel      withdraw a customer's return before it is received
"""

MODULE = "shipping"

# resource -> actions, in the order the roles screen shows them.
RESOURCES: dict[str, tuple[str, ...]] = {
    "directory": ("read", "write"),
    "shipments": ("read", "create", "update", "dispatch", "deliver", "cancel", "ready", "reopen", "reschedule", "fail", "close"),
    "returns": ("read", "create", "approve", "receive", "cancel", "reject"),
    "settings": ("update",),
}


def code(resource: str, action: str) -> str:
    assert action in RESOURCES[resource], f"{resource}:{action} is not a shipping permission"
    return f"{MODULE}:{resource}:{action}"


ALL: tuple[str, ...] = tuple(code(resource, action) for resource, actions in RESOURCES.items() for action in actions)

(SHIPMENTS_READ, SHIPMENTS_CREATE, SHIPMENTS_UPDATE, SHIPMENTS_DISPATCH, SHIPMENTS_DELIVER,
 SHIPMENTS_CANCEL, SHIPMENTS_READY, SHIPMENTS_REOPEN, SHIPMENTS_RESCHEDULE, SHIPMENTS_FAIL,
 SHIPMENTS_CLOSE) = (code("shipments", a) for a in RESOURCES["shipments"])
RETURNS_READ, RETURNS_CREATE, RETURNS_APPROVE, RETURNS_RECEIVE, RETURNS_CANCEL, RETURNS_REJECT = (code("returns", a) for a in RESOURCES["returns"])
SETTINGS_UPDATE = code("settings", "update")

# action offered on a shipment -> the permission it needs.
SHIPMENT_ACTIONS: dict[str, str] = {
    "edit": SHIPMENTS_UPDATE, "ready": SHIPMENTS_READY, "reopen": SHIPMENTS_REOPEN, "reschedule": SHIPMENTS_RESCHEDULE,
    "dispatch": SHIPMENTS_DISPATCH, "deliver": SHIPMENTS_DELIVER, "fail": SHIPMENTS_FAIL,
    "cancel": SHIPMENTS_CANCEL, "close": SHIPMENTS_CLOSE, "return": RETURNS_CREATE,
}

# action offered on a return -> the permission it needs.
RETURN_ACTIONS: dict[str, str] = {
    "approve": RETURNS_APPROVE, "reject": RETURNS_REJECT, "receive": RETURNS_RECEIVE, "cancel": RETURNS_CANCEL,
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
