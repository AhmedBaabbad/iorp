from uuid import uuid4
from app.workforce.infrastructure.models import WorkforceMember


def test_national_id_trim_uniqueness_update_and_list_privacy(client, db, test_user, auth_headers):
    test_user.is_organization_root = True
    db.commit()
    path = '/api/v1/workforce-members'
    body = dict(full_name='Employee driver', worker_type='driver', employment_type='employee', national_id='  NATIONAL-1  ')
    first = client.post(path, json=body, headers=auth_headers)
    assert first.status_code == 201, first.text
    assert first.json()['national_id'] == 'NATIONAL-1'
    conflict = client.post(path, json=body, headers=auth_headers)
    assert conflict.status_code == 409 and conflict.json()['detail'] == 'WORKFORCE_NATIONAL_ID_EXISTS'
    second = client.post(path, json={**body, 'national_id': None}, headers=auth_headers).json()
    update = client.patch(path + '/' + second['id'], json={'national_id': ' NATIONAL-1 '}, headers=auth_headers)
    assert update.status_code == 409
    assert 'national_id' not in client.get(path, headers=auth_headers).json()[0]
    assert client.patch(path + '/' + first.json()['id'], json={'national_id': ' '}, headers=auth_headers).json()['national_id'] is None
    # A matching national identity in another organization is unrelated.
    db.add(WorkforceMember(organization_id=uuid4(), employee_code='OTHER', full_name='Other', worker_type='driver',
                          employment_type='employee', national_id='NATIONAL-1'))
    db.commit()
    assert client.post(path, json=body, headers=auth_headers).status_code == 201
