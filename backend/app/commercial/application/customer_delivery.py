from fastapi import HTTPException
from sqlalchemy import select
from app.commercial.infrastructure.contact_models import CustomerContact,CustomerSite
from app.core.contact_records import view
from app.core.location_fields import city_text


class CustomerDeliveryProvider:
    def query(self,org,customer_id,kind):
        if kind not in ('contacts','sites'):raise HTTPException(404,'DIRECTORY_UNKNOWN')
        m=CustomerContact if kind=='contacts' else CustomerSite
        return m,select(m).where(m.organization_id==org,m.customer_id==customer_id,m.active.is_(True))

    def options(self,db,org,customer_id,kind,search=''):
        m,q=self.query(org,customer_id,kind)
        return [view(r) for r in db.scalars(q.where(m.name.icontains(search,autoescape=True)).order_by(m.is_default.desc(),m.name,m.id).limit(50))]

    def resolve(self,db,org,customer_id,kind,record_id):
        m,q=self.query(org,customer_id,kind)
        row=db.scalar(q.where(m.id==record_id))
        if not row:raise HTTPException(422,'CUSTOMER_DELIVERY_RECORD_UNAVAILABLE')
        result=view(row)
        if kind=='sites': result['city']=city_text(row.city,row.city_other)
        return result
