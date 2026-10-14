from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.core.interfaces.reference_lists import assert_reference_text
from app.masterdata.infrastructure.models import ListItem

@pytest.mark.parametrize('name',['downtime_reason','waste_reason','workforce_skill','test_method'])
def test_operational_catalog_is_tenant_scoped_and_preserves_old_text(db,test_org,name):
    row=ListItem(organization_id=test_org.id,list=name,key='original',name_ar='الأصل',name_en='Original',active=True,sort_order=1)
    db.add(row);db.commit()
    assert_reference_text(db,test_org.id,name,'Original')
    with pytest.raises(HTTPException) as exc:assert_reference_text(db,test_org.id,name,'Unknown')
    assert exc.value.status_code==422
    row.name_en='Renamed';row.active=False;db.commit()
    assert_reference_text(db,test_org.id,name,'Original','Original')
    with pytest.raises(HTTPException):assert_reference_text(db,test_org.id,name,'Renamed')
    # No catalog configured for another organization: legacy free text remains available there.
    assert_reference_text(db,uuid4(),name,'Legacy free text')
