# ADR-009 — Reusable operational records and document snapshots

Status: implemented, 2026-10-13. Extends ADR-005; does not introduce a generic entity module.

## Ownership and boundaries

| Data | Owner | Consumers |
| --- | --- | --- |
| Drivers, vehicles, carriers | Shipping | Shipping and Procurement through `core/interfaces/transport_directory.py` |
| Customer contacts and delivery sites | Commercial | Commercial; Shipping through `core/interfaces/customer_delivery.py` |
| Supplier contacts | Procurement | Supplier profile and purchase orders |
| Quotation terms per issued revision | Commercial | Quotation document builder |
| Downtime/waste reasons, skills, test methods | Master Data reference lists | Owning operational service through `core/interfaces/reference_lists.py` |

Each module remains the writer of its records. The composition root registers providers. Shared contact persistence is mechanical; it does not decide parent visibility or permissions. Parent authorization and locking happen in the owning route.

## Drivers

Affiliation (`internal` / `external`) and storage mode (saved directory record / one-off entry) are independent.

- An internal saved driver references a workforce member in the same organization. A user login is not required.
- An external saved driver cannot reference a workforce member.
- A one-off internal or external driver remains on that shipment/receipt; no driver or user account is created implicitly.
- New or replaced manual driver names require an affiliation. An untouched legacy name may remain unclassified, explicitly displayed as legacy rather than guessed external.
- Vehicles are independent of drivers. A carrier association is optional.
- Directory records are deactivated rather than deleted. Updates require the current version. Internal employee references prevent deleting the employee while the directory refers to them.

## Historical data

Selecting a different saved record copies its operational fields to the shipment, receipt or order. Updating the directory does not update those fields. Keeping the same selected ID preserves the stored snapshot, including full-form requests that try to overwrite its fields. Clearing the ID enables manual entry. Existing inactive selections may remain unchanged; new selections must be active and belong to the correct organization/parent.

Customer and supplier profile legacy fields remain intact. Existing transaction text is not automatically merged into directory records: equal names are insufficient evidence of identity.

The four new supporting lists reuse the existing Master Data screen and permissions. They store the selected canonical English text in existing operational columns, with bilingual choice labels. This is an intentional **text snapshot**, not a live lookup key: renaming a reason, skill or method does not rewrite past records. Until a list is configured, legacy free entry remains supported; after configuration, new text must match an active item. An unchanged historical value can remain. No mass-rename holders are registered for these lists. The original sector/source/country/city key-based behavior remains unchanged.

## Quotation terms

- Draft previews use current active terms.
- Issuance stores both languages for that revision in the same transaction as the existing state transition and approval record.
- Issued documents use that snapshot, including an explicitly empty set of terms.
- Revision retains earlier snapshots; issuing the new revision captures the settings then in force.
- Quotes with issued snapshots cannot be deleted through the quote service; deletion-impact reports the block.
- Historical non-drafts receive a `legacy_baseline` during migration, from the active terms at migration time. This does **not** recover original issued wording. The printed document warns about this limitation. Missing snapshots never silently fall back to current settings.
- Branding, prices and full revision document archival are outside this terms-only change.

## Authorization and migration

`shipping:directory:read` and `shipping:directory:write` govern management. Operational lookup access is limited to the relevant shipment/receipt write permissions or directory permissions. Customer contacts/sites require customer read access; writes also enforce customer update scope. Supplier contacts reuse supplier update permission. Organization IDs and audit actors come from authentication.

Migration `f6a1b2o3` adds seven tables and nullable transaction references/classification columns, and seeds permission definitions without silently granting existing custom roles. It does not delete or rewrite legacy customers, suppliers, shipments or receipts. Downgrade refuses to discard directory records, quote history, or populated new transaction fields; empty-schema upgrade/downgrade is tested separately in PostgreSQL.
