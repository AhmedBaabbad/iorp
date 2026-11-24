"""Black-box contract shared by legacy-array endpoints that opt into ADR-006."""
from uuid import uuid4

from app.core.tenancy import TenantContext


def assert_paged_contract(client, path, *, headers=None, search=None, search_key="search", ctx=None, scoped=False):
    legacy = client.get(path, headers=headers)
    assert legacy.status_code == 200, legacy.text
    rows = legacy.json()
    assert isinstance(rows, list) and len(rows) >= 2
    seen = []
    for number in range(1, len(rows) + 1):
        response = client.get(path, headers=headers, params={"page": number, "page_size": 1})
        assert response.status_code == 200, response.text
        page = response.json()
        assert (page["total"], page["pages"], page["page"], page["page_size"]) == (len(rows), len(rows), number, 1)
        assert len(page["items"]) == 1
        seen.append(page["items"][0])
    # Stable order, no duplication, and identical enrichment in both contracts.
    assert seen == rows
    outside = client.get(path, headers=headers, params={"page": len(rows) + 1, "page_size": 1}).json()
    assert outside["items"] == [] and outside["total"] == len(rows)
    default = client.get(path, headers=headers, params={"page": 1}).json()
    assert default["page_size"] == 50
    empty = client.get(path, headers=headers, params={"page": 1, search_key: "no-match"}).json()
    assert empty["items"] == [] and empty["total"] == empty["pages"] == 0
    if search:
        matching = client.get(path, headers=headers, params={search_key: search}).json()
        paged = client.get(path, headers=headers, params={search_key: search, "page": 1, "page_size": 1}).json()
        assert matching and paged["total"] == len(matching)
        assert paged["items"] == matching[:1]
    for params in ({"page": 0}, {"page_size": 101}, {"page_size": 0}):
        assert client.get(path, headers=headers, params=params).status_code == 422
    if ctx is not None:
        original = ctx.tenant
        ctx.tenant = TenantContext(original.user_id, uuid4(), permissions=original.permissions)
        try:
            other = client.get(path, params={"page": 1, "page_size": 1})
            if scoped:
                assert other.status_code == 404
            else:
                assert other.status_code == 200, other.text
                assert other.json()["total"] == 0 and other.json()["items"] == []
        finally:
            ctx.tenant = original
