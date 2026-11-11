"""ARCH-PAGE-001: quotations, sales orders, samples and a customer's interactions come in server pages, searched and
filtered by the query, each row with its customer's name (read once for the page)."""
import pytest

API = "/api/v1/commercial"


@pytest.fixture
def two_customers(client, auth_headers, with_owner):
    make = lambda code, name: client.post(f"{API}/customers", json=with_owner({"customer_code": code, "name": name}),
                                          headers=auth_headers).json()["id"]
    return make("C-1", "Gulf Packaging"), make("C-2", "Red Sea Foods")


def get(client, headers, path):
    r = client.get(f"{API}{path}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def quote(client, headers, customer, **extra):
    body = {"issue_date": "2026-06-09T10:00:00Z", "valid_until": "2026-06-19T10:00:00Z", "currency": "SAR",
            "items": [{"line_no": 1, "product_type": "pp_strap", "quantity": "10", "unit": "kg", "unit_price": "2"}], **extra}
    return client.post(f"{API}/customers/{customer}/quotes", json=body, headers=headers).json()


def test_quotes_are_paged_searched_and_named(client, auth_headers, two_customers):
    gulf, red = two_customers
    made = [quote(client, auth_headers, gulf) for _ in range(3)] + [quote(client, auth_headers, red)]
    first = get(client, auth_headers, "/quotes?page_size=2")
    assert (first["total"], first["pages"], len(first["items"])) == (4, 2, 2)
    seen = {q["id"] for p in (1, 2) for q in get(client, auth_headers, f"/quotes?page={p}&page_size=2")["items"]}
    assert seen == {q["id"] for q in made}
    by_customer = get(client, auth_headers, "/quotes?search=red sea")
    assert [q["customer_name"] for q in by_customer["items"]] == ["Red Sea Foods"] and by_customer["items"][0]["customer_code"].startswith("CUST-")
    assert get(client, auth_headers, f"/quotes?search={made[0]['quote_number']}")["total"] == 1
    client.post(f"{API}/quotes/{made[0]['id']}/issue", headers=auth_headers)
    assert [q["id"] for q in get(client, auth_headers, "/quotes?status=issued")["items"]] == [made[0]["id"]]
    assert get(client, auth_headers, f"/quotes?customer_id={gulf}")["total"] == 3


def test_orders_are_paged_and_carry_the_quote_number(client, auth_headers, two_customers):
    gulf, red = two_customers
    q = quote(client, auth_headers, gulf)
    client.post(f"{API}/quotes/{q['id']}/issue", headers=auth_headers)
    client.post(f"{API}/quotes/{q['id']}/accept", headers=auth_headers)
    client.post(f"{API}/quotes/{q['id']}/sales-order", headers=auth_headers)
    client.post(f"{API}/customers/{red}/orders", headers=auth_headers, json={"order_date": "2026-06-09T10:00:00Z", "customer_reference": "PO-7781",
                "items": [{"line_no": 1, "product_type": "pp_strap", "quantity": "5", "unit": "kg"}]})
    page = get(client, auth_headers, "/orders")
    assert page["total"] == 2 and {o["customer_name"] for o in page["items"]} == {"Gulf Packaging", "Red Sea Foods"}
    assert [o["quote_number"] for o in page["items"] if o["customer_name"] == "Gulf Packaging"] == [q["quote_number"]]
    assert [o["customer_reference"] for o in get(client, auth_headers, "/orders?search=7781")["items"]] == ["PO-7781"]
    assert get(client, auth_headers, "/orders?status=confirmed")["total"] == 0


def test_samples_are_paged_and_searched(client, db, test_org, test_user, auth_headers, two_customers):
    from app.masterdata.infrastructure.models import Product
    db.add(Product(organization_id=test_org.id, code="PRD-0001", key="pp_strap", name_ar="شريط", name_en="PP Strap",
                   created_by_user_id=test_user.id))
    db.commit()
    gulf, red = two_customers
    for customer in (gulf, gulf, red):
        assert client.post(f"{API}/customers/{customer}/samples", headers=auth_headers,
                           json={"product_type": "pp_strap", "request_date": "2026-06-09T10:00:00Z"}).status_code == 201
    page = get(client, auth_headers, "/samples?page_size=2")
    assert (page["total"], page["pages"], len(page["items"])) == (3, 2, 2) and page["items"][0]["customer_name"]
    assert get(client, auth_headers, "/samples?search=gulf")["total"] == 2
    assert get(client, auth_headers, f"/samples?customer_id={red}")["total"] == 1


def test_a_customers_interactions_are_paged_latest_first(client, auth_headers, two_customers):
    gulf, _ = two_customers
    for day in range(1, 6):
        r = client.post(f"{API}/customers/{gulf}/interactions", headers=auth_headers,
                        json={"interaction_type": "call", "interaction_date": f"2026-06-0{day}T10:00:00Z", "subject": f"Call {day}"})
        assert r.status_code == 201, r.text
    page = get(client, auth_headers, f"/customers/{gulf}/interactions?page_size=2")
    assert (page["total"], page["pages"]) == (5, 3) and [i["subject"] for i in page["items"]] == ["Call 5", "Call 4"]
    assert [i["subject"] for i in get(client, auth_headers, f"/customers/{gulf}/interactions?page=3&page_size=2")["items"]] == ["Call 1"]
