from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from app.foundation.infrastructure.models import User, TenantSecurityEvent
from app.foundation.infrastructure.permanent_deletion import reference_tables,delete_owned_rows,detach_personal_security


class UserDeletionConflict(ValueError):
    def __init__(self,code,tables=None):
        self.code=code;self.tables=tables or []
        super().__init__(code)


def eligibility_code(user,actor_id):
    if user.is_organization_root:return 'USER_DELETE_ROOT'
    if user.id==actor_id:return 'USER_DELETE_SELF'
    return None


def can_delete_permanently(db,user,actor_id):
    return deletion_block(db,user,actor_id) is None


def deletion_block(db,user,actor_id):
    code=eligibility_code(user,actor_id)
    if code:return {'code':code,'tables':[]}
    tables=reference_tables(db,user.id,user.organization_id)
    return {'code':'USER_DELETE_HAS_HISTORY','tables':tables} if tables else None


def delete_permanently(db,organization_id,user_id,actor,reason):
    try:
        user=db.scalar(select(User).where(User.id==user_id,User.organization_id==organization_id)
            .with_for_update().execution_options(populate_existing=True))
        if user is None:raise LookupError('User not found.')
        code=eligibility_code(user,actor.id)
        if code:raise UserDeletionConflict(code)
        tables=reference_tables(db,user.id,user.organization_id)
        if tables:raise UserDeletionConflict('USER_DELETE_HAS_HISTORY',tables)
        details={'email':user.email,'full_name':user.full_name,'reason':reason}
        detached=detach_personal_security(db,user)
        deleted=delete_owned_rows(db,user.id,organization_id)
        db.execute(delete(User.__table__).where(User.id==user.id,User.organization_id==organization_id))
        deleted['foundation_users']=1
        details.update(deleted_rows=sum(deleted.values()),detached_rows=sum(detached.values()),
            deleted_by_table=deleted,detached_by_table=detached)
        # Mandatory audit belongs to this transaction; do not use best-effort logging.
        db.add(TenantSecurityEvent(organization_id=organization_id,event_type='user.deleted_permanently',
            actor_id=actor.id,actor_email=actor.email,details=details))
        db.flush()
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise UserDeletionConflict('USER_DELETE_HAS_HISTORY') from exc
    except Exception:
        db.rollback();raise
