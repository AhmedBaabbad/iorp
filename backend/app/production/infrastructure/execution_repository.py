from sqlalchemy import select


class ExecutionRepository:
    def __init__(self, db, organization_id):
        self.db = db
        self.organization_id = organization_id

    def query(self, model):
        return select(model).where(model.organization_id == self.organization_id)

    def get(self, model, record_id, *, lock=False):
        query = self.query(model).where(model.id == record_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        return self.db.scalar(query)

    def list(self, model, **filters):
        query = self.query(model)
        for field, value in filters.items():
            if value is not None:
                query = query.where(getattr(model, field) == value)
        return list(self.db.scalars(query.order_by(model.created_at, model.id)))
