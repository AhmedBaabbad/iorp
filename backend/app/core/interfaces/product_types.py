"""Product types other modules store (MD-001).

Sales, production, quality and procurement store a product's key on their own records (a quotation line, an order,
a specification, a material). Before master data existed they stored free text, so the same product was written in
several ways. Master data shows those legacy values and maps each one to a product; it must not write the other
modules' tables, so each module registers, at the composition root, how to read and how to rewrite its own:

  usage(db, organization_id) -> {stored text: number of records}
  rename(db, organization_id, old_text, new_key) -> number of records changed   (the caller commits)
"""
from dataclasses import dataclass
from typing import Callable
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class ProductTypeHolder:
    module: str  # "commercial", "production", …
    usage: Callable[[Session, UUID], dict[str, int]]
    rename: Callable[[Session, UUID, str, str], int]


_holders: list[ProductTypeHolder] = []


def register_product_type_holder(holder: ProductTypeHolder) -> None:
    if all(h.module != holder.module for h in _holders):
        _holders.append(holder)


def product_type_holders() -> tuple[ProductTypeHolder, ...]:
    return tuple(_holders)


def count_values(db: Session, column, scope) -> dict[str, int]:
    """{stored text: records} of one column, within the organization's rows (scope is a where-clause)."""
    rows = db.execute(select(column, func.count()).where(scope, column.is_not(None)).group_by(column)).all()
    return {value: count for value, count in rows if value}


def replace_value(db: Session, model, column, scope, old: str, new: str) -> int:
    """Rewrite one stored text to a product key in the module's own table; the caller commits."""
    result = db.execute(update(model).where(column == old, scope).values({column.key: new}).execution_options(synchronize_session=False))
    return result.rowcount or 0


def holder_for(module: str, columns) -> ProductTypeHolder:
    """A holder over (model, column, scope(organization_id)) triples, each in the registering module's own tables."""
    def usage(db, organization_id):
        totals: dict[str, int] = {}
        for _model, column, scope in columns:
            for value, count in count_values(db, column, scope(organization_id)).items():
                totals[value] = totals.get(value, 0) + count
        return totals

    def rename(db, organization_id, old, new):
        return sum(replace_value(db, model, column, scope(organization_id), old, new) for model, column, scope in columns)
    return ProductTypeHolder(module, usage, rename)
