# ADR-005 — Master data is a module of its own, reached through core

Status: accepted (MD-001)

## Context

«نوع المنتج» (product type) was free text in six tables across four modules: samples, quotation lines and commercial
order lines (commercial); production demand lines and production orders (production); product specifications
(quality); and a purchased material's specification key (procurement). It is not only a label: quality picks the
specification in force for a production order by its product type, and production compares product types before it
combines orders. The same product was stored as `PP Strap`, `pp_strap` and `اشرطة تربيط ` (with a trailing space), so an
order could silently find no quality specification. Specification property names (`width_mm` or `width`, `color` or
`colour`) had the same problem, and the VAT rate (15 %) was a constant in two modules.

## Decision

1. A new module, `app/masterdata` (tables `masterdata_*`), owns the organization's **products** — a fixed key, Arabic
   and English names, a kind (finished product or material), a default unit and a **specification template** (ordered
   properties: number with unit, text, or a choice with bilingual options) — and the **general settings** (VAT rate,
   default currency).
2. It imports no business module and none imports it (ADR-004). Modules ask through
   `core/interfaces/product_catalog.py` (`ProductCatalog`): which keys are products, their names and templates, the VAT rate
   and currency. Master data implements the protocol and the composition root (`main.py`) registers it. Foundation reads
   only its permission codes, like every module's.
3. Records keep storing the product's **key** in their own `product_type` column: no schema change in the other modules,
   and every existing match (quality specification ↔ production order) keeps working. The key never changes and a
   product is never deleted (it is deactivated), so a stored key always resolves.
4. **Choosing from the list** is enforced by each module in its own write path, once the organization has defined its
   first product (before that nothing is enforced, so no organization is blocked). A value a record already stores may
   stay on it (a legacy text, a product since deactivated, the lines a quotation carries into an order or a demand).
5. **Legacy values** are mapped to products from the master data screen. Master data never writes another module's
   tables: each module registers a holder (`core/interfaces/product_types.py`) that reads and rewrites its own records;
   master data calls them in one transaction.
6. A document keeps its VAT rate; a new or edited one may use the organization's rate or none.

7. **Reference lists** (MD-002) follow the same rules: sectors, opportunity sources, countries and cities live in master
   data (`masterdata_list_items`); customers, suppliers and shipments store an item's key in their own columns and ask
   through `core/interfaces/reference_lists.py`; each module registers a holder for its legacy texts.

## Consequences

- One source for product names (bilingual on documents), templates (specification fields become inputs and choices) and
  the VAT rate.
- Every module stays the single writer of its tables; dependencies point to `core` only.
- Names on documents follow the current product name (documents are generated on demand, never stored).
- `tests/test_module_boundaries.py::test_b11…` and `tests/masterdata/` enforce the boundaries.
