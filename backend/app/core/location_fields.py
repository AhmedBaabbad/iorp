"""Shared location validation and display primitives; no module model imports."""
from typing import Annotated
from urllib.parse import urlsplit

from pydantic import AfterValidator
from pydantic_core import PydanticCustomError
from sqlalchemy import case


def https_location(value: str) -> str:
    try:
        parsed = urlsplit(value)
        valid = parsed.scheme == "https" and bool(parsed.hostname) and not any(c.isspace() or ord(c) < 32 for c in value)
        _ = parsed.port
    except ValueError:
        valid = False
    if not valid:
        raise PydanticCustomError("LOCATION_URL_INVALID", "LOCATION_URL_INVALID")
    return value


LocationURL = Annotated[str, AfterValidator(https_location)]


def normalize_city(values: dict, record=None) -> dict:
    """Normalize partial writes without losing an unchanged legacy location."""
    if record is not None and "country" in values and values["country"] != record.country and "city" not in values:
        values["city"] = None
    city = values.get("city", getattr(record, "city", None))
    other = values.get("city_other", getattr(record, "city_other", None))
    if not city or not city.endswith("_other"):
        values["city_other"] = None
    else:
        other = other.strip() if other else None
        if not other and (record is None or "city" in values or "city_other" in values):
            raise ValueError("CITY_OTHER_REQUIRED")
        values["city_other"] = other
    return values


def city_text(city: str | None, other: str | None) -> str | None:
    return other if city and city.endswith("_other") and other else city


def city_expression(city, other):
    return case((city.endswith("_other", autoescape=True) & other.is_not(None), other), else_=city)


def assert_city_country(db, organization_id, values, record=None):
    from sqlalchemy import select
    from app.core.db import Base
    city, country = values.get("city", getattr(record, "city", None)), values.get("country", getattr(record, "country", None))
    if not city or not country or (record is not None and city == record.city and country == record.country):
        return
    items = Base.metadata.tables["masterdata_list_items"]
    parent = db.scalar(select(items.c.parent_key).where(items.c.organization_id == organization_id,
        items.c.list == "city", items.c.key == city))
    if parent and parent != country:
        raise ValueError("CITY_COUNTRY_MISMATCH")


def effective_contact_columns(parent, contacts, parent_key="customer_id"):
    """Default contact fields, falling back only when no default contact exists.

    An empty phone on a default contact must not resurrect a retired legacy phone.
    Both sides are tenant-scoped; callers supply their own tables.
    """
    from sqlalchemy import select
    query = select(contacts.c.id).where(contacts.c[parent_key] == parent.c.id,
        contacts.c.organization_id == parent.c.organization_id, contacts.c.is_default.is_(True)).correlate(parent)
    present = query.exists()
    return {field: case((present, query.with_only_columns(contacts.c[field]).order_by(contacts.c.created_at, contacts.c.id)
                        .limit(1).scalar_subquery()), else_=parent.c[field]) for field in ("phone", "email")}
