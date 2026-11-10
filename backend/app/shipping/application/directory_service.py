from sqlalchemy import select, or_, text
from fastapi import HTTPException
from email_validator import validate_email, EmailNotValidError
from app.core.interfaces.reference_lists import unknown_list_values
from app.core.interfaces.workforce_directory import directory as workforce
from app.shipping.infrastructure.directory_models import Driver, Vehicle, Carrier

MODELS = {'drivers': Driver, 'vehicles': Vehicle, 'carriers': Carrier}
PERSONAL = ('name', 'phone', 'email', 'identity_no')


def view(db, org, row):
    result = {c.name: getattr(row, c.name) for c in row.__table__.columns}
    if isinstance(row, Driver) and row.affiliation == 'internal':
        member = workforce().member(db, org, row.workforce_member_id)
        result.update({key: member.get(key) if member else ('—' if key == 'name' else None) for key in PERSONAL})
    return result


def lock_identity(db, org, identity):
    # Serialize application-level identities shared by external drivers and workforce-owned internal drivers.
    if identity and db.get_bind().dialect.name == 'postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:identity, 0))'),
                   {'identity': str(org) + ':' + identity})


def duplicate_identity(db, org, identity, record_id=None):
    if not identity:
        return None
    query = select(Driver).where(Driver.organization_id == org,
        or_(Driver.identity_no == identity, Driver.affiliation == 'internal'))
    if record_id:
        query = query.where(Driver.id != record_id)
    for row in db.scalars(query):
        if view(db, org, row)['identity_no'] == identity:
            return row.id
    return None


def identity_conflict(existing):
    raise HTTPException(409, {'code': 'DRIVER_IDENTITY_EXISTS', 'existing_driver_id': str(existing)})


class TransportProvider:
    def validate_worker_identity(self, db, org, worker_id, identity):
        row = db.scalar(select(Driver).where(Driver.organization_id == org, Driver.workforce_member_id == worker_id))
        if row and identity:
            lock_identity(db, org, identity)
            existing = duplicate_identity(db, org, identity, row.id)
            if existing:
                identity_conflict(existing)

    def uses_worker(self, db, org, worker_id):
        return db.scalar(select(Driver.id).where(Driver.organization_id == org,
            Driver.workforce_member_id == worker_id).limit(1)) is not None

    def resolve(self, db, org, kind, record_id):
        model = MODELS[kind + 's']
        row = db.scalar(select(model).where(model.organization_id == org, model.id == record_id, model.active.is_(True)))
        if row is None:
            raise HTTPException(422, 'TRANSPORT_RECORD_UNAVAILABLE')
        if kind == 'driver' and row.affiliation == 'internal':
            if not workforce().member(db, org, row.workforce_member_id, active_only=True):
                raise HTTPException(422, 'TRANSPORT_RECORD_UNAVAILABLE')
        return view(db, org, row)


def validate(db, org, kind, values, previous=None):
    if values.get('carrier_id'):
        query = select(Carrier.id).where(Carrier.organization_id == org, Carrier.id == values['carrier_id'])
        if values.get('active', True):
            query = query.where(Carrier.active.is_(True))
        if not db.scalar(query):
            raise HTTPException(422, 'TRANSPORT_RECORD_UNAVAILABLE')
    if kind == 'drivers':
        worker = values.get('workforce_member_id')
        if values['affiliation'] == 'internal':
            member = workforce().member(db, org, worker, active_only=values.get('active', True), lock=True) if worker else None
            if not member:
                raise HTTPException(422, 'ACTIVE_WORKER_REQUIRED')
            values.update({key: member[key] for key in PERSONAL})
        else:
            if worker:
                raise HTTPException(422, 'EXTERNAL_DRIVER_CANNOT_REFERENCE_EMPLOYEE')
            values['identity_no'] = (values.get('identity_no') or '').strip() or None
            if not values['identity_no'] and (previous is None or previous.affiliation != 'external' or previous.identity_no):
                raise HTTPException(422, 'DRIVER_IDENTITY_REQUIRED')
            if not (values.get('name') or '').strip():
                raise HTTPException(422, 'DIRECTORY_DATA_INVALID')
        if values.get('email'):
            try:
                values['email'] = validate_email(values['email'], check_deliverability=False).normalized
            except EmailNotValidError as exc:
                raise HTTPException(422, 'DRIVER_EMAIL_INVALID') from exc
        if values.get('default_vehicle_id'):
            if not db.scalar(select(Vehicle.id).where(Vehicle.organization_id == org,
                    Vehicle.id == values['default_vehicle_id'], Vehicle.active.is_(True))):
                raise HTTPException(422, 'TRANSPORT_RECORD_UNAVAILABLE')
        lock_identity(db, org, values.get('identity_no'))
        existing = duplicate_identity(db, org, values.get('identity_no'), previous.id if previous else None)
        if existing:
            identity_conflict(existing)
    if kind in ('vehicles', 'drivers'):
        if kind == 'vehicles':
            values['plate'] = ' '.join(values['plate'].upper().split())
        kept = [previous.vehicle_type] if previous is not None and previous.vehicle_type else []
        if values.get('vehicle_type') and unknown_list_values(db, org, 'vehicle_type', [values['vehicle_type']], kept):
            raise HTTPException(422, 'REFERENCE_VALUE_UNAVAILABLE')
    return values
