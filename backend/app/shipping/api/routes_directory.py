from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, or_
from sqlalchemy.exc import IntegrityError
from app.dependencies import get_db, get_current_tenant, require_permission, require_any_permission
from app.core.pagination import page_params, paginate, page_of
from app.core.db import Base
from app.shipping.application.directory_service import MODELS, validate

router=APIRouter(prefix='/shipping/directory',tags=['transport-directory'])
READ='shipping:directory:read'
WRITE='shipping:directory:write'
USE=[READ,WRITE,'shipping:shipments:create','shipping:shipments:update','shipping:shipments:reschedule','procurement:receipts:create','procurement:receipts:update']


class CarrierInput(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    name:str=Field(min_length=1,max_length=200)
    phone:str|None=Field(None,max_length=30)
    active:bool=True
    version:int|None=Field(None,ge=1)


class DriverInput(CarrierInput):
    affiliation:Literal['internal','external']
    workforce_member_id:UUID|None=None
    identity_no:str|None=Field(None,max_length=40)
    carrier_id:UUID|None=None


class VehicleInput(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    name:str=Field(min_length=1,max_length=200)
    plate:str=Field(min_length=1,max_length=40)
    vehicle_type:str|None=Field(None,max_length=80)
    carrier_id:UUID|None=None
    active:bool=True
    version:int|None=Field(None,ge=1)


SCHEMAS={'drivers':DriverInput,'vehicles':VehicleInput,'carriers':CarrierInput}


def model_for(kind):
    if kind not in MODELS:raise HTTPException(404,'DIRECTORY_UNKNOWN')
    return MODELS[kind]


@router.get('/workers',dependencies=[Depends(require_permission(WRITE))])
def workers(search:str=Query('',max_length=120),db=Depends(get_db),tenant=Depends(get_current_tenant)):
    t=Base.metadata.tables['workforce_members']
    return [dict(id=r.id,name=r.full_name) for r in db.execute(select(t.c.id,t.c.full_name).where(t.c.organization_id==tenant.organization_id,
        t.c.status=='active',t.c.full_name.icontains(search,autoescape=True)).order_by(t.c.full_name,t.c.id).limit(50))]


@router.get('/customers/{customer_id}/{kind}',dependencies=[Depends(require_any_permission(['shipping:shipments:create','shipping:shipments:update']))])
def customer_options(customer_id:UUID,kind:str,search:str=Query('',max_length=120),db=Depends(get_db),tenant=Depends(get_current_tenant)):
    from app.core.interfaces.customer_delivery import directory
    return directory().options(db,tenant.organization_id,customer_id,kind,search)


@router.get('/{kind}/options',dependencies=[Depends(require_any_permission(USE))])
def options(kind:str,search:str=Query('',max_length=120),db=Depends(get_db),tenant=Depends(get_current_tenant)):
    m=model_for(kind)
    match=m.name.icontains(search,autoescape=True)
    if kind=='vehicles':match=or_(match,m.plate.icontains(search,autoescape=True))
    rows=db.scalars(select(m).where(m.organization_id==tenant.organization_id,m.active.is_(True),match).order_by(m.name,m.id).limit(50))
    # Operational users see only the fields needed to identify their selection, not the directory's identity numbers.
    return [dict(id=r.id,name=r.name,**({'affiliation':r.affiliation} if kind=='drivers' else {'plate':r.plate} if kind=='vehicles' else {})) for r in rows]


@router.get('/{kind}',dependencies=[Depends(require_permission(READ))])
def listing(kind:str,search:str=Query('',max_length=120),params=Depends(page_params),db=Depends(get_db),tenant=Depends(get_current_tenant)):
    m=model_for(kind)
    rows,total=paginate(db,select(m).where(m.organization_id==tenant.organization_id,m.name.icontains(search,autoescape=True)).order_by(m.name,m.id),params)
    return page_of([view(r) for r in rows],total,params)


def view(row):return {c.name:getattr(row,c.name) for c in row.__table__.columns}


def save(kind,payload,db,tenant,record_id=None):
    from pydantic import ValidationError
    m=model_for(kind)
    try:data=SCHEMAS[kind].model_validate(payload)
    except ValidationError:raise HTTPException(422,'DIRECTORY_DATA_INVALID')
    values=data.model_dump(exclude={'version'})
    row=None
    if record_id:
        row=db.scalar(select(m).where(m.organization_id==tenant.organization_id,m.id==record_id).with_for_update().execution_options(populate_existing=True))
        if not row:raise HTTPException(404,'DIRECTORY_RECORD_NOT_FOUND')
        if data.version!=row.version:raise HTTPException(409,'DIRECTORY_CHANGED')
    values=validate(db,tenant.organization_id,kind,values,row)
    if row:
        for k,v in values.items():setattr(row,k,v)
        row.version+=1;row.updated_by=tenant.user_id
    else:
        row=m(**values,organization_id=tenant.organization_id,created_by=tenant.user_id,updated_by=tenant.user_id)
        db.add(row)
    from app.core.interfaces.audit_trail import record
    try:
        db.flush()
        record(db,tenant.organization_id,'directory.update' if record_id else 'directory.create',row.__tablename__,row.id,row.name,tenant.user_id,
            {'version':row.version,'active':row.active})
        db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'DIRECTORY_DUPLICATE')
    return view(row)


@router.post('/{kind}',status_code=201,dependencies=[Depends(require_permission(WRITE))])
def create(kind:str,payload:dict,db=Depends(get_db),tenant=Depends(get_current_tenant)):
    return save(kind,payload,db,tenant)


@router.put('/{kind}/{record_id}',dependencies=[Depends(require_permission(WRITE))])
def update(kind:str,record_id:UUID,payload:dict,db=Depends(get_db),tenant=Depends(get_current_tenant)):
    return save(kind,payload,db,tenant,record_id)
