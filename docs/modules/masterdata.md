# Master data (MD-001)

The organization's **products** with their specification templates, and its **general settings** (VAT rate, default
currency). Every other module names products through it. Architecture: [ADR-005](../adr/ADR-005-master-data.md).

## Architecture and boundaries

- `app/masterdata`: `domain` (pure rules and permissions), `infrastructure` (tables `masterdata_*`), `application`
  (single writers; `catalog_provider.py` answers core), `api` (`/api/v1/masterdata`).
- Other modules never import it: they call `core/interfaces/product_catalog.py` (`products`, `business_settings`,
  `unknown_product_types`), registered at the composition root. It imports none of them.
- Legacy product types are rewritten by each module's own holder (`core/interfaces/product_types.py`):
  `commercial/application/product_types.py`, `production/…`, `quality/…`, `procurement/…`.

## Products (`masterdata_products`, `masterdata_product_properties`)

- `PRD-NNNN`, a **key** (`pp_strap`: small English letters, digits, `_`; from the English name when left empty; fixed once
  saved: `PRODUCT_KEY_TAKEN`, `PRODUCT_KEY_INVALID`), Arabic and English names, kind (`finished`, `material`), default
  unit (the shared catalogue), notes, active. Never deleted; deactivated.
- **Specification template**, in print order: key (`width_mm`), Arabic and English names, type (`number` with a unit,
  `text`, `choice` with options `{value, label_ar, label_en}`), required. Errors: `PROPERTY_KEY_INVALID`,
  `PROPERTY_KEY_DUPLICATE`, `OPTIONS_REQUIRED`, `OPTIONS_INVALID`, `OPTIONS_ONLY_FOR_CHOICE`, `UNIT_ONLY_FOR_NUMBER`.
- A line stores `{property key: value}` in the template's order (numbers as numbers, a choice by its value).

## Where products are chosen

| Screen | Field | Module (its own check) |
|---|---|---|
| Quotations, commercial orders, samples | product type (+ the template in the quotation's specification) | commercial |
| Production demands | product type (+ the template's fields) | production |
| Quality specifications | product | quality |
| Materials | specification key (materials) | procurement |

- Once the organization has a product, a new value must be an **active product's key** (sales answers a bilingual 400;
  production `product_type_unknown`; quality and procurement `PRODUCT_TYPE_UNKNOWN`). A value the record already stores
  may stay, and a quotation's lines carry into an order or a demand as they are. Before the first product, the field is
  free text, as before.
- Screens show the product's name in their language (`useProductName`); the quotation document prints the name in the
  document's language and the specification by the template: numbers with their unit, choices by their label.

## Legacy product types

`GET /products/legacy` lists every text other modules store that is not a product key, with where and how often
(`{commercial: 2, production: 1}`). `POST /products/legacy/map {value, product_id}` makes every record storing exactly
that text (trailing spaces included) store the product's key, module by module (`LEGACY_VALUE_NOT_FOUND`). «Create a
product from it» opens the product form with the name filled.

## Reference lists (MD-002, `masterdata_list_items`)

Sectors, opportunity sources, countries and cities; a city names its country by key (`PARENT_REQUIRED`). Each item: a key
(from the English name, fixed: `ITEM_KEY_TAKEN`, `ITEM_KEY_INVALID`), Arabic and English names, active, order. «Add the usual
values» (`POST /lists/{list}/standard`) adds a starting set: common sectors, opportunity sources, the region's countries and
the Kingdom's main cities (their country with them); the organization edits or deactivates them afterwards.

| Field | Record (module, its own check) |
|---|---|
| Sector, opportunity source, country, city | customer (commercial: bilingual 400) |
| Country, city | supplier (procurement: `LIST_VALUE_UNKNOWN`) |
| Delivery city | shipment (shipping: `LIST_VALUE_UNKNOWN`; the customer's city may be copied as it is) |

The same rule as products: once a list has an item, a new value must be one of its active items; a stored value may stay.
Screens offer a city of the chosen country (`ListSelect`), and show names (`useListName`); customer reports, the delivery
note and the purchase order print names in their language (`core/interfaces/reference_lists.names`). Legacy texts:
`GET /lists/{list}/legacy`, `POST /lists/{list}/legacy/map {value, item_id}`, through each module's holder
(`commercial|procurement|shipping/application/reference_values.py`).

## General settings (`masterdata_settings`)

VAT rate (0–100, 15 by default) and default currency (`SAR`, `USD`). New quotations and purchase orders start in the
default currency; with VAT they use this rate. A document keeps the rate it was written with; another rate is refused
(sales: bilingual 400; procurement `TAX_RATE_UNKNOWN`).

## Permissions

| Code | Granted to (system roles) |
|---|---|
| `masterdata:products:read`, `masterdata:settings:read` | every business role (admin, factory, commercial, sales, production, quality, warehouse, shipping, maintenance, procurement, safety, finance, viewer) |
| `masterdata:products:create`, `update` | admin, factory, commercial, production, quality managers |
| `masterdata:settings:update` | admin, finance manager |
| `masterdata:lists:read` | every business role |
| `masterdata:lists:update` | admin, factory, commercial, procurement, shipping managers |

## API (`/api/v1/masterdata`)

| Method | Path | Permission |
|---|---|---|
| GET / POST | `/products` (`search`, `kind`, `active_only`) | products:read / products:create |
| GET / PATCH | `/products/{id}` | products:read / products:update |
| GET | `/products/legacy` | products:create or products:update |
| POST | `/products/legacy/map` | products:update |
| GET / PATCH | `/settings` | settings:read / settings:update |
| GET | `/lists?list=` | lists:read |
| POST | `/lists/{list}`, `/lists/{list}/standard` | lists:update |
| PATCH | `/lists/items/{id}` | lists:update |
| GET / POST | `/lists/{list}/legacy`, `/lists/{list}/legacy/map` | lists:update |

Frontend: `/master-data/products`, `/master-data/products/new`, `/master-data/products/{id}`, `/master-data/lists`, `/master-data/settings`
(sidebar section «البيانات الأساسية»).

Migrations `f6a1b2k3` (products, settings) and `f6a1b2k4` (reference lists) create the tables and the grants for existing organizations (recorded, so the downgrade removes
exactly them; it refuses while products exist).
