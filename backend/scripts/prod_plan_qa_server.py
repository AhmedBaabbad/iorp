"""Isolated UI verification server; never opens the project's PostgreSQL data."""
import os
import sys
from pathlib import Path

backend = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend))
qa_dir = backend.parent / ".tmp" / "prod-plan-qa"
qa_dir.mkdir(parents=True, exist_ok=True)
os.environ["DATABASE_URL"] = "sqlite:///" + (qa_dir / "ui.sqlite").as_posix()
os.environ["DEBUG"] = "true"
os.environ["CORS_ORIGINS"] = "http://localhost:3001,http://127.0.0.1:3001"
from sqlalchemy import select
from app.main import app
from app.core.db import Base, engine, SessionLocal
from app.core.security import hash_password
from app.core.utils import utc_now
from app.core.storage import LocalFileStorage
from app.foundation.infrastructure.models import Organization, User
from app.foundation.infrastructure.organization_queries import FoundationOrganizationQueries
from app.commercial.infrastructure.models import Customer, Quote, QuoteItem
from app.platform.infrastructure.models import BootstrapState

Base.metadata.create_all(engine)
with SessionLocal() as db:
    org = db.scalar(select(Organization).where(Organization.code == "PROD-PLAN-QA"))
    if org is None:
        org = Organization(name="Production Planning QA", code="PROD-PLAN-QA", timezone="UTC", default_locale="en")
        db.add(org); db.flush()
        user = User(organization_id=org.id, full_name="Planning Reviewer", email="planner-prod-plan@example.com", password_hash=hash_password("PlanReview123!"), is_organization_root=True)
        db.add(user); db.flush()
        provider = FoundationOrganizationQueries(db, LocalFileStorage(str(qa_dir / "uploads")))
        provider._seed_roles(org, provider._get_or_create_permissions(org.id))
        customer = Customer(organization_id=org.id, customer_code="C-QA-001", name="Rehana Packaging", sales_owner_user_id=user.id)
        db.add(customer); db.flush()
        quote = Quote(organization_id=org.id, customer_id=customer.id, quote_number="Q-QA-001", issue_date=utc_now(), valid_until=utc_now(), currency="SAR", subtotal_amount=500, discount_amount=0, tax_amount=0, total_amount=500, created_by_user_id=user.id)
        quote.items = [QuoteItem(line_no=1, product_type="pp_strap", requested_spec_json={"width_mm": 12, "thickness_mm": .6, "color": "blue", "roll_weight_kg": 12}, quantity=500, unit="kg", unit_price=1, line_total=500)]
        db.add(quote); db.commit()
    if db.get(BootstrapState, 1) is None:
        db.add(BootstrapState(id=1, is_initialized=True, first_organization_id=org.id, initialized_at=utc_now()))
        db.commit()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8081)
