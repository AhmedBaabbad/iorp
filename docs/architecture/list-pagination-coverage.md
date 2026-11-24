# List pagination coverage

This extends [ADR-006](../adr/ADR-006-pagination.md). Operational lists use server-side filtering and counting before `OFFSET`/`LIMIT`. The UI uses `Pagination`, `ListToolbar`, URL state, a default of 50 rows, and sizes 25/50/100.

## Compatibility and implementation

Legacy array endpoints opt into the standard `Page` envelope when `page` or `page_size` is supplied. Calls without either parameter retain their array contract, including existing picker, document, and export callers. Existing explicit legacy limits remain; the new paged queries do not inherit those limits. Products' legacy catalog remains an array and no longer truncates at 500 products.

API clients expose typed overloads for the two contracts. `useListPage` keeps URL filters and page metadata together, ignores responses from an earlier filter or parent record, and returns to the last available page after deletion. Small configuration catalogs use `useClientListPage`; filtering always precedes slicing. A legacy-array fallback supports existing callers and test fixtures; server filtering remains the authority for operational lists.

Incoming/returned quality queues page **whole source documents** after checking whether any eligible line remains unfinished. All eligible lines belonging to a selected document are returned together, including already inspected lines. Completing a whole document removes it before the count and page are calculated.

The product legacy-mapping dialog searches its options separately on the server; its options are not limited to the product table's currently visible page.

## Coverage changed in this PR

| List | Before | After / execution |
| --- | --- | --- |
| Shipments | Array, hidden 500-row cap, no pager | Server `Page`, URL filters, shared toolbar/pager |
| Shipment returns | Array, hidden 500-row cap, no pager | Server `Page`, URL filters, shared toolbar/pager |
| Quality specifications | Array capped at 500 | Server `Page`, status/product/search before paging |
| Quality test parameters | Complete array, no pager | Server `Page`, active/inactive/search |
| Defects within a quality check | Complete scoped array | Server `Page`, check ownership and filters before count |
| Sample evaluations | Complete scoped array | Server `Page`, existing ownership scope retained, batch evaluator names |
| Production results | Complete completed/closed order array | Server `Page` over orders, then batch result enrichment |
| Shift definitions | Complete array | Server `Page`, search/status/type |
| Work centers | Complete array | Server `Page`, search/status/type |
| Workforce members | Legacy limit/offset array | Server `Page`, worker/employment/status/search before count |
| Administration users | Complete array, archived rows hidden locally | Server `Page`, archived/status/search filters before count |
| Products | Catalog array capped at 500 | Server `Page`, kind/search before paging |
| Suppliers | Array capped at 500 | Server `Page`, existing filters and batch enrichment |
| Materials | Array capped at 500 | Server `Page`, category/search/active filters |
| Purchase orders | Array capped at 500 | Server `Page`, existing supplier/status/date/search filters |
| Goods receipts | Array capped at 500 | Server `Page`, existing supplier/status/date/lot search filters |
| Returns awaiting quality | Array capped at 300 source lines | Server `Page` over eligible return documents |
| Incoming goods awaiting quality | Array capped at 300 source lines | Server `Page` over eligible receipt documents |
| Customer contacts / delivery sites | Existing server pages fixed at 50 | Honor validated `page_size`; shared URL toolbar/pager |
| Supplier contacts | Existing server pages fixed at 50 | Honor validated `page_size`; shared directory toolbar/pager |
| Transport drivers / vehicles / carriers | Existing server page contract; custom previous/next controls | Shared URL toolbar/pager and size selector; existing search/order behavior retained |
| Follow-ups | Server pages with local state and custom footer | Shared URL toolbar/pager, default 50 |
| Demands / planning queue | Server pages with local filters and 20-row footer | Shared URL toolbar/pager, default 50, existing status visibility and export filters retained |
| Roles | Complete configuration array | Client search/paging with URL state |
| Administration roles | Complete configuration array | Client search/paging with URL state |
| Permission catalog | Complete deployed catalog | Client search/module filtering/paging with URL state |
| Reference lists | Complete bounded configuration list | Client search/paging with URL list selection; complete parent choices retained |
| Platform audit | Existing server paging, fixed 25, local state | Shared URL toolbar/pager, default 50 |
| Platform organizations | Existing client paging, default 10, local filters | Shared URL toolbar/pager, default 50, URL filters and sorting; existing client execution retained |

Drivers already sort/search their workforce-projected display values in memory through the workforce interface. This PR preserves that implementation and its batch-read behavior; it does not introduce a cross-module model import or claim SQL paging for the projected driver list.

## Already covered and retained

Customers, quotations, sales orders, samples, production orders, downtime events, waste records, quality checks, global defects, quality rejections, certificates, NCR reports, corrective actions, notifications, and separated tenant/platform activity/security logs already use server `Page` responses and `Pagination`. Their existing behavior is retained. Document history, dashboard summaries and embedded document lines are not independent list pages.

## Explicit exceptions

* Roles and permissions are small configuration catalogs. Their existing endpoints remain arrays; client filtering/paging is deliberate.
* Master-data reference lists have the existing `MAX_ITEMS = 500` limit per list. Their complete country/parent hierarchy is needed by editors and pickers, so their table pages locally.
* Platform organizations already page locally and use the full organization inventory for global status counters, industry facets and sorting. This PR retains that existing execution choice while unifying controls and URL state. It does **not** add server paging to that endpoint; a separate inventory/aggregate contract would be needed to remove the full read without losing these features.
* `ProductionOrderItemsList` edits the lines of one order document together; paging those lines would hide part of the document while editing and calculating totals. It is an explicit source-test exception.
* `ListSelect` is a searchable reference picker, and `ListCreateDialog` creates one record. Neither is a list page; both are explicit source-test exceptions.

`frontend/tests/list-pagination-coverage.test.mjs` scans every `features/**/*List*.tsx` and `*-list-page.tsx`, plus known list pages with other names. A new matching page without an imported and rendered `Pagination` fails the test. Exceptions must be explicit and documented above.

## Database changes

No migration, database schema change, or new index. Paging uses existing organization/source/identifier columns. New SQL orders end with a unique identifier. Query performance on a production-sized PostgreSQL dataset has not been benchmarked by this change.
