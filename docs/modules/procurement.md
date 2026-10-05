# Procurement Module

**Status:** PROC-001 — suppliers (approved supplier list), materials, goods receipts.

The procurement module owns who the factory buys from, what it buys, and what arrives. All data is organization-scoped
through `TenantContext` (ADR-001). Purchase orders are not managed yet: a receipt keeps the purchase order number as text.

## Architecture and boundaries

- Layers like the other modules: `domain/` (pure: `permissions.py`, `rules.py`), `infrastructure/models.py`, `application/`
  (`services.py` — single writers `SupplierService`, `MaterialService`, `ReceiptService`; `support.py` — numbering, history,
  reads from other modules), `api/` (`schemas.py`, `routes.py`) and `reporting/` (the goods receipt note).
- Every table is prefixed `procurement_`. The module imports no business module — enforced by
  `tests/procurement/test_procurement.py` and `tests/test_module_boundaries.py`.
- Reads from other modules go through the shared metadata (ADR-004): user names, and quality's non-conformance reports about a
  supplier (`QualityReads`). Quality reads `procurement_suppliers` the same way to let a report name a registered supplier.
- Phone numbers are normalized by the core (`app/core/phones.py`), shared with shipping.
- Composition root (`app/main.py`): the router at `/api/v1/procurement` and the document registration.

## Suppliers (`procurement_suppliers`)

Numbered `SUP-NNNN` (never restarting). Category (raw materials, packaging, consumables, services, other), what it supplies,
contact, phone (international form), email, address, city, country, VAT and commercial registration numbers, notes.

**Standing on the approved supplier list:** `pending` (new, not evaluated) → `approved` · `conditional` (on probation) ·
`blocked`. Anything but approved needs a reason (`REASON_REQUIRED`); who decided and when are kept. A blocked supplier can
deliver nothing: a receipt is neither created nor received from it (`SUPPLIER_BLOCKED`), and it is left out of the lookup.

A supplier's page shows its performance: received receipts and the last one, and the non-conformance reports quality raised
about it (all and still open), with links.

## Materials (`procurement_materials`)

Numbered `MAT-NNNN`. Category (resin, masterbatch, additive, core, carton, film, accessory, other), default unit from the shared
catalogue, **whether each lot is inspected on arrival**, the product key of its quality specification (`spec_product_type`, for
the incoming inspection), in use or not.

## Goods receipts (`procurement_receipts`, `procurement_receipt_lines`)

Numbered `<prefix>YYYY-NNNN` (`GRN-` by default, `procurement_settings.receipt_prefix`), from a registered supplier, with the
supplier's delivery note and invoice numbers, the purchase order reference, vehicle and driver.

```
draft ─receive→ received        draft / received ─cancel(reason)→ cancelled
```

Only a draft is edited (`RECEIPT_NOT_DRAFT`); receiving needs a line (`LINES_REQUIRED`). Each line is a material (its name and
whether it is inspected are copied) or a described item, the supplier's lot, quantity in a unit of the catalogue, packages and
weight. A received line can open a non-conformance report pre-filled with the supplier, the receipt and lot, and the item.

The history of suppliers and receipts is in `procurement_events`.

## Goods receipt note

`procurement.goods_receipt` (not listed): the company's identity, supplier and references, the lots received with the ones to
inspect marked ("not used before quality releases them"), totals, and signature boxes (supplier's driver, warehouse, quality).
"DRAFT" / "CANCELLED" when so. Arabic or English. Nothing is stored.

## Permissions

`procurement/domain/permissions.py` is the single source, mirrored by `frontend/src/lib/procurement-permissions.ts`
(`tests/procurement-permissions.test.mjs` keeps them identical).

| Code | Granted to (system roles) |
|------|---------------------------|
| `procurement:suppliers:read`, `materials:read`, `receipts:read` | admin, procurement, warehouse, quality, factory, viewer (finance: suppliers and receipts) |
| `procurement:suppliers:create`, `update` · `materials:create` | admin, procurement |
| `procurement:suppliers:approve` (approve, probation, block) | admin, procurement, quality |
| `procurement:materials:update` | admin, procurement, quality |
| `procurement:receipts:create`, `update`, `receive`, `cancel` | admin, procurement, warehouse |
| `procurement:settings:update` (receipt prefix) | admin, procurement |

Migration `f6a1b2j7` creates the tables and these grants for existing organizations; its downgrade refuses while suppliers exist.

## API (`/api/v1/procurement`)

| Method | Path | Permission |
|--------|------|------------|
| GET / POST | `/suppliers` (`status`, `category`, `search`) | suppliers:read / suppliers:create |
| GET | `/suppliers/lookup?q=` (not blocked) | suppliers:read or receipts:create/update |
| GET / PATCH | `/suppliers/{id}` | suppliers:read / suppliers:update |
| POST | `/suppliers/{id}/status` (`status`, `reason`) | suppliers:approve |
| GET / POST / PATCH | `/materials[/{id}]` (`category`, `search`, `active_only`) | materials:read (or receipts:create/update) / create / update |
| GET / POST | `/receipts` (`status`, `supplier_id`, dates, `search` incl. lots) | receipts:read / receipts:create |
| GET / PATCH | `/receipts/{id}` | receipts:read / receipts:update (draft) |
| POST | `/receipts/{id}/receive`, `/cancel` (`reason`) | receipts:receive / receipts:cancel |
| GET | `/receipts/{id}/document.pdf?lang=ar|en` | receipts:read |
| GET / PATCH | `/settings` (`receipt_prefix`) | receipts:read / settings:update |

Frontend: `/suppliers`, `/suppliers/{id}`, `/materials`, `/goods-receipts`, `/goods-receipts/{id}` (sidebar section «المشتريات»).

## Next phases

- Incoming inspection (quality): an inspection of each received lot marked for inspection, against its material's specification;
  a rejected lot opens a non-conformance report with the supplier, and the receipt shows each lot's release.
- Supplier evaluation: a score from rejected lots, non-conformances and their cost.
- Purchase orders, when needed.
