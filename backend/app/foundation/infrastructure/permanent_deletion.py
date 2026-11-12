"""Fail-closed reference inventory: metadata only, no other module's models.

Exemptions are owner rows, not entire tables: assigning somebody else's role
remains history, even though the user's own role bindings are disposable.
"""
from sqlalchemy import and_, delete, or_, select
from app.core.db import Base

SELF_OWNED = {
    'foundation_user_roles':'user_id',
    'foundation_password_reset_tokens':'user_id',
    'foundation_user_email_changes':'user_id',
}
SELF_SESSION_TABLE = 'core_auth_sessions'  # polymorphic account_id, no tenant-user FK
EXTRA_HISTORY = {
    'foundation_audit_log':('actor_id',),
    'foundation_role_assignment_removals':('user_id',),
    'notifications_items':('actor_user_id',),
}


def reference_tables(db,user_id,organization_id,limit=5):
    found=[]
    for table in sorted(Base.metadata.tables.values(),key=lambda t:t.name):
        columns={fk.parent.name for fk in table.foreign_keys if fk.target_fullname=='foundation_users.id'}
        columns.update(EXTRA_HISTORY.get(table.name,()))
        if not columns:continue
        condition=or_(*(table.c[column]==user_id for column in sorted(columns)))
        owner=SELF_OWNED.get(table.name)
        if owner:
            not_owned=or_(table.c[owner].is_(None),table.c[owner]!=user_id)
            if 'organization_id' in table.c:
                not_owned=or_(not_owned,table.c.organization_id.is_(None),table.c.organization_id!=organization_id)
            condition=and_(condition,not_owned)
        # No organization filter: even a corrupt cross-tenant reference must block deletion.
        if db.scalar(select(1).select_from(table).where(condition).limit(1)):
            found.append(table.name)
            if len(found)==limit:break
    return found


def delete_owned_rows(db,user_id,organization_id):
    for name,owner in SELF_OWNED.items():
        table=Base.metadata.tables[name]
        scope=table.c[owner]==user_id
        if 'organization_id' in table.c:scope=and_(scope,table.c.organization_id==organization_id)
        db.execute(delete(table).where(scope))
    table=Base.metadata.tables[SELF_SESSION_TABLE]
    db.execute(delete(table).where(table.c.account_type=='tenant',table.c.account_id==user_id,
        table.c.organization_id==organization_id))
