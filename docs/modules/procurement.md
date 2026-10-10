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

## Lot release and supplier evaluation (PROC-002)

Quality inspects each received lot marked for inspection (see quality.md, *Incoming inspection*); procurement only **reads**
`quality_checks` (by `receipt_line_id`) and `quality_non_conformance_reports` (by `supplier_id`) through `support.QualityReads`.

- **Lot status** (`rules.lot_status`), on each line of a received receipt (`line_quality`, with its inspection) and as
  `lots_pending` in the list: `not_required`, `awaiting` (no inspection yet), `inspecting`, `released` (all accepted),
  `partly_released`, `rejected` (nothing accepted).
- **Evaluation** (`rules.evaluate`, `GET /suppliers/{id}/evaluation?months=12`, also on every supplier view), over the closed
  inspections of its lots and its NCRs that are not cancelled in the period:

  ```
  score = 100 × lots released in full / lots inspected
        − min(30, 10 × critical + 5 × major + 2 × minor NCRs)
        − min(20, 1 point per 1,000 of the NCRs' cost)          (never below 0)
  A ≥ 90, B ≥ 75 → approved · C ≥ 60 → conditional · D → blocked
  ```

  Without inspected lots there is no score. The grade only **suggests** a standing; changing it stays with `suppliers:approve`.

## Purchase orders (PROC-003)

Numbered `<prefix>YYYY-NNNN` (`PO-` by default, `procurement_settings.po_prefix`), to a registered supplier that is not blocked
(`domain/purchase_orders.py`, single writer `application/purchase_order_service.py`, routes `api/routes_purchase_orders.py`).

```
draft ─approve→ approved ─send→ sent ─(goods receipts)→ partially_received → received
approved · sent · partially_received ─close(reason)→ closed       draft · approved · sent ─cancel(reason)→ cancelled
```

- **Header:** order date, required date, the supplier's contact (its contact person by default) and quotation number, subject,
  payment terms (advance, on delivery, net 15–90 days, letter of credit, other) with details, delivery terms (Incoterms 2020,
  for imports) and place, notes.
- **Currency and VAT:** Saudi riyals (`SAR`) or US dollars (`USD`); VAT is the organization's rate (master data, 15 % by
  default) or not applied; an order keeps the rate it was written with (`TAX_RATE_UNKNOWN` otherwise). A new order starts in
  the organization's default currency. The screen
  ticks VAT for riyals and clears it for dollars (an import: customs VAT is settled on import); the choice stays the user's.
- **Lines:** a material (its name, editable) or a described item or service, specification notes, quantity in a unit of the
  catalogue, unit price up to four decimals.
- **Amounts are computed by the server** on every save: line = quantity × price; subtotal − discount = taxable; VAT = taxable ×
  rate; total = taxable + VAT, each rounded half-up to 0.01. A discount above the subtotal is refused (`DISCOUNT_INVALID`).
- Only a draft is edited (`ORDER_NOT_DRAFT`). Approving needs a line, a total above zero and a supplier that is not blocked.
- **Receiving against the order:** a goods receipt may name the order (same supplier, `ORDER_OF_ANOTHER_SUPPLIER`; approved,
  sent or partly received, `ORDER_NOT_OPEN_FOR_RECEIPT`) and each of its lines the order line it delivers, in that line's unit
  (`ORDER_LINE_NOT_IN_ORDER`, `ORDER_LINE_UNIT_MISMATCH`). «Receive goods» on the order opens a receipt filled with what each
  line still expects. Confirming or cancelling such a receipt moves the order to partially received or received by itself.
- An order with goods received (or a draft receipt) is not cancelled (`ORDER_HAS_RECEIPTS`): it is closed with the reason.
- **General terms** (`procurement_settings.po_terms_ar|en`, one per line) are printed on every order in its language.

## Purchase order document

`procurement.purchase_order` (not listed): the company's identity; number, date, required date and currency; the supplier
(code, VAT and CR numbers, address, contact) and the delivery and payment; the items and prices; totals with «VAT (15%)» and
«Total including VAT», or «Total» with a note that the prices exclude VAT; notes; the general terms; boxes for whoever prepared
and approved it and for the supplier's acceptance (name, signature, stamp, date). Amounts in riyals carry the Saudi riyal sign
(drawn in SVG from the OFL-1.1 `saudi-riyal-font` path, so no font is needed); dollars carry `$`. «Draft — not approved» /
«Cancelled» when so. Arabic or English. Nothing is stored.

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
| `procurement:settings:update` (number prefixes, purchase order terms) | admin, procurement |
| `procurement:purchase_orders:read` | admin, procurement, warehouse, quality, factory, finance, viewer |
| `procurement:purchase_orders:create`, `update` (edit a draft, mark as sent) | admin, procurement |
| `procurement:purchase_orders:approve` (approve, close) · `cancel` | admin, procurement |

Migration `f6a1b2j7` creates the tables and these grants for existing organizations; its downgrade refuses while suppliers exist.
Migration `f6a1b2k1` adds the purchase orders, the receipt references and their permissions; its downgrade refuses while orders exist.

## API (`/api/v1/procurement`)

| Method | Path | Permission |
|--------|------|------------|
| GET / POST | `/suppliers` (`status`, `category`, `search`) | suppliers:read / suppliers:create |
| GET | `/suppliers/{id}/evaluation?months=` | suppliers:read |
| GET | `/suppliers/lookup?q=` (not blocked) | suppliers:read or receipts:create/update |
| GET / PATCH | `/suppliers/{id}` | suppliers:read / suppliers:update |
| POST | `/suppliers/{id}/status` (`status`, `reason`) | suppliers:approve |
| GET / POST / PATCH | `/materials[/{id}]` (`category`, `search`, `active_only`) | materials:read (or receipts:create/update) / create / update |
| GET / POST | `/receipts` (`status`, `supplier_id`, dates, `search` incl. lots) | receipts:read / receipts:create |
| GET / PATCH | `/receipts/{id}` | receipts:read / receipts:update (draft) |
| POST | `/receipts/{id}/receive`, `/cancel` (`reason`) | receipts:receive / receipts:cancel |
| GET | `/receipts/{id}/document.pdf?lang=ar|en` | receipts:read |
| GET / PATCH | `/settings` (`receipt_prefix`, `po_prefix`, `po_terms_ar`, `po_terms_en`) | receipts:read / settings:update |
| GET / POST | `/purchase-orders` (`status`, `supplier_id`, `open_only`, dates, `search` incl. items) | purchase_orders:read / create |
| GET | `/purchase-orders/open-for-receipt?supplier_id=` (what each line still expects) | receipts:create or receipts:update |
| GET / PATCH | `/purchase-orders/{id}` | purchase_orders:read / update (draft) |
| POST | `/purchase-orders/{id}/approve`, `/close` (`reason`) | purchase_orders:approve |
| POST | `/purchase-orders/{id}/send` · `/cancel` (`reason`) | purchase_orders:update · purchase_orders:cancel |
| GET | `/purchase-orders/{id}/document.pdf?lang=ar|en` | purchase_orders:read |

Receipts take `purchase_order_id` and, per line, `po_line_id`; they show the order's number (`po_number`).

Frontend: `/suppliers`, `/suppliers/{id}`, `/materials`, `/purchase-orders`, `/purchase-orders/{id}`, `/goods-receipts`,
`/goods-receipts/{id}` (sidebar section «المشتريات»).
