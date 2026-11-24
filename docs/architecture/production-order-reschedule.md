# Production order rescheduling

Open orders can change their planned dates through `POST /production/production-orders/{id}/reschedule`, with `production:production_orders:update`. A trimmed reason of 3–500 characters and an end date are required. The start date is optional; once actual execution has started, or the order is in progress/on hold, it cannot change. Completed, closed and cancelled orders cannot be rescheduled. The end cannot precede the start, and an unchanged schedule is rejected.

The service locks the tenant-scoped order row before validating its current state. Dates and the `production_order.rescheduled` activity event commit together. Audit failure rolls back the date change. Generic PATCH date changes use the same rules and audit event, with a null reason; a no-op PATCH creates no event. Status and actual execution timestamps are unchanged.

The existing activity log stores old/new start and end dates, reason and the actor snapshot. Authorized order readers receive the scoped rescheduling history in the order response, without requiring global activity-log access. No migration is needed.

The detail page edits dates in a RecordDialog and refreshes the dates, overdue flags and timeline after success. Both allocation entry points offer an optional end-date extension for overdue orders. The extension completes before allocation; extension failure prevents allocation. If extension succeeds but allocation fails, the audited extension remains and retrying allocation does not repeat it. Form values remain available for retry.

Overdue flags use the organization's calendar date on the server, including eligible-order results. The browser does not infer lateness from its own timezone.

The Playwright rescheduling scenario exercises the real Arabic detail page against a deterministic API fixture on desktop and mobile. Backend integration tests independently exercise authorization, audit atomicity, lifecycle restrictions and PostgreSQL row-lock concurrency.
