def test_workforce_phone_normalized_on_create_and_update(client,db,test_user,auth_headers):
    test_user.is_organization_root=True;db.commit()
    root='/api/v1/workforce-members'
    response=client.post(root,json=dict(full_name='Phone test',worker_type='driver',employment_type='employee',phone='0551234567'),headers=auth_headers)
    assert response.status_code==201,response.text
    assert response.json()['phone']=='+966551234567'
    url=root+'/'+response.json()['id']
    changed=client.patch(url,json={'phone':'00971501234567'},headers=auth_headers)
    assert changed.status_code==200 and changed.json()['phone']=='+971501234567'
    bad=client.patch(url,json={'phone':'invalid'},headers=auth_headers)
    assert bad.status_code==422 and bad.json()['detail']=='PHONE_INVALID'
