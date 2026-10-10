"""Master data's answer to core/interfaces/product_catalog.py (MD-001): what other modules may know of the products and
the general settings, without importing this module. Registered at the composition root."""
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.interfaces.product_catalog import BusinessSettings, ProductInfo, PropertyInfo, ProductSpecificationError
from app.core.interfaces.reference_lists import ListItemInfo
from app.masterdata.domain import rules
from app.masterdata.infrastructure.models import ListItem, MasterDataSettings, Product


class MasterDataCatalog:
    def defined(self, db, organization_id) -> bool:
        return db.scalar(select(Product.id).where(Product.organization_id == organization_id).limit(1)) is not None

    def products(self, db, organization_id, keys) -> dict[str, ProductInfo]:
        rows = db.scalars(select(Product).options(selectinload(Product.properties)).where(
            Product.organization_id == organization_id, Product.key.in_(list(keys))))
        return {p.key: ProductInfo(p.key, p.name_ar, p.name_en, p.active, tuple(
            PropertyInfo(q.key, q.name_ar, q.name_en, q.kind, q.unit, tuple((o["value"], o["label_ar"], o["label_en"]) for o in q.options or ()), q.required)
            for q in p.properties), p.default_unit) for p in rows}

    def sample_products(self, db, organization_id):
        keys=db.scalars(select(Product.key).where(Product.organization_id==organization_id,Product.active.is_(True)).order_by(Product.code)).all()
        found=self.products(db,organization_id,keys)
        return [found[key] for key in keys]

    def validate_sample_properties(self, db, organization_id, key, values, *, existing_key=None, existing_values=None):
        product=self.products(db,organization_id,[key]).get(key)
        if product is None:
            raise ProductSpecificationError('SAMPLE_PRODUCT_NOT_FOUND')
        if not product.active and key!=existing_key:
            raise ProductSpecificationError('SAMPLE_PRODUCT_INACTIVE')
        preserved = existing_values if key == existing_key else None
        if preserved:
            known = {p.key for p in product.properties}
            values = {**{k: v for k, v in preserved.items() if k not in known}, **values}
        rules.assert_property_values(product.properties, values, preserved)
        return values

    def settings(self, db, organization_id) -> BusinessSettings:
        row = db.get(MasterDataSettings, organization_id)
        return BusinessSettings(row.vat_rate if row else rules.DEFAULT_VAT_RATE, row.default_currency if row else rules.DEFAULT_CURRENCY)


class MasterDataLists:
    """Master data's answer to core/interfaces/reference_lists.py (MD-002)."""
    def defined(self, db, organization_id, list_name) -> bool:
        return db.scalar(select(ListItem.id).where(ListItem.organization_id == organization_id, ListItem.list == list_name).limit(1)) is not None

    def items(self, db, organization_id, list_name, keys) -> dict[str, ListItemInfo]:
        rows = db.scalars(select(ListItem).where(ListItem.organization_id == organization_id, ListItem.list == list_name, ListItem.key.in_(list(keys))))
        return {r.key: ListItemInfo(r.key, r.name_ar, r.name_en, r.active, r.parent_key) for r in rows}
