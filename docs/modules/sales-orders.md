# Sales orders and the quotation lifecycle (SALES-001)

The flow: **quotation → sales order (the agreement) → production demand(s) → planning**. Each document is independent
once copied: changing the order does not change the quotation, and a demand keeps what it took from the order.

## Quotation (`commercial_quotes`)

| From | Step | To | Reason |
|---|---|---|---|
| draft | `POST /quotes/{id}/issue` | issued | — |
| issued | `/accept` | accepted (final) | optional |
| issued | `/reject` | rejected | required |
| issued | `/expire` | expired | optional |
| issued · rejected · expired | `/revise` | draft, `revision + 1` | required |

- Edited (`PATCH`) only as a draft (`QUOTE_NOT_DRAFT`); the status never changes through `PATCH`.
- An accepted quotation is final: not edited, not deleted (`QUOTE_ACCEPTED`). `POST /quotes/{id}/sales-order` makes a draft
  sales order from it (its lines, specifications, prices and currency). One order in force per quotation
  (`ORDER_EXISTS_FOR_QUOTE:<number>`; a cancelled order frees it).
- Read: `revision`, `allowed_actions` (`edit`, `issue`, `accept`, `reject`, `expire`, `revise`, `create_order`), `history`, `orders`.

## Sales order (`commercial_orders`)

| From | Step | To | Condition |
|---|---|---|---|
| draft | `POST /orders/{id}/confirm` | confirmed | a line; an **accepted** quotation (`ORDER_QUOTE_NOT_ACCEPTED`) or, for a direct order, the customer's reference (`ORDER_SOURCE_REQUIRED`); a currency when priced (`ORDER_CURRENCY_REQUIRED`) |
| confirmed | `/revise` (reason) | draft, `revision + 1` | nothing in production (`ORDER_HAS_PRODUCTION_HISTORY`) |
| draft · confirmed | `/cancel` (reason) | cancelled | confirmed: nothing in production |

- A confirmed order is locked: lines, quantities, specifications and prices (`ORDER_LOCKED`).
- Lines: a product from master data, its specification by the product's template (`ORDER_SPEC_INVALID:<property>`), quantity,
  unit (`ORDER_UNIT_INVALID`), an optional agreed price. Lines carried from the quotation as they are stay valid even if
  written before the product list. Currency: SAR or USD; from the quotation, else the organization's default.
- Delete: a draft never confirmed and never sent to production; otherwise it is cancelled, so its history stays.
- Read: `allowed_actions` (`edit`, `confirm`, `transfer`, `revise`, `cancel`, `delete`, each by the user's permission;
  `transfer` needs production's `production:demands:create`), `transferred_quantities` per line, `fulfilment`
  (`none` · `partial` · `full`), `history`.

## Status history (`commercial_status_history`)

One row per step of a quotation or a sales order: action, from and to status, revision, reason, who and when. Never
changed; removed only with a draft that is deleted.

## Sending a confirmed order to production

- `GET /production/demand-lookups/sales-orders?customer_id=` — the customer's confirmed orders with, per line, what was
  ordered, what the demands in force took, and what remains.
- `POST /production/demands/from-sales-order {sales_order_id, lines: [{order_item_id, quantity}], transfer_key, …}` — a demand
  with part (or all) of the lines. A line never takes more than what remains (`quantity_exceeds_remaining`); the order must
  be confirmed (`sales_order_not_confirmed`). The same `transfer_key` returns the same demand (a retry).
- A demand's lines from an order keep its product, specification and unit (`sales_order_lines_locked`); the quantity may
  change within what remains. Cancelling the demand gives its quantity back; reopening it takes it again only if still free.
- The order row is locked while a transfer, a revision or a cancellation is decided, so they never cross.

## Boundaries

`core/interfaces/sales_order_source.py`: commercial registers `CommercialSalesOrderSource` (snapshots), production
registers `ProductionSalesDemandUsage` (quantities taken) and its permission code. No module imports the other.

## Screens

- `/commercial-orders/new` — «تسجيل طلب العميل الداخلي وتحديد المنتجات والكميات والمواصفات المطلوبة»: from an accepted
  quotation or a direct order; products from master data and specifications by template (no JSON); prices optional.
- `/commercial-orders/{id}` — status, revision, fulfilment, the lines with sent and remaining, actions and history.
- `/quotes/{id}` — the quotation's next step, its sales order, and history. The status field is gone from the edit form.
- `/production/demands/new` — from a confirmed sales order (default), or a manual demand.

Migration `f6a1b2k5` adds the columns, the history table and the demand links; existing records stay unlinked.
