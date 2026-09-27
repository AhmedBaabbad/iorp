# IORP — Industrial Operations & Relationship Platform

v0.1 monorepo. FastAPI backend + Next.js 15 frontend. Modular monolith, layered architecture, multi-tenant by design.

## Status

**Sprint 7 — Complete** (2026-07-07)

Sprint 7 delivered the CAPA frontend UI baseline: Corrective Actions, Action Follow-ups, and Closure/Verification. The flow is nested, navigable, and validated through REV7-001 to REV7-006.

| UI Area | Features | Status |
|---------|---------|--------|
| Commercial | Customers, Samples, Sample Evaluations, Quotes, Commercial Orders | Complete |
| Production | Work Centers, Shifts, Production Orders, Order Items, Shift Reports, Outputs, Downtime Events, Waste Records | Complete |
| Quality/NCR | Quality Checks, Defects, Rejections, NCR Reports, NCR Items | Complete |
| CAPA | Corrective Actions, Action Follow-ups, Closure and Verification | Complete |

**Sprint 6 — Complete** (2026-07-07) — Quality/NCR frontend UI: Quality Checks, Quality Defects, Quality Rejections, NCR Reports, and NCR Items. Validated through REV6-001 to REV6-005.

**Sprint 5 — Complete** (2026-07-06) — Frontend UI expansion: 12 feature modules covering Commercial and Production domains. Validated through REV5-001 to REV5-005.

**Sprint 4 — Complete** (2026-07-03) — Quality/NCR backend baseline: 5 entities, auto-generated codes, quantity constraints, NCR closed-report item guard. 127+ tests pass.

**Sprint 3 — Complete** (2026-07-02) — Production module: 8 entities (work centers through waste records).

**Sprint 2 — Complete** (2026-06-10) — Commercial Slice 2: samples, evaluations, quotes, confirmed orders.

**Sprint 1 — Complete** (2026-06-08) — Foundation: JWT auth, customers, interactions, follow-ups.

Next: dashboard and cross-module summary work, or the next approved frontend roadmap step.

## Stack

| Layer    | Technology |
|----------|-----------|
| Backend  | Python 3.11, FastAPI, SQLAlchemy 2.0, Pydantic v2 |
| Database | PostgreSQL 16, Alembic migrations |
| Frontend | Next.js 15, React 19, TypeScript |
| Auth     | JWT HS256, bcrypt |

## Quick start

See [docs/dev-setup.md](docs/dev-setup.md) for full instructions.

```bash
# 1 — database
docker run -d --name iorp-db \
  -e POSTGRES_USER=iorp -e POSTGRES_PASSWORD=iorp -e POSTGRES_DB=iorp \
  -p 5432:5432 postgres:16-alpine

# 2 — backend  (from repo root)
cd backend && pip install -e ".[dev]"
cp .env.example .env          # set SECRET_KEY before staging
alembic upgrade head
cd .. && python scripts/seed-dev-data.py
cd backend && uvicorn app.main:app --reload --port 8000
# → http://localhost:8000   docs at /docs

# 3 — frontend  (from repo root)
cd frontend && npm install && npm run dev
# → http://localhost:3000
```

Dev credentials after seed: `admin@iorp-dev.com` / `Admin1234!`

## Running tests

```bash
cd backend

# All tests
pytest

# Sprint 4 Quality/NCR baseline (8 focused tests)
pytest tests/quality/test_sprint4_baseline.py -v

# All Quality/NCR tests (54 tests)
pytest tests/quality/ -v

# Full suite
pytest tests/ -v
```

Frontend (from repo root):

```bash
cd frontend && npm run dev
# → http://localhost:3000
```

## Re-seeding from scratch

```bash
# Reset the database and re-apply all migrations
bash scripts/reset-db.sh
cd backend && alembic upgrade head

# Re-seed Sprint 1–4 data (Foundation + Commercial + Production + Quality/NCR)
cd .. && python scripts/seed-dev-data.py
```

The seed is idempotent — it skips silently if the dev org already exists. Drop and re-create to re-seed.

The seed covers:
- Sprint 1: 3 customers, 1 interaction, 1 follow-up
- Sprint 2: sample → evaluation → quote → confirmed order
- Sprint 3: 2 work centers, 3 shifts, 2 production orders, shift report, output, 2 downtime events, waste record
- Sprint 4: quality check (QI-2026-0001), defect, rejection → NCR report (NCR-2026-0001) with 2 items
- Sprint 5: frontend — Commercial and Production entities accessible via the Next.js UI at http://localhost:3000
- Sprint 6: frontend — Quality/NCR entities above accessible via the Next.js UI at http://localhost:3000
- Sprint 7: frontend — CAPA corrective actions, follow-ups, and closure verification accessible via the Next.js UI at http://localhost:3000

## Project layout

```
iorp/
  backend/
    app/
      foundation/     # auth, organizations, users, roles, permissions
      commercial/     # customers, interactions, follow-ups, samples, quotes, orders
      production/     # work centers, shifts, orders, outputs, downtime, waste
      quality/        # quality checks, defects, rejections + NCR reports, items  ← Sprint 4
    tests/
    alembic/
  frontend/
    src/
      app/            # Next.js App Router shells
      features/       # domain feature components
      types/          # TypeScript types
      lib/            # api-client, auth helpers, utilities
      styles/         # shared style tokens
  docs/
  scripts/
```

## Documentation index

### Frontend

| Document | Content |
|----------|---------|
| [docs/frontend/patterns.md](docs/frontend/patterns.md) | Sprint 5–7 frontend patterns — feature structure, UX states, Quality/NCR and CAPA references |
| [docs/frontend/next-steps.md](docs/frontend/next-steps.md) | Post-Sprint 7 frontend notes and next recommended direction |

### Roadmap

| Document | Content |
|----------|---------|
| [docs/roadmap/sprint-1.md](docs/roadmap/sprint-1.md) | Sprint 1 scope and status |
| [docs/roadmap/sprint-2.md](docs/roadmap/sprint-2.md) | Sprint 2 scope and status |
| [docs/roadmap/sprint-3.md](docs/roadmap/sprint-3.md) | Sprint 3 scope and status |
| [docs/roadmap/sprint-4.md](docs/roadmap/sprint-4.md) | Sprint 4 scope and status — Quality/NCR backend |
| [docs/roadmap/sprint-5.md](docs/roadmap/sprint-5.md) | Sprint 5 scope and status — Frontend UI expansion |
| [docs/roadmap/sprint-status.md](docs/roadmap/sprint-status.md) | Cumulative sprint status — Sprint 1 through Sprint 7 |

### Backend

| Document | Content |
|----------|---------|
| [docs/dev-setup.md](docs/dev-setup.md) | Local setup, seed, test, re-seed |
| [docs/modules/foundation.md](docs/modules/foundation.md) | Foundation module notes |
| [docs/modules/commercial.md](docs/modules/commercial.md) | Commercial module notes |
| [docs/modules/production.md](docs/modules/production.md) | Production module notes |
| [docs/modules/quality.md](docs/modules/quality.md) | Quality/NCR module notes — Sprint 4 |
| [docs/api/sprint-1.md](docs/api/sprint-1.md) | Sprint 1 API endpoints |
| [docs/api/sprint-2.md](docs/api/sprint-2.md) | Sprint 2 API endpoints |
| [docs/api/production.md](docs/api/production.md) | Production API endpoints |
| [docs/api/quality.md](docs/api/quality.md) | Quality/NCR API endpoints — Sprint 4 |
| [docs/erd/sprint-1.md](docs/erd/sprint-1.md) | Sprint 1 tables |
| [docs/erd/sprint-2.md](docs/erd/sprint-2.md) | Sprint 2 tables |
| [docs/erd/sprint-3.md](docs/erd/sprint-3.md) | Sprint 3 tables |
| [docs/erd/sprint-4.md](docs/erd/sprint-4.md) | Sprint 4 tables — Quality/NCR |
# First-run initialization

Set a strong one-time `IORP_BOOTSTRAP_TOKEN`, migrate an empty database, then open
`/setup`. The bootstrap request atomically creates the Platform Root, first
organization, organization administrator, permissions, roles, and persistent
installation state. Remove or rotate the environment token immediately after a
successful initialization.

The Platform Root uses `/api/v1/platform/login`; tenant accounts continue to use
`/api/v1/auth/login`.

Emergency password reset:

```sh
cd backend
python -m app.cli.reset_platform_root_password --email root@example.com
```

Docker:

```sh
docker compose exec backend python -m app.cli.reset_platform_root_password --email root@example.com
```

Destructive local database reset:

```sh
cd backend
python scripts/reset_database.py
```
