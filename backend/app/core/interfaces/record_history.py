"""Strict, transaction-local record history; modules own visibility and event selection."""
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID
from app.core.interfaces.activity_log import get_registered_activity_logger
from app.core.interfaces.user_directory import directory

_registry = {}
_secrets = ('password', 'token', 'secret', 'credential', 'recovery_code', 'authorization',
            'api_key', 'access_key', 'private_key', 'otp_code', 'mfa_code', 'pin_code', 'session_id')


def safe(value):
    if isinstance(value, dict):
        return {str(k): safe(v) for k, v in value.items() if not any(s in str(k).lower() for s in _secrets)}
    if isinstance(value, (list, tuple)):
        return [safe(v) for v in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (Decimal, UUID)):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def diff_fields(before, after, fields):
    changes = []
    for field in fields:
        if any(s in field.lower() for s in _secrets):
            continue
        old, new = before.get(field), after.get(field)
        # Specification keys are independent; ranges remain a min/max value.
        if '.' not in field and field.endswith('spec_json'):
            for key in sorted(set(old or {}) | set(new or {})):
                changes.extend(diff_fields({f'{field}.{key}': (old or {}).get(key)},
                                           {f'{field}.{key}': (new or {}).get(key)}, [f'{field}.{key}']))
        elif safe(old) != safe(new):
            changes.append(dict(field=field, old=safe(old), new=safe(new)))
    return changes


def record_event(db, org, entity_type, entity_id, entity_name, action, actor, changes=None, reason=None, related=None):
    actor_id = getattr(actor, 'user_id', None) or getattr(actor, 'id', None)
    actor_name = getattr(actor, 'full_name', None)
    if actor_id and not actor_name:
        actor_name = directory().names(db, org, [actor_id]).get(actor_id)
    details = safe(dict(schema_version=1, changes=changes or [], reason=reason, related=related or {}))
    # Filtering change field names as well prevents callers from putting secrets in old/new.
    details['changes'] = [c for c in details['changes'] if not any(s in c.get('field', '').lower() for s in _secrets)]
    try:
        get_registered_activity_logger().log_activity_strict(db, org, action, entity_type,
            entity_id=entity_id, entity_name=entity_name, actor_id=actor_id, actor_name=actor_name, details=details)
    except Exception:
        db.rollback()
        raise


def register_record_history(entity_type, permission, visible):
    _registry[entity_type] = (permission, visible)


def registered_record_types():
    return tuple(_registry)


def can_read(db, tenant, entity_type, entity_id, can):
    policy = _registry.get(entity_type)
    return bool(policy and can(policy[0]) and policy[1](db, tenant, entity_id))
