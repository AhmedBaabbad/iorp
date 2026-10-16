"""Access errors must survive get_db's generator context-manager cleanup on Python 3.12."""
import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_db
from app.foundation.domain.enums import OrganizationStatus, UserStatus
from app.main import app


@pytest.mark.parametrize(
    "target,status,code,message",
    [
        ("user", UserStatus.LOCKED, "ACCOUNT_LOCKED",
         "Your account has been locked. Contact your administrator."),
        ("organization", OrganizationStatus.SUSPENDED, "ORGANIZATION_SUSPENDED",
         "Your organization has been suspended. Contact your administrator."),
    ],
    ids=["account_access_locked", "organization_access_suspended"],
)
def test_access_error_through_yield_dependency(
    client, auth_headers, db, test_user, test_org, target, status, code, message,
):
    # Authenticate while active, then deny an existing session through the real
    # get_current_user dependency and the application's production error handlers.
    entity = test_user if target == "user" else test_org
    entity.status = status
    db.commit()
    propagated = []
    previous = app.dependency_overrides[get_db]

    def yielding_db():
        try:
            yield db
        except Exception as exc:
            propagated.append(exc)
            raise

    app.dependency_overrides[get_db] = yielding_db
    try:
        # Return actual 500 responses rather than re-raising server exceptions.
        with TestClient(app, raise_server_exceptions=False) as request_client:
            response = request_client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 403, response.text
        assert response.json() == {"code": code, "message": message}
        assert len(propagated) == 1
        assert propagated[0].code == code
    finally:
        app.dependency_overrides[get_db] = previous
