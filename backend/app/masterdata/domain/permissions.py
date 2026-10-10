"""Master data permissions (MD-001): the single source of every master data permission code.

The platform catalog registers these, system roles are generated from them, and routes and the frontend refer to these
names only. Pure: no imports from other modules.

  products:read     choose a product (every screen that names one) and see the catalogue
  products:create   add a product, and turn a legacy product type into one
  products:update   rename, deactivate, change its specification template
  products:map_legacy  rewrite a legacy product type, wherever other modules store it, to a product's key
  settings:read     the organization's VAT rate and default currency (used by quotations and purchase orders)
  settings:update   change them
  lists:read        choose a sector, opportunity source, country or city (customers, suppliers, shipments)
  lists:update      add and edit their items
  lists:map_legacy  rewrite a legacy text, wherever other modules store it, to an item's key
"""

MODULE = "masterdata"

# resource -> actions, in the order the roles screen shows them.
RESOURCES: dict[str, tuple[str, ...]] = {
    "products": ("read", "create", "update", "map_legacy"),
    "settings": ("read", "update"),
    # MD-002: sectors, opportunity sources, countries and cities.
    "lists": ("read", "update", "map_legacy"),
}


def code(resource: str, action: str) -> str:
    assert action in RESOURCES[resource], f"{resource}:{action} is not a master data permission"
    return f"{MODULE}:{resource}:{action}"


ALL: tuple[str, ...] = tuple(code(resource, action) for resource, actions in RESOURCES.items() for action in actions)

PRODUCTS_READ, PRODUCTS_CREATE, PRODUCTS_UPDATE, PRODUCTS_MAP_LEGACY = (code("products", a) for a in RESOURCES["products"])
SETTINGS_READ, SETTINGS_UPDATE = (code("settings", a) for a in RESOURCES["settings"])
LISTS_READ, LISTS_UPDATE, LISTS_MAP_LEGACY = (code("lists", a) for a in RESOURCES["lists"])
READ = (PRODUCTS_READ, SETTINGS_READ, LISTS_READ)

PRODUCT_ACTIONS: dict[str, str] = {"edit": PRODUCTS_UPDATE}

# Labels where "<action> <resource>" reads badly; everything else is composed by the catalog.
LABELS: dict[str, tuple[str, str]] = {
    PRODUCTS_READ: ("Read Products", "عرض المنتجات"),
    PRODUCTS_CREATE: ("Add Products", "إضافة المنتجات"),
    PRODUCTS_UPDATE: ("Update Products and Their Specification Templates", "تعديل المنتجات وقوالب مواصفاتها"),
    SETTINGS_READ: ("Read General Settings (VAT, currency)", "عرض الإعدادات العامة (الضريبة والعملة)"),
    SETTINGS_UPDATE: ("Update General Settings (VAT, currency)", "تعديل الإعدادات العامة (الضريبة والعملة)"),
    LISTS_READ: ("Read Reference Lists (sectors, sources, countries, cities)", "عرض القوائم المرجعية (القطاعات والمصادر والدول والمدن)"),
    LISTS_UPDATE: ("Manage Reference Lists", "إدارة القوائم المرجعية"),
}
