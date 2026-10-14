from sqlalchemy import select
from fastapi import HTTPException
from app.core.db import Base
from app.core.interfaces.reference_lists import unknown_list_values
from app.shipping.infrastructure.directory_models import Driver, Vehicle, Carrier

MODELS={'drivers':Driver,'vehicles':Vehicle,'carriers':Carrier}


class TransportProvider:
    def uses_worker(self,db,org,worker_id):
        return db.scalar(select(Driver.id).where(Driver.organization_id==org,Driver.workforce_member_id==worker_id).limit(1)) is not None

    def resolve(self,db,org,kind,record_id):
        model=MODELS[kind+'s']
        row=db.scalar(select(model).where(model.organization_id==org,model.id==record_id,model.active.is_(True)))
        if row is None:
            raise HTTPException(422,'TRANSPORT_RECORD_UNAVAILABLE')
        if kind=='driver' and row.affiliation=='internal':
            table=Base.metadata.tables['workforce_members']
            if not db.scalar(select(table.c.id).where(table.c.id==row.workforce_member_id,table.c.organization_id==org,table.c.status=='active')):
                raise HTTPException(422,'TRANSPORT_RECORD_UNAVAILABLE')
        return {column.name:getattr(row,column.name) for column in model.__table__.columns}


def validate(db,org,kind,values,previous=None):
    if values.get('carrier_id'):
        query=select(Carrier.id).where(Carrier.organization_id==org,Carrier.id==values['carrier_id'])
        if values.get('active',True):query=query.where(Carrier.active.is_(True))
        if not db.scalar(query):raise HTTPException(422,'TRANSPORT_RECORD_UNAVAILABLE')
    if kind=='drivers':
        worker=values.get('workforce_member_id')
        if values['affiliation']=='internal':
            table=Base.metadata.tables['workforce_members']
            query=select(table).where(table.c.organization_id==org,table.c.id==worker)
            if values.get('active',True):
                query=query.where(table.c.status=='active')
            member=db.execute(query.with_for_update()).mappings().first() if worker else None
            if not member:
                raise HTTPException(422,'ACTIVE_WORKER_REQUIRED')
            values['name']=member['full_name']
            values['phone']=member['phone']
        elif worker:
            raise HTTPException(422,'EXTERNAL_DRIVER_CANNOT_REFERENCE_EMPLOYEE')
    if kind=='vehicles':
        values['plate']=' '.join(values['plate'].upper().split())
        # MD-003: the type is chosen from the organization's vehicle types; the one a vehicle already has may stay.
        kept=[previous.vehicle_type] if previous is not None and previous.vehicle_type else []
        if values.get('vehicle_type') and unknown_list_values(db,org,'vehicle_type',[values['vehicle_type']],kept):
            raise HTTPException(422,'REFERENCE_VALUE_UNAVAILABLE')
    return values
