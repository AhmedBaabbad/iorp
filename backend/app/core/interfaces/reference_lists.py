"""Reference lists as other modules see them (MD-002): sectors, opportunity sources, countries and cities.

Master data owns them; customers (commercial), suppliers (procurement) and shipments (shipping) store an item's key in
their own columns. They ask here, never by importing master data nor reading its tables; master data registers the
provider at the composition root. Read-only.

Choosing from a list: once the organization has an item in a list, a value written to a field of that list must be the
key of one of its active items. A value a record already stores (a legacy text, an item since deactivated) may stay on it.
Legacy texts are mapped from master data: each module registers a holder that rewrites its own records (`holder_for`).
"""
from dataclasses import dataclass
from typing import Iterable, Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.interfaces.product_types import count_values, replace_value


@dataclass(frozen=True)
class ListItemInfo:
    key: str
    name_ar: str
    name_en: str
    active: bool
    parent_key: str | None = None

    def name(self, lang: str) -> str:
        return self.name_ar if lang == "ar" else self.name_en


class ReferenceLists(Protocol):
    def defined(self, db: Session, organization_id: UUID, list_name: str) -> bool: ...
    def items(self, db: Session, organization_id: UUID, list_name: str, keys: Iterable[str]) -> dict[str, ListItemInfo]: ...


_provider: ReferenceLists | None = None


def register_reference_lists(provider: ReferenceLists) -> None:
    global _provider
    _provider = provider


def list_items(db: Session, organization_id: UUID, list_name: str, keys: Iterable[str]) -> dict[str, ListItemInfo]:
    keys = {k for k in keys if k}
    return _provider.items(db, organization_id, list_name, keys) if _provider and keys else {}


def names(db: Session, organization_id: UUID, list_name: str, values: Iterable[str], lang: str) -> dict[str, str]:
    """{stored value: what to print}: an item's name in `lang`, a legacy text as written."""
    values = {v for v in values if v}
    found = list_items(db, organization_id, list_name, values)
    return {v: (found[v].name(lang) if v in found else v) for v in values}


def unknown_list_values(db: Session, organization_id: UUID, list_name: str, values: Iterable[str], keep: Iterable[str] = ()) -> list[str]:
    """The values that may not be written: not an active item of the list, and not already stored on the record (keep)."""
    if _provider is None or not _provider.defined(db, organization_id, list_name):
        return []
    kept = set(keep)
    wanted = {v for v in values if v and v not in kept}
    found = list_items(db, organization_id, list_name, wanted)
    return sorted(v for v in wanted if not (v in found and found[v].active))


@dataclass(frozen=True)
class ReferenceHolder:
    """Where a module stores a list's values: usage(db, org) -> {text: records}; rename(db, org, old, key) -> records."""
    module: str
    list_name: str
    usage: object
    rename: object


_holders: list[ReferenceHolder] = []


def register_reference_holder(holder: ReferenceHolder) -> None:
    if all((h.module, h.list_name) != (holder.module, holder.list_name) for h in _holders):
        _holders.append(holder)


def reference_holders(list_name: str) -> tuple[ReferenceHolder, ...]:
    return tuple(h for h in _holders if h.list_name == list_name)


def holder_for(module: str, list_name: str, columns) -> ReferenceHolder:
    """A holder over (model, column, scope(organization_id)) triples, each in the registering module's own tables."""
    def usage(db, organization_id):
        totals: dict[str, int] = {}
        for _model, column, scope in columns:
            for value, count in count_values(db, column, scope(organization_id)).items():
                totals[value] = totals.get(value, 0) + count
        return totals

    def rename(db, organization_id, old, new):
        return sum(replace_value(db, model, column, scope(organization_id), old, new) for model, column, scope in columns)
    return ReferenceHolder(module, list_name, usage, rename)
