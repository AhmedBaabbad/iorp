from app.masterdata.domain import lists as L
from app.masterdata.domain.geography import ARAB_COUNTRIES, country_sort_key
from app.masterdata.application.list_service import seed_standard_lists, ListService
from app.masterdata.infrastructure.models import ListItem
from app.core.tenancy import TenantContext


def test_world_and_arab_city_catalogue_preserves_saudi_keys():
    countries, cities = L.STANDARD[L.COUNTRY], L.STANDARD[L.CITY]
    assert len(countries) == len({row[0] for row in countries}) == 249
    assert tuple(row[0] for row in countries[:22]) == ARAB_COUNTRIES
    assert list(countries) == sorted(countries, key=lambda row: country_sort_key(row[0], row[2]))
    assert len(cities) == len({row[0] for row in cities}) == 357
    assert {row[0] for row in cities if row[0].endswith('_other')} == {row[0] + '_other' for row in countries}
    assert {'riyadh', 'jeddah', 'makkah', 'madinah', 'dammam', 'khobar', 'abha', 'arar'} <= {row[0] for row in cities}
    assert all(row[3] in ARAB_COUNTRIES for row in cities if not row[0].endswith('_other'))
    assert all(row[0].startswith(row[3] + '_') for row in cities if row[3] != 'sa')


def test_existing_organization_seed_is_additive_and_idempotent(db, test_org, test_user):
    sa = ListItem(organization_id=test_org.id, list='country', key='sa', name_ar='اسم مخصص', name_en='Custom Saudi', active=False, sort_order=99)
    cn = ListItem(organization_id=test_org.id, list='country', key='cn', name_ar='الصين', name_en='China', sort_order=1)
    custom = ListItem(organization_id=test_org.id, list='city', key='my_city', name_ar='مدينتي', name_en='My city', parent_key='sa', active=False)
    db.add_all([sa, cn, custom]); db.commit()
    identities = (sa.id, custom.id)
    assert seed_standard_lists(db, test_org.id) > 0
    db.commit()
    assert seed_standard_lists(db, test_org.id) == 0
    assert (sa.id, custom.id) == identities
    assert sa.name_en == 'Custom Saudi' and not sa.active and sa.sort_order == 99
    assert not custom.active and custom.name_en == 'My city'
    displayed = ListService(db, TenantContext(test_user.id, test_org.id)).items('country')
    assert [row.key for row in displayed[:22]] == list(ARAB_COUNTRIES)
