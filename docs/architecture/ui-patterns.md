# UI patterns

Short records open in a modal dialog for both creation and editing. Use the shared `RecordDialog`, built on `Dialog`, with a responsive field grid, errors before the fields, and Save/Cancel actions. A failed save keeps the dialog open with its values intact; cancellation remains available when no save is running.

Never navigate away from a form to create a missing record. Inline additions use `RecordDialog`, retain all parent-form data, refresh every mounted catalog consumer, and select the created record immediately. The product template and its fields must be available as soon as the new product is selected. A management link may appear inside the creation dialog only and must explicitly say that it opens a new tab.

Classify screens consistently: short records use dialogs; long documents use full pages with inline-add dialogs and an unsaved-changes guard; detail pages with multiple sections use tabs. Downtime, waste, inspections and rejections opened from a detail page reuse the same field components and API calls as their standalone creation pages, with their parent record fixed and their originating section refreshed after a successful save.

Long-document forms use `useUnsavedChangesGuard(dirty)` through `useUnsavedFormChanges` with a snapshot of editable data. Browser refresh/close triggers `beforeunload`; Back, Cancel and sidebar links in the same tab trigger a translated confirmation dialog. Programmatic Back/Cancel actions use `requestNavigation`. Successful saves call `markSaved` before redirecting or showing their success state. Lookup results and automatic initial defaults do not count as user edits.

Detail pages with multiple sections use the shared accessible `Tabs`. Tabs support arrow keys (reversed in RTL), Home/End, and persist selection in `?tab=` while retaining other query parameters. Each tab owns a labelled tab panel.

Long documents, including shipments, quotations and sales orders, keep full-page forms with clear sections. Use the shared searchable `Combobox` for record selection, including secondary option details and a clear action. A selected saved record shows its copied fields read-only. A labelled manual-entry action removes the binding; the server remains authoritative for saved snapshots.

This change applies these patterns only to customer contacts/sites, the transport directory and shipments. Other modules will migrate in separate PRs. Existing manual tabs in `NotificationCenter.tsx`, `followups-list-page.tsx`, and `NotificationsPage.tsx` remain unchanged and are future migration candidates.

Record selection must retain the active-default and explicit-contact rules from PR #24. Changing a site must never replace a contact the user selected. Existing document snapshots must not be refreshed just by opening an edit form. Quantity rendering uses `formatQuantity` and preserves up to three decimal places without trailing zeros.

## Current API boundary

Transport option responses omit driver personal fields and vehicle type. The UI can enrich these options using the full directory only with `shipping:directory:read`; it must not bypass that permission. Users with document permissions alone retain server-side snapshot copying and receive an explanatory hint. Immediate display of those protected fields for these users requires a separately approved API projection change; this frontend change does not alter the server contract.

## Verification

Run `npm test`, `npx tsc --noEmit`, `npm run lint`, and `npm run build` from `frontend`. For browser checks, install Chromium with `npx playwright install chromium`, then run `npm run test:e2e`. `E2E_CHROME_PATH` can select an existing Chrome executable. Browser tests use deterministic API fixtures to verify UI flows on desktop and phone viewports, including Arabic RTL; backend integration tests verify the server independently.
