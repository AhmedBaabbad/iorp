# IORP v0.1 — Developer Setup

Sprint 1 baseline. Everything runs locally with Docker for the database.

---

## Prerequisites

- Python 3.11+
- Node.js 20+
- Docker Desktop

---

## 1. Start the database

```bash
docker run -d \
  --name iorp-db \
  -e POSTGRES_USER=iorp \
  -e POSTGRES_PASSWORD=iorp \
  -e POSTGRES_DB=iorp \
  -p 5432:5432 \
  postgres:16-alpine
```

---

## 2. Backend

```bash
cd backend

# Install dependencies (first time)
pip install -e ".[dev]"

# Copy env and adjust SECRET_KEY
cp .env.example .env

# Run migrations
alembic upgrade head

# Seed development data (idempotent — safe to re-run)
cd ..
python scripts/seed-dev-data.py
cd backend

# Start the API server
uvicorn app.main:app --reload --port 8000
```

API is at `http://localhost:8000`
Docs at `http://localhost:8000/docs`

**Dev credentials (after seed):**

| Role      | Email                  | Password    |
|-----------|------------------------|-------------|
| Admin     | admin@iorp-dev.com     | Admin1234!  |
| Sales Rep | sales@iorp-dev.com     | Sales1234!  |

**Seed data created:**

| Entity | Code / Number | Customer |
|--------|--------------|---------|
| Customers | CUST-001, CUST-002, CUST-003 | — |
| Interaction + Follow-up | — | CUST-001 |
| Sample | SAMP-001 (evaluated) | CUST-002 |
| Sample Evaluation | accepted → proceed_to_quote | CUST-002 |
| Quote | Q-2026-001 (issued, SAR 2,950.00) | CUST-002 |
| Order | ORD-2026-001 (confirmed) | CUST-002 |

---

## 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

App is at `http://localhost:3000`

---

## 4. Run backend tests

Tests use SQLite in-memory — no running database needed.

```bash
cd backend
pytest
```

To run a specific module:

```bash
pytest tests/foundation/test_auth.py -v
pytest tests/commercial/test_customers.py -v
```

---

## 5. Re-seed (clean slate)

To reset dev data, drop and recreate the database:

```bash
docker exec -it iorp-db psql -U iorp -c "DROP DATABASE iorp;"
docker exec -it iorp-db psql -U iorp -c "CREATE DATABASE iorp;"
cd backend && alembic upgrade head
cd .. && python scripts/seed-dev-data.py
```

---

## Notes

- `SECRET_KEY` in `backend/.env` must be changed before staging deployment.
- The root path (`/`) redirects to `/customers`. Unauthenticated users are
  redirected to `/login` automatically.
- All commercial data is org-scoped. The seed creates one org (`dev-org`).
