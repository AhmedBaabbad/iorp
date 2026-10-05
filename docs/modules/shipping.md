# Shipping Module

**Status:** SHIP-001 — shipments and delivery notes; SHIP-003 — simple lines; SHIP-004 — delivery outcomes and returns.

The shipping module owns delivery notes: who a shipment is for, how it leaves the factory, what it carries, and its
lifecycle from preparation to receipt. All data is organization-scoped through `TenantContext` (ADR-001).

## Architecture and boundaries

- Layers like the other modules: `domain/` (pure: `permissions.py`, `rules.py` for shipments, `returns.py` for returns),
  `infrastructure/models.py`, `application/` (single writers `shipment_service.py`, `return_service.py` and
  `attachment_service.py`; cross-module reads in `support.py`), `api/` (`routes_shipments.py`, `routes_returns.py`) and
  `reporting/` (the delivery note and the return note).
- Every table is prefixed `shipping_`. Other modules are referenced by plain UUIDs (`customer_id`), never by foreign keys
  into their tables or imports of their models (ADR-004). Customers and user names are read through the shared metadata
  (`Base.metadata.tables`); a customer's name and contacts are **copied** onto the shipment, so a delivery note keeps what
  it printed. Production orders are read the same way (`production_orders`) and their number is copied onto the line.
- The module imports no business module (commercial, production, quality, foundation, workforce, platform) — enforced by
  `tests/shipping/test_shipments.py` and `tests/test_module_boundaries.py`.
- Activity logging goes through the core interface (`get_registered_activity_logger`).
- Uploaded files are saved by the core storage (`app/core/storage.py`, `save_attachment`): images and PDFs recognised by
  their content, 10 MB at most, under the organization's folder. Generated documents are never stored.
- Composition root (`app/main.py`): the two routers at `/api/v1/shipping` and the two document registrations.

## Shipment (`shipping_shipments`)

| Group | Fields |
|-------|--------|
| Identity | `shipment_no` (`<prefix>YYYY-NNNN`, locked counter per year), `status`, `delivery_method`, `shipment_date` |
| Customer | `customer_id` (registered, optional), `customer_name` (always required, copied), `customer_reference` (PO) |
| Recipient | `consignee_name`, `consignee_phone` (international form), `consignee_email`, `notify_consignee`, address, city, location link |
| Transport | `driver_name`, `driver_phone`, `driver_id_no`, `vehicle_plate`, `vehicle_type` — or `carrier_name`, `tracking_no` |
| Lifecycle | `attempt`, `ready_at`, `dispatched_at/by`, `delivered_at`, `received_by_name`, `delivery_notes`, `failed_at`, `cancel_reason`, `close_reason` |
| Weights | `gate_weight_kg` (factory weighbridge, at dispatch), `received_weight_kg` (customer's, at delivery) |

**Customer:** a registered customer (its name, phone, email and city fill the recipient's empty fields), or an unregistered
one named by hand. A customer is always named (`CUSTOMER_REQUIRED`).

**Phones** are stored as `+<country><number>`: a Saudi local number (`05…`, `011…`) gets `+966`, Arabic digits are accepted,
anything else is refused (`PHONE_INVALID`). A malformed phone stored on a customer is simply not copied.

**Delivery methods** (`domain/rules.py`):

| Method | Needed before "ready" | Lifecycle |
|--------|----------------------|-----------|
| `factory_delivery` | driver name, vehicle plate | ready → dispatched → delivered |
| `carrier` | carrier name | ready → dispatched → delivered |
| `pickup` | collector name, vehicle plate | ready → delivered (collected at the factory) |

```
draft ─ready→ ready ─dispatch→ dispatched ─deliver(received by)→ delivered
                                           ─deliver(part refused)→ partially_delivered   + delivery return
                                           ─fail(reason)→ returned                        + delivery return (whole load)
                                 returned ─reschedule→ ready  (same number, attempt + 1, transport may change)
                                 returned ─close(reason)→ not_delivered
              ready ─reopen→ draft                   (first attempt only)
              ready ─deliver→ delivered              (pickup)
draft / ready ─cancel(reason)→ cancelled             (first attempt only)
```

Only a draft is edited. Once the goods have left, the note's lines are frozen: a dispatched note cannot be cancelled
(`SHIPMENT_ALREADY_LEFT`); after a failed attempt it is rescheduled under the **same number** or closed as not delivered
(`SHIPMENT_LEFT_BEFORE` for reopen and cancel). A returned note is rescheduled or closed only once its goods are back at the
factory (`RETURN_NOT_RECEIVED`). A pickup is never received in part (`PARTIAL_NOT_FOR_PICKUP`). Delivered, partially
delivered, not delivered and cancelled are final.

**Weights:** the received weight is checked against the gate weight (else the lines' total) with the organization's
tolerance (`weight_check`: reference, received, difference in kg and %, within tolerance or not).

## Lines (`shipping_shipment_lines`)

Kept simple on purpose (SHIP-003). Each line has:
- **Description** — free text.
- **Width** and **thickness** in millimetres (`width_mm`, `thickness_mm`, optional, >= 0).
- **Quantity** (> 0) and its **unit** — a code from the shared units catalogue (`app/core/units.py`, mirrored by
  `src/lib/units.ts`, labelled in `common.units`): count, packaging, weight, length, area/volume and time. Anything else is
  refused (422). Documents print the label in their language.
- **One full weight** (`weight`) with its own unit — gram, kilogram, ton, pound or ounce (`weight_unit`, default kg).
  There is no net/gross split, no packages, specification or per-line notes. No prices: a delivery note is not an invoice.
- **Production order** (optional, SHIP-004): `production_order_id` from the lookup (not drafts or cancelled orders), its number
  copied to `production_order_no` and printed under the description — the batch a complaint is traced back to.
- **Delivered quantity** (`delivered_quantity`): what the customer accepted, set at delivery.

Totals: quantities per unit (rolls and kilograms are never added together) and the total weight converted to kilograms.
Migration `f6a1b2j2` moved lines onto the units catalogue; `f6a1b2j3` moved them to this form (width/thickness taken from the
old specification when numeric, weight from the gross weight, else the net weight) and dropped the other columns.

The units catalogue moved from the commercial module to the core so every module shares it; `app/commercial/domain/units.py`
re-exports it, and the quotation document uses the shared `spec_text`.

## Returns (`shipping_returns`, `shipping_return_lines`)

Goods that come back after leaving, numbered on their own (`<return prefix>YYYY-NNNN`, `RT-` by default, counter
`shipping_return_counters`) and **always against their delivery note**, which never changes. `domain/returns.py`:

| Kind | When | Lifecycle |
|------|------|-----------|
| `delivery` | not received at the door: the whole load on a failed delivery, or the refused part of a partial one | approved → received |
| `customer` | the customer received the goods and later sends (some of) them back | requested → approved → received; requested → rejected; requested / approved → cancelled |

- Lines are chosen from the note's lines (description, sizes, units and production order copied); a customer may return at
  most what was delivered less what earlier returns took back (received quantity once received, requested before; rejected
  and cancelled returns take nothing) — `RETURN_QUANTITY_INVALID` with `available`.
- Receipt records what actually arrived per line (quantity and weight); the weight is in proportion when not given.
- **Reasons and responsibility:** each reason names who is responsible — factory (quality issue/defect, not to
  specification, wrong item, wrong address), customer (refused, site closed, nobody to receive, excess quantity, cancelled)
  or undetermined (other, which needs details). Transit damage falls on whoever carried the goods: the carrier (then a
  `carrier_claim_ref` may be kept), the factory for its own truck, the customer for a pickup.
- **Return window** (`return_window_days`, 30 by default): a customer return registered later is `is_late`; approving it
  needs a note (`LATE_RETURN_NEEDS_NOTE`).
- The decision on returned goods (back to stock, rework, scrap «هالك») belongs to quality and comes later; the
  `return.received` event is its hook.

## Attachments (`shipping_attachments`)

Files kept with a note (`proof_of_delivery`: the signed delivery note, or `document`) once its goods have left, and with a
return (`photo`, `document`) unless it is rejected or cancelled. At most 20 per owner.

## Events and notifications (`shipping_shipment_events`)

Every step writes an event (`shipment.created`, `.ready`, `.reopened`, `.dispatched`, `.delivered`,
`.partially_delivered`, `.returned`, `.rescheduled`, `.closed`, `.cancelled`; for returns `return.opened`, `.requested`,
`.approved`, `.rejected`, `.received`, `.cancelled` with `return_id`) with the actor, the reason and a payload carrying
what a message needs (number, status, attempt, method, customer, recipient contacts, `notify`, and the return's number,
kind, reason and responsibility). A note's history includes its returns'. The events are the shipment's history and the **outbox** a future workflow-automation step will read
(`processed_at` stays empty). This module sends nothing.

## Delivery note document

`shipping.delivery_note` (not listed in the report center), rendered by the reporting core with the company's external
identity: number, date and method; customer and recipient; transport; items with width, thickness, quantity and weight and the
totals; the production order under each description; on a partial delivery what was received of each line; the attempt
when above 1; its returns' numbers; notes; the receipt statement and three signature boxes (warehouse, driver or carrier,
recipient). Drafts carry "DRAFT", cancelled notes "CANCELLED", closed ones "NOT DELIVERED", with the reason. Arabic by
default, English on request. Nothing is stored.

## Return note document

`shipping.return_note` (not listed), same identity and layout: return number, date and kind; customer, delivery note,
delivery date and customer reference; reason, responsibility, status (and the carrier claim, the late flag); the items
returned and received with width, thickness, unit, weight and production order; details, decision and receipt notes;
signature boxes (registered by, approved by, received by the warehouse). Rejected and cancelled returns are marked.

## Permissions

`shipping/domain/permissions.py` is the single source, mirrored by `frontend/src/lib/shipping-permissions.ts`
(`tests/shipping-permissions.test.mjs` keeps them identical). Every route declares one.

| Code | Meaning | Granted to (system roles) |
|------|---------|---------------------------|
| `shipping:shipments:read` | see notes | admin, shipping, warehouse, factory, commercial, sales rep, quality, finance, viewer |
| `shipping:shipments:create`, `update` | prepare a note; ready, reopen, reschedule | admin, shipping, warehouse |
| `shipping:shipments:dispatch` | the gate: goods leave (gate weight) | admin, shipping, warehouse |
| `shipping:shipments:deliver` | delivery outcome: received in full or part, not received; proof of delivery | admin, shipping |
| `shipping:shipments:cancel` | cancel before leaving; close as not delivered | admin, shipping |
| `shipping:returns:read` | see returns | admin, shipping, warehouse, factory, commercial, sales rep, quality, finance, viewer |
| `shipping:returns:create` | register a customer return | admin, shipping, commercial, sales rep |
| `shipping:returns:approve` | approve or reject a customer return | admin, shipping, commercial, factory |
| `shipping:returns:receive` | receive returned goods at the factory | admin, shipping, warehouse |
| `shipping:returns:cancel` | withdraw a customer return before receipt | admin, shipping, commercial |
| `shipping:settings:update` | prefixes, return window, weight tolerance | admin, shipping |

Migration `f6a1b2j1` creates the tables and the shipment grants; `f6a1b2j4` adds the returns, the new columns and
statuses, and the return grants (recorded, so its downgrade removes exactly them; it refuses while returns, returned notes
or attachments exist).

## API (`/api/v1/shipping`)

| Method | Path | Permission |
|--------|------|------------|
| GET | `/shipments` (`status`, `method`, `customer_id`, `date_from`, `date_to`, `search`) | shipments:read |
| GET | `/shipments/lookups/customers?q=` | shipments:create or update |
| POST | `/shipments` | shipments:create |
| GET / PATCH | `/shipments/{id}` | shipments:read / shipments:update (draft) |
| POST | `/shipments/{id}/ready`, `/reopen` | shipments:update |
| GET | `/shipments/lookups/production-orders?q=` | shipments:create or update |
| POST | `/shipments/{id}/dispatch` (`gate_weight`, `gate_weight_unit`) | shipments:dispatch |
| POST | `/shipments/{id}/deliver` (`received_by_name`, `delivery_notes`, `lines[{line_id, delivered_quantity}]`, `refusal_reason`, `refusal_details`, `received_weight`, `received_weight_unit`) | shipments:deliver |
| POST | `/shipments/{id}/fail` (`reason`, `details`) | shipments:deliver |
| POST | `/shipments/{id}/reschedule` (transport and date, optional) | shipments:update |
| POST | `/shipments/{id}/close`, `/cancel` (`reason`) | shipments:cancel |
| GET | `/shipments/{id}/document.pdf?lang=ar|en` | shipments:read |
| POST / GET / DELETE | `/shipments/{id}/attachments[/{attachment_id}]` (multipart `file`, `kind`) | shipments:deliver / read / deliver |
| GET / POST | `/returns` (`status`, `kind`, `shipment_id`, `customer_id`, dates, `search`) | returns:read / returns:create |
| GET | `/returns/{id}`, `/returns/{id}/document.pdf?lang=` | returns:read |
| POST | `/returns/{id}/approve` (`note`), `/reject` (`reason`) | returns:approve |
| POST | `/returns/{id}/receive` (`lines[{return_line_id, received_quantity, received_weight}]`, `notes`) | returns:receive |
| POST | `/returns/{id}/cancel` (`reason`) | returns:cancel |
| POST / GET / DELETE | `/returns/{id}/attachments[/{attachment_id}]` | returns:create, approve or receive / read |
| GET / PATCH | `/settings` (`note_prefix`, `return_prefix`, `return_window_days`, `weight_tolerance_pct`) | shipments:read / settings:update |

Frontend: `/shipments` (list, settings), `/shipments/{id}` (detail with the outcome dialogs, weights, returns, attachments),
`/shipment-returns` (list), `/shipment-returns/new?shipment=<id>` (customer return), `/shipment-returns/{id}` (detail).

## Next phases

- Quality decision on received returns (back to stock, rework, scrap «هالك») from the `return.received` event.
- Links: a shipment from a commercial order (lines pre-filled, ordered vs delivered); the certificate of analysis number on
  the note and the note number on the certificate; a quality gate before dispatch.
- Finance: credit notes for accepted customer returns.
- Drivers and vehicles lists, gate pass, shipping report center.
- Notifications (WhatsApp, SMS, email) reading the event outbox.
