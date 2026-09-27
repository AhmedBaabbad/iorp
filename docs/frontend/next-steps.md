# Frontend - After Sprint 7

Sprint 7 completed the CAPA UI baseline. This note keeps the next frontend step clear without adding a heavy documentation process.

---

## Sprint 7 delivered

CAPA now has three frontend feature areas:

| Feature | Location | Notes |
|---------|----------|-------|
| Corrective Actions | `frontend/src/features/corrective-actions/` | List, create, detail, status badges, priority badges, source context links |
| Action Follow-ups | `frontend/src/features/action-follow-ups/` | Nested section inside Corrective Action detail; inline create form |
| Closure Verifications | `frontend/src/features/closure-verifications/` | Singleton nested section inside Corrective Action detail |

Routes added:

| Route | Purpose |
|-------|---------|
| `/corrective-actions` | Corrective actions list |
| `/corrective-actions/new` | Create corrective action |
| `/corrective-actions/[id]` | Corrective action detail with follow-ups and closure verification |

No standalone routes were added for action follow-ups or closure verifications. They stay nested under the corrective action context.

---

## Current frontend patterns in use

- Feature-oriented structure: each feature keeps its own `api/`, `types/`, `components/`, and `index.ts`.
- Thin pages: `frontend/src/app/` pages import and render feature components only.
- API integration: all HTTP calls use `apiClient` through feature-local API files.
- UX baseline: list/detail/create flows use loading, empty, error, retry, and submit states where appropriate.
- Status changes: lifecycle transitions use action buttons on detail pages, not status selects in create forms.
- Nested sections: repeatable child records use `SectionShell`, an "Add ..." toggle, inline form, refresh-after-create, and closed-parent guards where needed.

---

## Pending after Sprint 7

Keep the next phase MVP-safe. Do not add broad workflow engines or enterprise features yet.

Recommended next frontend direction:

1. Dashboard and cross-module summaries, if approved.
2. Role-based UX improvements, if approved.
3. Better source pickers for CAPA source links, if manual UUID entry becomes a real user pain.
4. Continue the same feature-oriented pattern for any future Quality/NCR/CAPA expansion.

Explicitly still out of scope unless approved:

- Analytics dashboards with KPIs beyond simple navigation/discoverability.
- Notifications and escalations.
- Advanced workflow builders.
- Global state management libraries.
- Generic shared badge/status frameworks.
