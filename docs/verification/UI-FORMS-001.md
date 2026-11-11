# UI-FORMS-001

Base: `origin/main` at `d1accc9dbeb7c1d697faa94d4db7429471778bda` (PR #9).
Branch: `fix/ui-forms`. UX-BATCH-A is deferred, as directed by the user.

## Implementation

- Eight form tokens in `globals.css`; the border token resolves against each theme's existing `--border-strong`.
- Both existing styling systems retained. Matching label size/weight, field gap, padding, border, radius, control font, and textarea minimum size.
- Fixed 44px native input/single-select height in global type-aware selectors, so shared inline styles do not impose that height on multiple selects, checkboxes or radios.
- Form grids align at the start and use the common form gap, including inline sharedStyles grids and filter grids outside forms. Existing bare labels around shared inline controls also receive the common label/field tokens.
- ListSelect management link is an accessible gear icon next to the select, preserving its permission gate, URL, new tab behavior, loading state, free text fallback and change callbacks. The existing localized management text supplies both title and accessible name.
- DirectorySelect search and selection share one shrinkable flex row. Existing search, option retention and error text remain intact.
- Accessible FormSection uses fieldset/legend, an optional described-by description, and a responsive field grid. Supplier create/edit is the only screen-specific adoption; it reuses the existing form title.
- Customer, password, quote and shift components were not edited. Quote PDF and translation files were not edited. No global overflow hiding was introduced.

## Automated verification

- `npx tsc --noEmit`: passed.
- `npm run lint`: passed, 0 errors and 22 warnings (within the requested ceiling).
- `npm test`: 90 Node tests and 303 Vitest tests passed on the successful full rerun (53 Vitest files).
- Initial full run: all assertions passed, but an existing NotificationCenter ringing timer fired after jsdom teardown (`window is not defined`). The complete rerun passed without that error. Notification code was not changed.
- `npm run i18n:check`: passed, 32 Arabic/English file pairs.
- New Node tests cover root token definitions, use by both systems, grid alignment, textarea sizing, native-control exclusions and the shrinkable management row.
- New ListSelect Vitest tests cover management-link adjacency, accessible naming, icon, destination/new tab, permission denial, change callback and free text fallback.
- `git diff --check`: passed.

## Manual screen verification — incomplete

No screen is claimed as visually verified. Browser automation discovery reported the browser host unavailable. Native-window access first timed out awaiting app approval; a subsequent Computer Use attempt was stopped because the tool could not determine the current browser URL with sufficient confidence to enforce its policy. No further UI actions were attempted.

The following is **source inspection**, not manual browser verification:

| Required screen | Source inspection | Remaining visual verification |
| --- | --- | --- |
| Customers | Shared styles and ListSelect inherit the common tokens; no customer files edited. | Create/edit, RTL/LTR and mobile, including management permissions. |
| Suppliers | Shared CSS fields and ListSelect; FormSection example preserves inputs and submission code. | Create/edit, fieldset appearance, disabled state and mobile. |
| Materials | Shared CSS grid/fields and existing UnitSelect/ProductSelect. | Dialog, selects and textarea alignment on mobile. |
| Vehicles / transport directory | Shared CSS grid/fields, ListSelect for vehicle type, DirectorySelect for saved records. | Long plate/driver options and the search/select row in RTL/LTR. |
| Shipment | Shared CSS fields; DirectorySelect and TransportSelection. | Header and line rows, conditional driver warnings, mobile. |
| Production order | Legacy create component redirects to production planning; list filters use shared styles. | Actual planning/allocation workflow and order screens. |
| Shift definition | Shared inline field/label/input styles; no shift-specific edits. | Time input/select alignment and mobile; other redesign deferred to UX-BATCH-A. |
| Users | Bare labels around shared inline controls inherit the common field/label tokens; role checkboxes excluded. | Email helper/error rows, role choices and mobile. |

Unresolved visual alignment defects cannot be ruled out without browser verification. In particular, conditional shipment/driver warnings and long directory values still need observation. Mobile overflow and dark/RTL/LTR appearance are not certified by source or jsdom tests.

## Repository hygiene

The only pre-existing untracked paths were four `.worktrees/` directories, explicitly accepted by the user. They were not deleted, modified or staged. Their own working trees were clean at inspection. No other pre-existing tracked modifications were found.
