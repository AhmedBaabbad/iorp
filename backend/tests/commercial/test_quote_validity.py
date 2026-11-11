from datetime import datetime, timedelta, timezone
import pytest

from app.commercial.infrastructure.models import Quote, QuoteSettings
from tests.commercial.test_quotes import customer_id, _quote_payload  # noqa: F401


@pytest.mark.parametrize("days,accepted", [(-1, False), (0, True), (10, True), (11, False)])
def test_new_quote_respects_validity_policy(client, auth_headers, customer_id, days, accepted):
    issue = datetime(2026, 11, 1, tzinfo=timezone.utc)
    payload = _quote_payload(issue_date=issue.isoformat(), valid_until=(issue + timedelta(days=days)).isoformat())
    response = client.post(f"/api/v1/commercial/customers/{customer_id}/quotes", headers=auth_headers, json=payload)
    assert response.status_code == (201 if accepted else 400), response.text
    if not accepted:
        assert response.json()["detail"] == {"code": "QUOTE_VALIDITY_EXCEEDED", "quote_validity_days": 10}


def test_custom_policy_and_unchanged_legacy_dates(client, db, test_org, auth_headers, customer_id):
    db.add(QuoteSettings(organization_id=test_org.id, quote_validity_days=20)); db.commit()
    issue = datetime(2026, 11, 1, tzinfo=timezone.utc)
    payload = _quote_payload(issue_date=issue.isoformat(), valid_until=(issue + timedelta(days=20)).isoformat())
    response = client.post(f"/api/v1/commercial/customers/{customer_id}/quotes", headers=auth_headers, json=payload)
    assert response.status_code == 201, response.text
    from uuid import UUID
    quote = db.get(Quote, UUID(response.json()["id"]))
    quote.valid_until = issue + timedelta(days=30); db.commit()
    path = f"/api/v1/commercial/quotes/{quote.id}"
    assert client.patch(path, headers=auth_headers, json={"notes": "Keep original dates"}).status_code == 200
    assert client.patch(path, headers=auth_headers, json={"valid_until": quote.valid_until.isoformat()}).status_code == 200
    rejected = client.patch(path, headers=auth_headers, json={"valid_until": (issue + timedelta(days=31)).isoformat()})
    assert rejected.status_code == 400
    assert rejected.json()["detail"]["quote_validity_days"] == 20


def test_settings_default_range_and_editor_access(client, auth_headers):
    response = client.get("/api/v1/commercial/quote-settings/validity", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"quote_validity_days": 10}
    from app.commercial.api.quote_settings_schemas import QuoteSettingsUpdate
    from pydantic import ValidationError
    for days in [0, 366, 1.5]:
        with pytest.raises(ValidationError):
            QuoteSettingsUpdate(quote_validity_days=days)


def test_validity_policy_is_tenant_scoped(client, db, test_org, auth_headers):
    from app.foundation.infrastructure.models import Organization
    other = Organization(name="Other organization", code="other-validity")
    db.add(other); db.flush()
    db.add_all([QuoteSettings(organization_id=test_org.id, quote_validity_days=17, signature_title_ar="Private signature"),
                QuoteSettings(organization_id=other.id, quote_validity_days=29)])
    db.commit()
    response = client.get(f"/api/v1/commercial/quote-settings/validity?organization_id={other.id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"quote_validity_days": 17}
