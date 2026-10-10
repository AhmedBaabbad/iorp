# ADR-007: A permission for every decision, readable names, and the sales representative's own customers (RBAC-002)

## Context

A review of all 398 routes found that every business route requires a permission, but several decisions were still
granted by a general one: the permanent delete of a user came with "deactivate", sending a purchase order with "edit",
closing one with "approve", closing a shipment with "cancel", a failed delivery with "deliver", rejecting a return with
"approve", the non-conformance stages with "edit", mapping legacy values (which rewrites records in every module) with
"edit". Some permissions existed with nothing behind them (editing and deleting interactions and evaluations), and the
commercial module carried vague "write" (manage) permissions. Names were composed mechanically ("تحديث العملاء"), and a
sales representative's read scope covered customers but not their quotations, orders and samples.

## Decision

1. **A permission for each decision.** The code (`module:resource:action`) is what the server checks; a decision never
   shares its code with ordinary editing.

   | Action | Permission |
   |---|---|
   | Delete a user permanently | `foundation:users:delete` |
   | Record a failed delivery / close an undelivered note | `shipping:shipments:fail` / `shipping:shipments:close` |
   | Reject a customer's return | `shipping:returns:reject` |
   | Send a purchase order to the supplier / close it | `procurement:purchase_orders:send` / `:close` |
   | Containment, root cause, submission of a non-conformance | `quality:ncr_reports:contain` / `:investigate` / `:submit` |
   | Issue a replacement certificate (it revokes the original) | `quality:certificates:issue` **and** `:revoke` |
   | Map legacy product types / list values | `masterdata:products:map_legacy` / `masterdata:lists:map_legacy` |
   | Correct / delete an interaction | `commercial:interactions:update` / `:delete` (new routes and screens) |
   | Correct / delete a sample evaluation | `commercial:evaluations:update` / `:delete` (new routes and screens) |

   Done at the same time (another session): quotation and sales order steps, sample stages, follow-up cancel and reopen,
   production demand release and cancel, shipment ready, reopen and reschedule, closing a shift roster.
2. **No vague permissions.** `commercial:*:write` was removed; create, update and delete say exactly what is allowed.
3. **Readable names.** `backend/app/foundation/domain/permission_labels.py` gives every permission an Arabic and English
   name and a one-line description of what it allows («تعديل بيانات عميل» / "Edit customer details"). Screens show them
   in the user's language; the code stays as it is. A test requires an entry for every permission.
4. **Own customers.** `commercial:quotes:read`, `commercial:orders:read` and `commercial:samples:read` are scopable through
   the customer's sales owner (`customer.sales_owner_user_id`). At scope "own" (or "team", until teams exist) a user
   lists, opens, prints and acts on only their own customers' records, and creates them only for those customers; a
   broader scope or the organization's root sees all (`commercial/application/visibility.py`).
5. **System roles.** The new permissions go to the roles that held the general permission they come from. The sales
   representative now works their own customers' quotations, samples and draft sales orders (reads at scope "own");
   confirming, revising and cancelling a sales order stays with the commercial manager.
6. **Screens.** Every create, edit and delete button of the customers module shows only to who holds its permission;
   the new and edit pages are guarded; record actions follow the server's allowed actions. The server checks again.

Migration `f6a1b2k8` applies it to existing organizations (custom roles receive nothing implicitly) and records every
change so the downgrade restores the previous state.
