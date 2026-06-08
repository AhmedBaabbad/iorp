# API Reference — Sprint 1

Base URL: `http://localhost:8000/api/v1`

All protected routes require `Authorization: Bearer <token>`.
Interactive docs: `http://localhost:8000/docs`

---

## Auth

### POST /auth/login
Authenticate a user and receive a JWT.

**Body:**
```json
{ "email": "admin@iorp-dev.com", "password": "Admin1234!" }
```

**Response 200:**
```json
{ "access_token": "<jwt>", "token_type": "bearer" }
```

**Response 401:** Invalid credentials.

---

### GET /auth/me
Return the current authenticated user's profile.

**Headers:** `Authorization: Bearer <token>`

**Response 200:**
```json
{
  "id": "<uuid>",
  "organization_id": "<uuid>",
  "organization_code": "dev-org",
  "full_name": "Dev Admin",
  "email": "admin@iorp-dev.com",
  "status": "active",
  "roles": ["admin"]
}
```

---

## Customers

All customer routes are scoped to the caller's organization.

### POST /commercial/customers
Create a new customer record.

**Required fields:** `customer_code`, `name`
**Optional fields:** `sector`, `city`, `country`, `status`, `relationship_stage`, `priority_level`, `opportunity_source`, `estimated_consumption`, `assigned_sales_user_id`, `notes`

**Response 201:** `CustomerRead`
**Response 400:** Duplicate `customer_code`, or `assigned_sales_user_id` not in same org.

---

### GET /commercial/customers
List all customers in the caller's organization.

**Response 200:** `list[CustomerRead]`

---

### GET /commercial/customers/{id}
Get a single customer by ID.

**Response 200:** `CustomerRead`
**Response 404:** Customer not found in org.

---

### PATCH /commercial/customers/{id}
Partially update a customer. All fields optional.

**Response 200:** `CustomerRead`
**Response 400:** Duplicate code or invalid assigned user.
**Response 404:** Customer not found.

> Note: No frontend form for this endpoint in Sprint 1 (ADR-003 scope freeze).

---

## Interactions

### POST /commercial/customers/{id}/interactions
Log a new interaction for a customer.

**Required fields:** `interaction_type`, `interaction_date` (ISO 8601 with timezone), `subject`
**Optional fields:** `summary`, `outcome`, `next_step_hint`

**Response 201:** `CustomerInteractionRead`
**Response 404:** Customer not found.

---

### GET /commercial/customers/{id}/interactions
List all interactions for a customer (most recent first).

**Response 200:** `list[CustomerInteractionRead]`
**Response 404:** Customer not found.

---

## Follow-ups

### POST /commercial/customers/{id}/follow-ups
Create a follow-up task for a customer.

**Required fields:** `assigned_user_id`, `due_date` (ISO 8601 with timezone), `reason`
**Optional fields:** `interaction_id`, `priority`, `notes`

**Response 201:** `FollowUpRead`
**Response 400:** `assigned_user_id` not in same org, or `interaction_id` not on this customer.
**Response 404:** Customer not found.

---

### GET /commercial/customers/{id}/follow-ups
List follow-ups for a specific customer.

**Response 200:** `list[FollowUpRead]`

---

### GET /commercial/follow-ups
List all follow-ups in the caller's organization (all customers).

**Response 200:** `list[FollowUpRead]`

---

### PATCH /commercial/follow-ups/{id}/complete
Mark a follow-up as completed.

**Body (all optional):**
```json
{ "completed_at": "2026-06-08T10:00:00Z", "notes": "Done." }
```
If `completed_at` is omitted, the server uses the current UTC time.

**Response 200:** `FollowUpRead` with `status: "completed"`
**Response 404:** Follow-up not found in org.

---

## System

### GET /health
Health check. No auth required.

**Response 200:**
```json
{ "status": "healthy", "app": "IORP Backend", "environment": "development" }
```
