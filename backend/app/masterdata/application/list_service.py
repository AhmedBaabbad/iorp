"""Reference lists (MD-002): the single writer of sectors, opportunity sources, countries and cities.

Legacy texts other modules stored before a list existed are read and rewritten through the holders they register
(core/interfaces/reference_lists.py): this module never touches their tables.
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func, select

from app.core.interfaces.reference_lists import reference_holders
from app.masterdata.domain import lists as L
from app.masterdata.domain import rules
from app.masterdata.domain.rules import MasterDataError
from app.masterdata.infrastructure.models import ListItem
from .services import log_activity


class ListService:
    def __init__(self, db, tenant):
        self.db, self.tenant, self.org = db, tenant, tenant.organization_id

    def items(self, list_name=None, active_only=False) -> list[ListItem]:
        query = select(ListItem).where(ListItem.organization_id == self.org)
        if list_name:
            L.assert_list(list_name)
            query = query.where(ListItem.list == list_name)
        if active_only:
            query = query.where(ListItem.active.is_(True))
        return list(self.db.scalars(query.order_by(ListItem.list, ListItem.sort_order, ListItem.name_ar)))

    def _get(self, item_id) -> ListItem:
        found = self.db.scalar(select(ListItem).where(ListItem.id == item_id, ListItem.organization_id == self.org).with_for_update())
        if found is None:
            raise MasterDataError("ITEM_NOT_FOUND", 404)
        return found

    def _keys(self, list_name) -> set[str]:
        return set(self.db.scalars(select(ListItem.key).where(ListItem.organization_id == self.org, ListItem.list == list_name)))

    def _add(self, list_name, key, name_ar, name_en, parent_key=None, sort_order=None) -> ListItem:
        parents = self._keys(L.PARENT[list_name]) if list_name in L.PARENT else set()
        L.assert_item(list_name, key, parent_key, parents)
        if key in self._keys(list_name):
            raise MasterDataError("ITEM_KEY_TAKEN", key=key)
        if sort_order is None:
            sort_order = (self.db.scalar(select(func.max(ListItem.sort_order)).where(ListItem.organization_id == self.org, ListItem.list == list_name)) or 0) + 1
        item = ListItem(organization_id=self.org, list=list_name, key=key, name_ar=name_ar, name_en=name_en, parent_key=parent_key, sort_order=sort_order)
        self.db.add(item)
        self.db.flush()
        return item

    def create(self, list_name, data) -> ListItem:
        L.assert_list(list_name)
        if len(self._keys(list_name)) >= L.MAX_ITEMS:
            raise MasterDataError("TOO_MANY_ITEMS", 400, limit=L.MAX_ITEMS)
        item = self._add(list_name, data.key or rules.key_from(data.name_en), data.name_ar, data.name_en, data.parent_key)
        self.db.commit()
        log_activity(self.db, self.org, self.tenant.user_id, f"list_item.created.{list_name}", item.id, item.name_ar)
        return item

    # ── use and deletion (MD-003): an item no record uses is deleted; one in use is only deactivated ──────────────
    def usage(self, list_name) -> dict[str, int]:
        """{stored value: records} across every module storing this list (keys; the English name for a text list)."""
        totals: dict[str, int] = {}
        for holder in reference_holders(list_name):
            for value, count in holder.usage(self.db, self.org).items():
                totals[value] = totals.get(value, 0) + count
        return totals

    def uses(self, item, usage=None) -> int:
        usage = self.usage(item.list) if usage is None else usage
        if item.list in L.TEXT_LISTS:
            return sum(usage.get(v, 0) for v in {item.name_en, item.name_ar, item.key})
        return usage.get(item.key, 0)

    def with_uses(self, items) -> list[dict]:
        usage: dict[str, dict] = {}
        out = []
        for item in items:
            if item.list not in usage:
                usage[item.list] = self.usage(item.list)
            out.append(dict(id=item.id, list=item.list, key=item.key, name_ar=item.name_ar, name_en=item.name_en, parent_key=item.parent_key,
                            active=item.active, sort_order=item.sort_order, uses=self.uses(item, usage[item.list]),
                            protected=item.key in L.PROTECTED.get(item.list, ())))
        return out

    def delete(self, item_id) -> dict:
        """Deletes an item nothing uses (nor a city belonging to it); an item in use is deactivated instead, never deleted."""
        item = self._get(item_id)
        if item.key in L.PROTECTED.get(item.list, ()):
            raise MasterDataError("ITEM_PROTECTED", 409)
        used = self.uses(item)
        if used:
            raise MasterDataError("ITEM_IN_USE", 409, uses=used)
        children = [l for l, parent in L.PARENT.items() if parent == item.list]
        if children and self.db.scalar(select(func.count()).select_from(ListItem).where(
                ListItem.organization_id == self.org, ListItem.list.in_(children), ListItem.parent_key == item.key)):
            raise MasterDataError("ITEM_HAS_CHILDREN", 409)
        name, list_name = item.name_ar, item.list
        self.db.delete(item)
        self.db.commit()
        log_activity(self.db, self.org, self.tenant.user_id, f"list_item.deleted.{list_name}", item_id, name)
        return dict(deleted=1)

    def update(self, item_id, data) -> ListItem:
        """Names, active, order, a city's country; the key never changes (other modules store it)."""
        item = self._get(item_id)
        values = data.model_dump(exclude_unset=True)
        for field in ("name_ar", "name_en", "active", "sort_order"):
            if values.get(field) is not None:
                setattr(item, field, values[field])
        if "parent_key" in values:
            parents = self._keys(L.PARENT[item.list]) if item.list in L.PARENT else set()
            L.assert_item(item.list, item.key, values["parent_key"], parents)
            item.parent_key = values["parent_key"]
        self.db.commit()
        return item

    def add_standard(self, list_name) -> list[ListItem]:
        """The usual values not there yet (a city's country is added with it when missing)."""
        L.assert_list(list_name)
        if list_name in L.PARENT:
            parents, have = {row[3] for row in L.STANDARD[list_name]}, self._keys(L.PARENT[list_name])
            for row in L.STANDARD[L.PARENT[list_name]]:
                if row[0] in parents and row[0] not in have:
                    self._add(L.PARENT[list_name], *row[:3])
        have = self._keys(list_name)
        added = [self._add(list_name, row[0], row[1], row[2], row[3] if len(row) > 3 else None) for row in L.STANDARD[list_name] if row[0] not in have]
        self.db.commit()
        return added

    # ── legacy texts ────────────────────────────────────────────────────────────────────────────
    def legacy(self, list_name) -> list[dict]:
        L.assert_list(list_name)
        if list_name in L.TEXT_LISTS:
            return []  # their records keep the name as written: nothing to map to a key
        keys = self._keys(list_name)
        found: dict[str, dict[str, int]] = defaultdict(dict)
        for holder in reference_holders(list_name):
            for text, count in holder.usage(self.db, self.org).items():
                if text and text not in keys:
                    found[text][holder.module] = found[text].get(holder.module, 0) + count
        rows = [dict(value=t, uses=u, total=sum(u.values()), suggested_key=rules.key_from(t)) for t, u in found.items()]
        return sorted(rows, key=lambda r: (-r["total"], r["value"]))

    def map_legacy(self, list_name, value, item_id) -> dict:
        L.assert_list(list_name)
        if list_name in L.TEXT_LISTS:
            raise MasterDataError("LEGACY_VALUE_INVALID", 400)
        item = self._get(item_id)
        if item.list != list_name or not value or value == item.key:
            raise MasterDataError("LEGACY_VALUE_INVALID", 400)
        changed = {}
        for holder in reference_holders(list_name):
            changed[holder.module] = changed.get(holder.module, 0) + holder.rename(self.db, self.org, value, item.key)
        if not any(changed.values()):
            self.db.rollback()
            raise MasterDataError("LEGACY_VALUE_NOT_FOUND", 404, value=value)
        self.db.commit()
        log_activity(self.db, self.org, self.tenant.user_id, f"list_item.legacy_mapped.{list_name}", item.id, f"{value} → {item.key}")
        return dict(value=value, key=item.key, changed=changed)


def seed_standard_lists(db, organization_id) -> int:
    """MD-003: every list's usual values for a new organization (countries before their cities); the caller commits."""
    have: dict[str, set[str]] = defaultdict(set)
    for list_name, key in db.execute(select(ListItem.list, ListItem.key).where(ListItem.organization_id == organization_id)):
        have[list_name].add(key)
    ordered = sorted(L.STANDARD, key=lambda name: name in L.PARENT)  # a parent list before the lists that belong to it
    added = 0
    for list_name in ordered:
        for order, row in enumerate(L.STANDARD[list_name], 1):
            if row[0] in have[list_name]:
                continue
            db.add(ListItem(organization_id=organization_id, list=list_name, key=row[0], name_ar=row[1], name_en=row[2],
                            parent_key=row[3] if len(row) > 3 else None, sort_order=order))
            have[list_name].add(row[0])
            added += 1
    db.flush()
    return added
