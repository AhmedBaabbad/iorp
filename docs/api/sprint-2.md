# API Reference — Sprint 2

Base URL: `http://localhost:8000/api/v1`

All protected routes require `Authorization: Bearer <token>`.
Interactive docs: `http://localhost:8000/docs`

Sprint 1 endpoints (auth, customers, interactions, follow-ups): see [sprint-1.md](sprint-1.md).

---

## Samples

All sample routes are scoped to the caller's organization via tenant context.

### POST /commercial/customers/{id}/samples
Create a new sample for a customer.

**Required fields:** `sample_code`, `product_type`, `request_date` (ISO 8601 with timezone)
**Optional fields:** `requested_spec_json`, `quantity_requested`, `unit`, `notes`

**Response 201:** `SampleRead`
**Response 400:** Duplicate `sample_code` for this customer.
**Response 404:** Customer not found.

---

### GET /commercial/samples
List all samples in the caller's organization.

**Response 200:** `list[SampleListItem]`

---

### GET /commercial/customers/{id}/samples
List all samples for a specific customer.

**Response 200:** `list[SampleListItem]`
**Response 404:** Customer not found.

---

### GET /commercial/samples/{id}
Get a single sample by ID.

**Response 200:** `SampleRead`
**Response 404:** Sample not found.

---

### PATCH /commercial/samples/{id}
Partially update a sample. All fields optional.

**Response 200:** `SampleRead`
**Response 400:** Duplicate code for this customer, or attempt to set status to `evaluated` directly.
**Response 404:** Sample not found.

> Note: To transition a sample to `evaluated`, create a `SampleEvaluation` — setting `status: "evaluated"` via this endpoint is rejected.

---

## Sample Evaluations

### POST /commercial/samples/{id}/evaluations
Create an evaluation for a sample. Auto-transitions the sample status to `evaluated`.

**Required fields:** `evaluation_date` (ISO 8601 with timezone), `result_status`, `next_action`
**Optional fields:** `comments`

Valid `result_status` values: `accepted`, `rejected`, `needs_modification`
Valid `next_action` values: `proceed_to_quote`, `revise_sample`, `close_request`, `further_review`

**Body example:**
```json
{
  "evaluation_date": "2026-06-08T10:00:00Z",
  "result_status": "accepted",
  "comments": "Meets structural grade requirements.",
  "next_action": "proceed_to_quote"
}
```

**Response 201:** `SampleEvaluationRead`
**Response 400:** Sample is cancelled.
**Response 404:** Sample not found.

---

### GET /commercial/samples/{id}/evaluations
List all evaluations for a sample.

**Response 200:** `list[SampleEvaluationRead]`
**Response 404:** Sample not found.

---

### GET /commercial/sample-evaluations/{id}
Get a single sample evaluation by ID.

**Response 200:** `SampleEvaluationRead`
**Response 404:** Evaluation not found.

---

## Quotes

### POST /commercial/customers/{id}/quotes
Create a new quote for a customer. `subtotal_amount` and `total_amount` are calculated server-side.

**Required fields:** `quote_number`, `issue_date`, `valid_until`, `items` (min 1 item)
**Optional fields:** `sample_id`, `currency` (default `SAR`), `discount_amount` (default `0`), `tax_amount` (default `0`), `notes`

**Item required fields:** `line_no`, `product_type`, `quantity`, `unit`, `unit_price`
**Item optional fields:** `requested_spec_json`

**Body example:**
```json
{
  "quote_number": "Q-2026-001",
  "issue_date": "2026-06-08T00:00:00Z",
  "valid_until": "2026-07-08T00:00:00Z",
  "currency": "SAR",
  "discount_amount": "60.00",
  "tax_amount": "0.00",
  "notes": "Based on approved sample SAMP-001.",
  "items": [
    { "line_no": 1, "product_type": "Steel Rod", "quantity": "500.00", "unit": "kg", "unit_price": "4.50" },
    { "line_no": 2, "product_type": "Rebar",     "quantity": "200.00", "unit": "kg", "unit_price": "3.80" }
  ]
}
```

**Response 201:** `QuoteRead` (includes `subtotal_amount`, `total_amount`, `items`)
**Response 400:** Duplicate `quote_number`, linked `sample_id` not belonging to this customer, or negative total.
**Response 404:** Customer not found.

---

### GET /commercial/quotes
List all quotes in the caller's organization.

**Response 200:** `list[QuoteListItem]`

---

### GET /commercial/customers/{id}/quotes
List all quotes for a specific customer.

**Response 200:** `list[QuoteListItem]`
**Response 404:** Customer not found.

---

### GET /commercial/quotes/{id}
Get a single quote by ID, including all line items.

**Response 200:** `QuoteRead`
**Response 404:** Quote not found.

---

### PATCH /commercial/quotes/{id}
Partially update a quote. All fields optional. If `items` is provided, it replaces all existing items and recalculates totals.

**Response 200:** `QuoteRead`
**Response 400:** Duplicate number, invalid sample, or negative total.
**Response 404:** Quote not found.

---

## Orders

### POST /commercial/customers/{id}/orders
Create a new commercial order for a customer.

**Required fields:** `order_number`, `order_date`, `items` (min 1 item)
**Optional fields:** `quote_id`, `requested_delivery_date`, `notes`

**Item required fields:** `line_no`, `product_type`, `quantity`, `unit`
**Item optional fields:** `agreed_unit_price`, `requested_spec_json`

**Body example:**
```json
{
  "order_number": "ORD-2026-001",
  "order_date": "2026-06-09T00:00:00Z",
  "quote_id": "<uuid>",
  "requested_delivery_date": "2026-06-23T00:00:00Z",
  "notes": "Confirmed based on Q-2026-001.",
  "items": [
    { "line_no": 1, "product_type": "Steel Rod", "quantity": "500.00", "unit": "kg", "agreed_unit_price": "4.50" },
    { "line_no": 2, "product_type": "Rebar",     "quantity": "200.00", "unit": "kg", "agreed_unit_price": "3.80" }
  ]
}
```

**Response 201:** `CommercialOrderRead` (includes `items`)
**Response 400:** Duplicate `order_number`; linked quote not belonging to this customer; or linked quote not in `issued` or `accepted` status.
**Response 404:** Customer not found.

---

### GET /commercial/orders
List all orders in the caller's organization.

**Response 200:** `list[CommercialOrderListItem]`

---

### GET /commercial/customers/{id}/orders
List all orders for a specific customer.

**Response 200:** `list[CommercialOrderListItem]`
**Response 404:** Customer not found.

---

### GET /commercial/orders/{id}
Get a single order by ID, including all line items.

**Response 200:** `CommercialOrderRead`
**Response 404:** Order not found.

---

### PATCH /commercial/orders/{id}
Partially update an order. All fields optional. If `items` is provided, it replaces all existing items.

**Response 200:** `CommercialOrderRead`
**Response 400:** Duplicate number, or invalid/wrong-status quote.
**Response 404:** Order not found.
