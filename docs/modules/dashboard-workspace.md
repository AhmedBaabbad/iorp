# Dashboard workspace

Routes: `/dashboard` (organization overview), `/commercial-dashboard`, `/production`, `/quality-dashboard`, `/shipping-dashboard`, `/procurement-dashboard`.

The overview separates each department into its own section, with up to four representative indicators, a trend/distribution and a link to all indicators and priorities. The organization snapshot is explicitly current, independent of the selected period. Detail pages display all indicators, workload, distributions, rankings and attention items returned by the owning module.

## Layout and behavior

- Period tiles show totals, the previous-period change, today's value and small trends where supplied.
- Rate cards use circular indicators; open-work cards are separate compact counters labelled as current workload.
- Charts use semantic colors for accepted/rejected results, responsive SVG sizing, interactive legends and CSV export.
- The chosen period is preserved in navigation links; refresh reloads every visible section.
- Failed sections show an explicit error and recover through refresh. Zero, absent data, loading and lack of permission are separate states.
- Data is never kept in a shared module-level cache. Component data is keyed by organization, user, effective permissions, period and refresh generation, and late responses are ignored.
- Arabic/English labels, RTL layout and existing theme tokens are used throughout. Narrow-layout visual review caught and fixed intrinsic grid/SVG overflow.

## Data and architecture

Each module computes its own indicators from its own tables and returns `app/core/dashboard.py`'s shared response. The overview composes the module endpoints in the frontend; it does not introduce cross-module database joins. Procurement now has a dashboard service in its application layer and a read-guarded API adapter. Commercial's existing dashboard adapter is registered in the composition root.

Existing resource read permissions control endpoint access and each section; no new dashboard role or blanket dashboard permission is introduced. Customer counts respect own scope. Unauthorized sections are not fetched by the frontend and are omitted by the backend.

Quality's acceptance KPI is **accepted or conditionally accepted closed inspections / all closed inspections**, not a sum of quantities in incompatible units. A zero denominator returns null. Commercial monetary totals remain separate by currency. Production retains its existing measured-unit selection; the displayed unit identifies the included output (units are never added together). Existing time-window helpers use UTC days and compare with the preceding window of equal length. Current-work cards are not period totals.

No database migration is needed for the dashboards. The earlier authorization migrations are documented separately in `docs/security/authorization-audit-2026-10-07.md`.

## Main implementation files

- `frontend/src/features/dashboard/DashboardWorkspace.tsx`, `workspace.module.css`, `departments.ts`, `DashboardPage.tsx`
- `frontend/src/components/dashboard/{DashboardKit.tsx,types.ts,dashboard.module.css}`
- New app pages and sidebar links in `frontend/src/components/layout/page-frame.tsx`
- Arabic/English `dashboard.json` and `navigation.json`
- `backend/app/{commercial,production,quality,shipping,procurement}/application/dashboard_service.py`
- Dashboard route adapters and composition in `backend/app/main.py`

## Verification

### Commercial follow-ups and samples (2026-10-07)

Both the commercial dashboard and overview show separate follow-up and sample groups, outside the overview's first-four-card limit. Cards remain conditional on backend read permissions and record scopes.

- Open follow-ups only: overdue means due before the current instant; remaining today means now through UTC midnight; upcoming means tomorrow through seven days from now (exclusive). These three groups do not overlap. Completed and cancelled follow-ups are excluded. Attention includes overdue and remaining-today items.
- Accepted/rejected samples use `Sample.sample_decision`, not individual evaluation results. Pending includes null legacy decisions. Cancelled samples are excluded. Awaiting evaluation uses the delivered lifecycle state and may overlap pending decision.
- These are current counts, independent of the selected chart period. Sample requests remain a period metric. Links open the existing samples list or all-follow-ups tab under their existing access controls; they do not pretend to apply unsupported decision filters.
- No schema change or migration. Targeted verification covers time boundaries, tenant isolation, own scope, permissions and overview visibility.

- Backend dashboard and route-denial suite: **368 passed**; `backend/artifacts/dashboard-verification.log`.
- Module-boundary checks: **12 passed**.
- Dashboard component tests: **5 passed**, including unauthorized-section suppression, identity-switch data clearing and Arabic error/retry behavior.
- TypeScript, targeted ESLint and Arabic/English message parity checks passed.
- Headless Edge visual review used the actual components with explicitly synthetic fixture data at desktop and narrow widths, without reading credentials or modifying business records. This is a layout review, not an authenticated end-to-end production-data browser test.
