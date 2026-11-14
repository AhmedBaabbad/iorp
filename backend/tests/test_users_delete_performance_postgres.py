"""Real JSONB predicate parity, bulk detachment and reversible index migration."""
import importlib.util
import os
from pathlib import Path
from uuid import uuid4
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.core.db import Base, engine
from app.main import app  # noqa: F401
from app.foundation.infrastructure.models import Organization, User, TenantSecurityEvent
from app.foundation.infrastructure.permanent_deletion import personal_security_condition, detach_personal_security

pytestmark = pytest.mark.skipif(os.environ.get('RUN_POSTGRES_TESTS') != '1', reason='Isolated PostgreSQL opt-in')


def test_jsonb_predicate_bulk_detachment_and_index_roundtrip():
    schema = 'test_delete_perf_' + uuid4().hex
    with engine.begin() as c:
        c.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    isolated = sa.create_engine(engine.url, connect_args={'options':f'-csearch_path={schema}'})
    try:
        Base.metadata.create_all(isolated)
        spec = importlib.util.spec_from_file_location('delete_perf_index', Path(__file__).parents[1] / 'alembic/versions/2026_11_19_0900_f6a1b2p2_security_actor_event.py')
        migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
        with isolated.begin() as c, Operations.context(MigrationContext.configure(c)):
            migration.downgrade()
            assert 'ix_foundation_security_actor_event' not in {i['name'] for i in sa.inspect(c).get_indexes('foundation_security_events')}
            migration.upgrade()
            index = next(i for i in sa.inspect(c).get_indexes('foundation_security_events') if i['name']=='ix_foundation_security_actor_event')
            assert index['column_names'] == ['actor_id','event_type']
        with Session(isolated,expire_on_commit=False) as db:
            org = Organization(name='Synthetic',code='PERF',status='active');db.add(org);db.flush()
            user = User(organization_id=org.id,email='perf@example.com',full_name='Performance',password_hash='!',status='active')
            db.add(user);db.flush()
            rows = [
                ('tenant.login_success',None,True),
                ('tenant.token_refreshed',{'user_id':str(user.id)},True),
                ('tenant.sessions_ended',{'reason':'session_limit'},True),
                ('tenant.sessions_ended',{'reason':'ended_by_user'},True),
                ('tenant.sessions_ended',{'reason':'admin_action'},False),
                ('tenant.sessions_ended',{},False),
                ('tenant.login_success',{'target_user_id':str(uuid4())},False),
                ('tenant.login_success',{'user_id':None},True),
                ('tenant.login_success',[],False),
                ('tenant.login_success','invalid',False),
                ('tenant.unknown_future_event',{},False),
                ('user.locked',{},False),
            ]
            for kind,details,expected in rows:
                record = TenantSecurityEvent(organization_id=org.id,actor_id=user.id,event_type=kind,details=details)
                db.add(record);db.flush()
                assert db.scalar(sa.select(personal_security_condition(db,user.id,org.id)).where(TenantSecurityEvent.id==record.id)) is expected
            db.execute(TenantSecurityEvent.__table__.insert(),[dict(organization_id=org.id,actor_id=user.id,
                event_type='tenant.token_refreshed',details={}) for _ in range(2000)])
            db.commit()
            statements=[]
            def capture(connection,cursor,statement,*args):statements.append(statement)
            sa.event.listen(isolated,'before_cursor_execute',capture)
            try:result=detach_personal_security(db,user)
            finally:sa.event.remove(isolated,'before_cursor_execute',capture)
            assert len(statements)==1 and statements[0].startswith('UPDATE ')
            assert result=={'foundation_security_events':2000+sum(expected for _,_,expected in rows)}
            db.commit()
            assert db.scalar(sa.select(sa.func.count()).select_from(TenantSecurityEvent).where(TenantSecurityEvent.actor_id==user.id))==sum(not expected for _,_,expected in rows)
            assert db.scalar(sa.select(sa.func.count()).select_from(TenantSecurityEvent).where(TenantSecurityEvent.actor_id.is_(None),TenantSecurityEvent.actor_email==user.email))==result['foundation_security_events']
    finally:
        isolated.dispose()
        with engine.begin() as c:c.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
