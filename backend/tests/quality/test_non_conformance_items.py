CHECKS_BASE = "/api/v1/quality/quality-checks"
NCR_BASE = "/api/v1/quality/non-conformance-reports"
NCR_ITEMS_BASE = "/api/v1/quality/non-conformance-items"


def _base_quality_check(**overrides) -> dict:
    payload = {
        "check_datetime": "2026-07-02T10:00:00+00:00",
        "check_type": "finished_product_inspection",
        "qty_inspected": 10,
        "qty_accepted": 8,
        "qty_rejected": 2,
    }
    payload.update(overrides)
    return payload


def _base_report(**overrides) -> dict:
    payload = {
        "report_date": "2026-07-02",
        "source_type": "internal_production",
        "report_type": "product_non_conformance",
        "title": "Roll surface non-conformance",
        "description": "Surface marks found during final inspection.",
    }
    payload.update(overrides)
    return payload


def _base_item(**overrides) -> dict:
    payload = {
        "item_name": "Roll A",
        "quantity_affected": "12.50",
        "unit": "kg",
        "issue_description": "Visible surface marks across the roll.",
    }
    payload.update(overrides)
    return payload


def _create_quality_check(client, auth_headers, **overrides):
    resp = client.post(CHECKS_BASE, json=_base_quality_check(**overrides), headers=auth_headers)
    assert resp.status_code == 201
    return resp


def _create_report(client, auth_headers, **overrides):
    resp = client.post(NCR_BASE, json=_base_report(**overrides), headers=auth_headers)
    assert resp.status_code == 201
    return resp


def _create_item(client, auth_headers, report_id: str, **overrides):
    resp = client.post(
        f"{NCR_BASE}/{report_id}/items",
        json=_base_item(**overrides),
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp


def test_create_ncr_item_auto_line_no(client, auth_headers):
    report = _create_report(client, auth_headers)

    resp = client.post(
        f"{NCR_BASE}/{report.json()['id']}/items",
        json=_base_item(),
        headers=auth_headers,
    )

    assert resp.status_code == 201
    assert resp.json()["non_conformance_report_id"] == report.json()["id"]
    assert resp.json()["line_no"] == 1


def test_create_ncr_item_explicit_line_no(client, auth_headers):
    report = _create_report(client, auth_headers)

    resp = client.post(
        f"{NCR_BASE}/{report.json()['id']}/items",
        json=_base_item(line_no=5),
        headers=auth_headers,
    )

    assert resp.status_code == 201
    assert resp.json()["line_no"] == 5


def test_list_ncr_items_by_report(client, auth_headers):
    report = _create_report(client, auth_headers)
    first = _create_item(client, auth_headers, report.json()["id"])
    second = _create_item(client, auth_headers, report.json()["id"], item_name="Roll B")

    resp = client.get(f"{NCR_BASE}/{report.json()['id']}/items", headers=auth_headers)

    assert resp.status_code == 200
    assert [item["id"] for item in resp.json()] == [first.json()["id"], second.json()["id"]]


def test_update_ncr_item(client, auth_headers):
    report = _create_report(client, auth_headers)
    item = _create_item(client, auth_headers, report.json()["id"])

    resp = client.patch(
        f"{NCR_ITEMS_BASE}/{item.json()['id']}",
        json={"item_name": "Updated roll", "issue_description": "Updated issue description."},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    assert resp.json()["item_name"] == "Updated roll"


def test_cannot_create_item_when_report_closed(client, auth_headers):
    report = _create_report(client, auth_headers)
    close_resp = client.patch(
        f"{NCR_BASE}/{report.json()['id']}",
        json={"status": "closed"},
        headers=auth_headers,
    )
    assert close_resp.status_code == 200

    resp = client.post(
        f"{NCR_BASE}/{report.json()['id']}/items",
        json=_base_item(),
        headers=auth_headers,
    )

    assert resp.status_code == 400
