"""Master data services (MD-001): the single writers of products, their specification templates and the general settings.

Legacy product types (free text written before master data) are read and rewritten through the holders other modules
register (core/interfaces/product_types.py): this module never touches their tables.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.core.interfaces.activity_log import get_registered_activity_logger
from app.core.interfaces.product_types import product_type_holders
from app.core import numbering
from app.masterdata.domain import rules
from app.masterdata.domain.rules import MasterDataError
from app.masterdata.infrastructure.models import MasterDataCounter, MasterDataSettings, Product, ProductProperty

HEADER = ("name_ar", "name_en", "kind", "default_unit", "active", "notes")


def log_activity(db, organization_id, actor_id, action, entity_id, name):
    """The tenant activity log (best effort, after the business commit), like the other modules."""
    try:
        get_registered_activity_logger().log_activity(db, organization_id, action, "product", entity_id, name, actor_id)
        db.commit()
    except Exception:  # noqa: BLE001 - logging never fails the business action
        db.rollback()


class ProductService:
    def __init__(self, db, tenant):
        self.db, self.tenant, self.org = db, tenant, tenant.organization_id

    def _get(self, product_id, lock=False) -> Product:
        query = select(Product).options(selectinload(Product.properties)).where(Product.id == product_id, Product.organization_id == self.org)
        found = self.db.scalar(query.with_for_update() if lock else query)
        if found is None:
            raise MasterDataError("PRODUCT_NOT_FOUND", 404)
        return found

    def get(self, product_id) -> Product:
        return self._get(product_id)

    def list(self, search=None, kind=None, active_only=False, limit=500) -> list[Product]:
        query = select(Product).options(selectinload(Product.properties)).where(Product.organization_id == self.org)
        if kind:
            query = query.where(Product.kind == kind)
        if active_only:
            query = query.where(Product.active.is_(True))
        if search:
            like = lambda column: column.icontains(search, autoescape=True)  # noqa: E731
            query = query.where(or_(like(Product.name_ar), like(Product.name_en), like(Product.key), like(Product.code)))
        return list(self.db.scalars(query.order_by(Product.active.desc(), Product.name_ar).limit(limit)))

    def _next_code(self) -> str:
        # A master record: one sequence that never restarts (core/numbering.py takes it without a race).
        return f"PRD-{numbering.take(self.db, MasterDataCounter, organization_id=self.org, kind='PRD'):04d}"

    def _write_template(self, product, properties):
        rules.assert_template(properties)
        product.properties.clear()
        self.db.flush()
        for number, prop in enumerate(properties, 1):
            product.properties.append(ProductProperty(
                line_no=number, key=prop.key, name_ar=prop.name_ar, name_en=prop.name_en, kind=prop.kind, unit=prop.unit or None,
                required=prop.required, options=[o.model_dump() for o in prop.options] if prop.options else None))

    def create(self, data) -> Product:
        key = data.key or rules.key_from(data.name_en)
        rules.assert_key(key)
        if self.db.scalar(select(Product.id).where(Product.organization_id == self.org, Product.key == key)):
            raise MasterDataError("PRODUCT_KEY_TAKEN", key=key)
        product = Product(organization_id=self.org, code=self._next_code(), key=key, created_by_user_id=self.tenant.user_id)
        for field in HEADER:
            setattr(product, field, getattr(data, field))
        self.db.add(product)
        self.db.flush()
        self._write_template(product, data.properties)
        self.db.commit()
        log_activity(self.db, self.org, self.tenant.user_id, "product.created", product.id, product.name_ar)
        return self._get(product.id)

    def update(self, product_id, data) -> Product:
        """Names, kind, unit, notes, active, and the template; the key never changes (other modules store it)."""
        product = self._get(product_id, lock=True)
        values = data.model_dump(exclude_unset=True, exclude={"properties"})
        for field in HEADER:
            if field in values and not (field in ("name_ar", "name_en", "kind", "active") and values[field] is None):
                setattr(product, field, values[field])
        if data.properties is not None:
            self._write_template(product, data.properties)
        self.db.commit()
        log_activity(self.db, self.org, self.tenant.user_id, "product.updated", product.id, product.name_ar)
        return self._get(product.id)

    # ── legacy product types ────────────────────────────────────────────────────────────────────
    def legacy(self) -> list[dict]:
        """What other modules store that is not a product key yet: each text, where it is used and how often."""
        keys = set(self.db.scalars(select(Product.key).where(Product.organization_id == self.org)))
        found: dict[str, dict[str, int]] = defaultdict(dict)
        for holder in product_type_holders():
            for text, count in holder.usage(self.db, self.org).items():
                if text and text not in keys:
                    found[text][holder.module] = found[text].get(holder.module, 0) + count
        rows = [dict(value=text, uses=uses, total=sum(uses.values()), suggested_key=rules.key_from(text)) for text, uses in found.items()]
        return sorted(rows, key=lambda r: (-r["total"], r["value"]))

    def map_legacy(self, value: str, product_id) -> dict:
        """Every record that stores this text now stores the product's key, in each module through its own holder."""
        product = self._get(product_id)
        if not value or value == product.key:
            raise MasterDataError("LEGACY_VALUE_INVALID", 400)
        changed = {holder.module: holder.rename(self.db, self.org, value, product.key) for holder in product_type_holders()}
        if not any(changed.values()):
            self.db.rollback()
            raise MasterDataError("LEGACY_VALUE_NOT_FOUND", 404, value=value)
        self.db.commit()
        log_activity(self.db, self.org, self.tenant.user_id, "product.legacy_mapped", product.id, f"{value} → {product.key}")
        return dict(value=value, key=product.key, changed=changed)


class SettingsService:
    def __init__(self, db, tenant):
        self.db, self.tenant, self.org = db, tenant, tenant.organization_id

    def read(self) -> dict:
        row = self.db.get(MasterDataSettings, self.org)
        rate = row.vat_rate if row else rules.DEFAULT_VAT_RATE
        return dict(vat_rate=Decimal(rate).quantize(Decimal("0.01")), default_currency=row.default_currency if row else rules.DEFAULT_CURRENCY,
                    currencies=list(rules.CURRENCIES))

    def update(self, data) -> dict:
        rules.assert_settings(data.vat_rate, data.default_currency)
        row = self.db.get(MasterDataSettings, self.org, with_for_update=True)
        if row is None:
            row = MasterDataSettings(organization_id=self.org, vat_rate=rules.DEFAULT_VAT_RATE, default_currency=rules.DEFAULT_CURRENCY)
            self.db.add(row)
        if data.vat_rate is not None:
            row.vat_rate = data.vat_rate
        if data.default_currency is not None:
            row.default_currency = data.default_currency
        row.updated_by_user_id = self.tenant.user_id
        self.db.commit()
        return self.read()
