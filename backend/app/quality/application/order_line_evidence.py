from sqlalchemy import select
from app.quality.infrastructure.models import QualityCheck, QualityDefect, QualityRejection, QualityCertificate


def evidence(db, org, line_id):
    # Quality stores cross-module IDs without FKs; only quality knows its records.
    return [model.__tablename__ for model in (QualityCheck, QualityDefect, QualityRejection, QualityCertificate)
            if db.scalar(select(model.id).where(model.organization_id == org, model.production_order_item_id == line_id).limit(1)) is not None]
