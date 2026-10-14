"""Shared contact field types and mechanical versioned persistence; modules own records and access rules."""
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, EmailStr
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException


class ContactInput(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    name:str=Field(min_length=1,max_length=200)
    phone:str|None=Field(None,max_length=30)
    email:EmailStr|None=None
    role:str|None=Field(None,max_length=120)
    active:bool=True
    is_default:bool=False
    version:int|None=Field(None,ge=1)


class SiteInput(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    name:str=Field(min_length=1,max_length=200)
    address:str=Field(min_length=1,max_length=1000)
    city:str|None=Field(None,max_length=120)
    location_url:str|None=Field(None,max_length=500,pattern=r'^https?://\S+$')
    contact_id:UUID|None=None
    active:bool=True
    is_default:bool=False
    version:int|None=Field(None,ge=1)


def view(row):return {c.name:getattr(row,c.name) for c in row.__table__.columns}


def save(db,tenant,model,parent_field,parent_id,data,record_id=None):
    # The owner locks/authorizes the parent first, including concurrent default selection.
    query=select(model).where(model.organization_id==tenant.organization_id,getattr(model,parent_field)==parent_id)
    values=data.model_dump(exclude={'version'})
    row=None
    if record_id:
        row=db.scalar(query.where(model.id==record_id).with_for_update().execution_options(populate_existing=True))
        if row is None:raise HTTPException(404,'DIRECTORY_RECORD_NOT_FOUND')
        if data.version!=row.version:raise HTTPException(409,'DIRECTORY_CHANGED')
    if values['is_default'] and not values['active']:raise HTTPException(422,'DEFAULT_MUST_BE_ACTIVE')
    if values['is_default']:
        for other in db.scalars(query.where(model.is_default.is_(True))):
            if not row or other.id!=row.id:
                other.is_default=False;other.version+=1;other.updated_by=tenant.user_id
    if row:
        for k,v in values.items():setattr(row,k,v)
        row.version+=1;row.updated_by=tenant.user_id
    else:
        row=model(**values,**{parent_field:parent_id},organization_id=tenant.organization_id,created_by=tenant.user_id,updated_by=tenant.user_id)
        db.add(row)
    from app.core.interfaces.audit_trail import record
    try:
        db.flush()
        record(db,tenant.organization_id,'directory.update' if record_id else 'directory.create',row.__tablename__,row.id,row.name,tenant.user_id,
            {'version':row.version,'active':row.active,'is_default':row.is_default})
        db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'DIRECTORY_DUPLICATE')
    return view(row)
