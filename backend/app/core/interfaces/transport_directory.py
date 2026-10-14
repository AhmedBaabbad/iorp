"""Shipping owns reusable transport data. Consumers receive snapshots, never ORM records."""
from typing import Protocol


class TransportDirectory(Protocol):
    def resolve(self, db, org, kind, record_id) -> dict: ...
    def uses_worker(self,db,org,worker_id) -> bool: ...


_provider: TransportDirectory | None = None


def register_transport_directory(provider: TransportDirectory):
    global _provider
    _provider=provider


def resolve(db, org, kind, record_id):
    if _provider is None:
        raise RuntimeError('Transport directory unavailable')
    return _provider.resolve(db,org,kind,record_id)


def worker_referenced(db,org,worker_id):
    return _provider.uses_worker(db,org,worker_id) if _provider else False


def apply_transport(db, org, record, values):
    """Copy only on a new selection; unrelated edits never refresh saved historical data."""
    maps={'driver':{'name':'driver_name','phone':'driver_phone','identity_no':'driver_id_no','affiliation':'driver_affiliation'},
          'vehicle':{'plate':'vehicle_plate','vehicle_type':'vehicle_type'},'carrier':{'name':'carrier_name'}}
    result=dict(values)
    for kind,fields in maps.items():
        key=kind+'_id'
        previous=getattr(record,key,None)
        selected=result.get(key,previous)
        if key not in result and not previous:
            continue
        if selected:
            if selected!=previous:
                source=resolve(db,org,kind,selected)
                result.update({target:source.get(field) for field,target in fields.items() if hasattr(record,target)})
            else:
                # A selected record's snapshot cannot be silently forged in a full-form PATCH.
                result.update({target:getattr(record,target) for target in fields.values() if hasattr(record,target)})
        elif previous:
            for target in fields.values():
                if hasattr(record,target):
                    result.setdefault(target,None)
    name=result.get('driver_name',getattr(record,'driver_name',None))
    affiliation=result.get('driver_affiliation',getattr(record,'driver_affiliation',None))
    changed=name!=getattr(record,'driver_name',None) or 'driver_affiliation' in result
    if name and changed and affiliation not in ('internal','external'):
        # An untouched legacy row may remain unspecified; new/replaced drivers cannot.
        legacy_unchanged=(name==getattr(record,'driver_name',None) and not getattr(record,'driver_affiliation',None))
        if not legacy_unchanged:
            from fastapi import HTTPException
            raise HTTPException(422,'DRIVER_AFFILIATION_REQUIRED')
    return result
