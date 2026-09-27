"""Focused test: delete work center with related data."""
from uuid import uuid4


def _create_wc(client, headers):
    r = client.post("/api/v1/production/work-centers", json={"name": "WC Delete Test", "center_type": "generic"}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _create_shift(client, headers, wc_id):
    r = client.post("/api/v1/production/shift-definitions", json={
        "name": "Morning",
        "shift_type": "custom", "code": "SD-TEST-001",
        "start_time": "08:00:00",
        "end_time": "16:00:00",
    }, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_delete_empty_work_center(client, auth_headers):
    wc_id = _create_wc(client, auth_headers)
    r = client.delete(f"/api/v1/production/work-centers/{wc_id}", headers=auth_headers)
    assert r.status_code == 204, f"Expected 204, got {r.status_code}: {r.text}"


def test_delete_work_center_with_shift(client, auth_headers):
    wc_id = _create_wc(client, auth_headers)
    _create_shift(client, auth_headers, wc_id)
    # verify summary
    r = client.get(f"/api/v1/production/work-centers/{wc_id}/delete-summary", headers=auth_headers)
    assert r.status_code == 200
    summary = r.json()
    print("Summary:", summary)
    # delete
    r = client.delete(f"/api/v1/production/work-centers/{wc_id}", headers=auth_headers)
    assert r.status_code == 204, f"Expected 204, got {r.status_code}: {r.text}"
    # verify gone
    r = client.get(f"/api/v1/production/work-centers/{wc_id}", headers=auth_headers)
    assert r.status_code == 404


def test_delete_work_center_not_found(client, auth_headers):
    r = client.delete(f"/api/v1/production/work-centers/{uuid4()}", headers=auth_headers)
    assert r.status_code == 404
