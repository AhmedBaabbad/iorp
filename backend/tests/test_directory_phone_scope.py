import pytest
from app.foundation.api.schemas import UserProfileUpdate
from app.foundation.api.branding_schemas import BrandingUpdate
from app.foundation.infrastructure.models import User
from app.foundation.infrastructure.branding_models import OrganizationBranding


@pytest.mark.parametrize('schema,model,limit',[
    (UserProfileUpdate,User,50),
    (BrandingUpdate,OrganizationBranding,60),
])
def test_user_and_branding_phone_capacity_and_free_text_are_preserved(schema,model,limit):
    value=('0551234567 / 0111234567 '*3)[:limit]
    assert len(value)==limit
    assert schema(phone=value).phone==value
    assert model.__table__.c.phone.type.length==limit
    from pydantic import ValidationError
    with pytest.raises(ValidationError):schema(phone=value+'1')
