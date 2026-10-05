"""Procurement permissions (PROC-001): the single source of every procurement permission code.

The platform catalog registers these, system roles are generated from them, and routes, services and the frontend
refer to these names only. Pure: no imports from other modules.

  suppliers:approve   put a supplier on the approved list, on probation, or block it
  receipts:receive    record that the material arrived (the goods receipt is final)
"""

MODULE = "procurement"

# resource -> actions, in the order the roles screen shows them.
RESOURCES: dict[str, tuple[str, ...]] = {
    "suppliers": ("read", "create", "update", "approve"),
    "materials": ("read", "create", "update"),
    "receipts": ("read", "create", "update", "receive", "cancel"),
    "settings": ("update",),
}


def code(resource: str, action: str) -> str:
    assert action in RESOURCES[resource], f"{resource}:{action} is not a procurement permission"
    return f"{MODULE}:{resource}:{action}"


ALL: tuple[str, ...] = tuple(code(resource, action) for resource, actions in RESOURCES.items() for action in actions)

SUPPLIERS_READ, SUPPLIERS_CREATE, SUPPLIERS_UPDATE, SUPPLIERS_APPROVE = (code("suppliers", a) for a in RESOURCES["suppliers"])
MATERIALS_READ, MATERIALS_CREATE, MATERIALS_UPDATE = (code("materials", a) for a in RESOURCES["materials"])
RECEIPTS_READ, RECEIPTS_CREATE, RECEIPTS_UPDATE, RECEIPTS_RECEIVE, RECEIPTS_CANCEL = (code("receipts", a) for a in RESOURCES["receipts"])
SETTINGS_UPDATE = code("settings", "update")
READ = (SUPPLIERS_READ, MATERIALS_READ, RECEIPTS_READ)

SUPPLIER_ACTIONS: dict[str, str] = {"edit": SUPPLIERS_UPDATE, "set_status": SUPPLIERS_APPROVE}
RECEIPT_ACTIONS: dict[str, str] = {"edit": RECEIPTS_UPDATE, "receive": RECEIPTS_RECEIVE, "cancel": RECEIPTS_CANCEL}

# Labels where "<action> <resource>" reads badly; everything else is composed by the catalog.
LABELS: dict[str, tuple[str, str]] = {
    SUPPLIERS_APPROVE: ("Approve or Block Suppliers", "اعتماد الموردين أو إيقافهم"),
    RECEIPTS_READ: ("Read Goods Receipts", "عرض استلام المواد"),
    RECEIPTS_CREATE: ("Create Goods Receipts", "إنشاء استلام مواد"),
    RECEIPTS_UPDATE: ("Update Goods Receipts", "تعديل استلام المواد"),
    RECEIPTS_RECEIVE: ("Confirm Goods Receipts", "تأكيد استلام المواد"),
    RECEIPTS_CANCEL: ("Cancel Goods Receipts", "إلغاء استلام المواد"),
    SETTINGS_UPDATE: ("Update Procurement Settings", "تعديل إعدادات المشتريات"),
}
