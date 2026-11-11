import pytest

from app.core.password_policy import PASSWORD_MIN_LENGTH, PasswordPolicyError, validate_password


@pytest.mark.parametrize("password,confirmation,email,code", [
    ("Ab1!", "Ab1!", "x@example.test", "PASSWORD_TOO_SHORT"),
    ("ABCDEFG1!", "ABCDEFG1!", "x@example.test", "PASSWORD_NEEDS_LOWER"),
    ("abcdefg1!", "abcdefg1!", "x@example.test", "PASSWORD_NEEDS_UPPER"),
    ("Abcdefg!!", "Abcdefg!!", "x@example.test", "PASSWORD_NEEDS_DIGIT"),
    ("Abcdefg12", "Abcdefg12", "x@example.test", "PASSWORD_NEEDS_SYMBOL"),
    ("Abcd123!", "different", "x@example.test", "PASSWORD_MISMATCH"),
    ("Test1@Email.test", "Test1@Email.test", "test1@email.test", "PASSWORD_EQUALS_EMAIL"),
])
def test_password_policy_reports_specific_codes(password, confirmation, email, code):
    with pytest.raises(PasswordPolicyError) as caught:
        validate_password(password, confirmation, email)
    assert caught.value.code == code


def test_eight_characters_are_sufficient_for_all_accounts():
    assert PASSWORD_MIN_LENGTH == 8
    validate_password("Abcd123!", "Abcd123!", "x@example.test")


@pytest.mark.parametrize("platform", [False, True])
@pytest.mark.parametrize("password,code", [
    ("Ab1!", "PASSWORD_TOO_SHORT"), ("ABCDEFG1!", "PASSWORD_NEEDS_LOWER"),
    ("abcdefg1!", "PASSWORD_NEEDS_UPPER"), ("Abcdefg!!", "PASSWORD_NEEDS_DIGIT"),
    ("Abcdefg12", "PASSWORD_NEEDS_SYMBOL"), ("email", "PASSWORD_EQUALS_EMAIL"),
    ("Abcd123!", "PASSWORD_MISMATCH"),
])
def test_reset_api_returns_policy_code(client, db, platform, password, code):
    from tests.test_password_reset import _seed
    from app.core.token_utils import hash_token, get_reset_expiry_time
    from app.foundation.infrastructure.models import TenantPasswordResetToken
    from app.platform.infrastructure.models import PlatformPasswordResetToken
    _, user, account = _seed(db)
    raw = "policy-test-token-with-more-than-32-characters"
    record = PlatformPasswordResetToken(account_id=account.id, token_hash=hash_token(raw), expires_at=get_reset_expiry_time()) if platform else TenantPasswordResetToken(user_id=user.id, organization_id=user.organization_id, token_hash=hash_token(raw), expires_at=get_reset_expiry_time())
    db.add(record); db.commit()
    if code == "PASSWORD_EQUALS_EMAIL":
        password = account.email if platform else user.email
    response = client.post("/api/v1/" + ("platform/" if platform else "") + "auth/reset-password", json={
        "token": raw, "new_password": password,
        "new_password_confirmation": "different" if code == "PASSWORD_MISMATCH" else password,
    })
    assert response.status_code == 400
    assert response.json()["code"] == code
