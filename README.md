# IORP — Industrial Operations & Relationship Platform

v0.1 monorepo. FastAPI backend + Next.js 15 frontend. Modular monolith, layered architecture, multi-tenant by design.

## Status

**Sprint 1 — Complete** (2026-06-08)

Sprint 1 delivered a full vertical slice: JWT auth, multi-tenant customer records, interaction logging, and follow-up management — backend API, database, and frontend UI. 12 backend tests pass.

Next: Sprint 2 — Commercial Slice 2 (samples, sample evaluations, quotes).

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

## Project layout

```
iorp/
  backend/
    app/
      foundation/     # auth, organizations, users, roles, permissions
      commercial/     # customers, interactions, follow-ups  ← Sprint 1
      production/     # planned
      quality/        # planned
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

| Document | Content |
|----------|---------|
| [docs/dev-setup.md](docs/dev-setup.md) | Local setup, seed, test, re-seed |
| [docs/roadmap/sprint-1.md](docs/roadmap/sprint-1.md) | Sprint 1 scope and status |
| [docs/api/sprint-1.md](docs/api/sprint-1.md) | Implemented API endpoints |
| [docs/modules/foundation.md](docs/modules/foundation.md) | Foundation module notes |
| [docs/modules/commercial.md](docs/modules/commercial.md) | Commercial module notes |
| [docs/erd/sprint-1.md](docs/erd/sprint-1.md) | Implemented tables |
