from uuid import UUID
from dataclasses import replace
from sqlalchemy import select
from tests.commercial.test_quotation_document import doc_env,create_quote,html,QUOTES
from tests.commercial.test_customer_reports import env,reports_env,result_env
from app.commercial.infrastructure.quote_terms_models import QuoteTermsSnapshot

def settings(e,text):
    e.ctx.auth_user.permissions |= {'commercial:quotes:issue','commercial:quotes:revise'}
    e.ctx.tenant=replace(e.ctx.tenant,permissions=frozenset(e.ctx.auth_user.permissions))
    response=e.client.put(f'{QUOTES}/quote-settings',json=dict(terms=[dict(title_ar='الدفع',body_ar=text,title_en='Payment',body_en=text)]))
    assert response.status_code==200,response.text

def test_issued_terms_stay_frozen_and_revisions_capture_new_terms(doc_env):
    e=doc_env
    settings(e,'Original terms')
    quote=create_quote(e)
    response=e.client.post(f"{QUOTES}/quotes/{quote['id']}/issue")
    assert response.status_code==200,response.text
    settings(e,'Replacement terms')
    output=html(e,quote,'en')
    assert 'Original terms' in output and 'Replacement terms' not in output
    response=e.client.post(f"{QUOTES}/quotes/{quote['id']}/revise",json={'reason':'New revision'})
    assert response.status_code==200,response.text
    assert 'Replacement terms' in html(e,quote,'en')
    assert e.client.post(f"{QUOTES}/quotes/{quote['id']}/issue").status_code==200
    rows=list(e.db.scalars(select(QuoteTermsSnapshot).where(QuoteTermsSnapshot.quote_id==UUID(quote['id'])).order_by(QuoteTermsSnapshot.revision)))
    assert len(rows)==2 and rows[0].terms[0]['body_en']=='Original terms' and rows[1].terms[0]['body_en']=='Replacement terms'
    assert all(r.captured_by and r.captured_at and r.source=='issued' for r in rows)

def test_empty_snapshot_never_falls_back_to_later_settings(doc_env):
    e=doc_env;quote=create_quote(e)
    e.ctx.auth_user.permissions |= {'commercial:quotes:issue'}
    e.ctx.tenant=replace(e.ctx.tenant,permissions=frozenset(e.ctx.auth_user.permissions))
    assert e.client.post(f"{QUOTES}/quotes/{quote['id']}/issue").status_code==200
    settings(e,'Do not inject into issued quote')
    assert 'Do not inject into issued quote' not in html(e,quote,'en')


def test_failed_approval_rolls_back_status_and_snapshot(doc_env):
    from app.commercial.infrastructure.models import Quote
    e=doc_env;quote=create_quote(e)
    e.ctx.auth_user.permissions.add('commercial:quotes:issue')
    # Route permission alone does not fabricate a persisted or delegated approval authority.
    assert e.client.post(f"{QUOTES}/quotes/{quote['id']}/issue").status_code==403
    e.db.expire_all()
    assert e.db.get(Quote,UUID(quote['id'])).status=='draft'
    assert e.db.scalar(select(QuoteTermsSnapshot.id).where(QuoteTermsSnapshot.quote_id==UUID(quote['id']))) is None


def test_issued_history_cannot_be_deleted_and_legacy_notice_is_visible(doc_env):
    e=doc_env;settings(e,'Baseline');quote=create_quote(e)
    assert e.client.post(f"{QUOTES}/quotes/{quote['id']}/issue").status_code==200
    e.ctx.auth_user.permissions.add('commercial:quotes:delete')
    assert e.client.get(f"{QUOTES}/quotes/{quote['id']}/deletion-impact").json()['is_blocked'] is True
    assert e.client.delete(f"{QUOTES}/quotes/{quote['id']}").status_code==400
    snapshot=e.db.scalar(select(QuoteTermsSnapshot).where(QuoteTermsSnapshot.quote_id==UUID(quote['id'])))
    snapshot.source='legacy_baseline';e.db.commit()
    assert 'original terms were not archived' in html(e,quote,'en')
