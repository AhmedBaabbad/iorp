"""Server-side pagination, the same for every list in the system (ARCH-PAGE-001).

A list endpoint takes `page` (from 1) and `page_size` (25, 50 or 100 on the screens; 1–100 accepted, 50 by default) and
answers `Page`: the rows of that page, the total that matches the filters (counted after the permission filter, so it never
reveals rows the user may not see), and the number of pages. Searching, filtering and sorting are done by the query
before the page is cut, never by the browser on one page. The order always ends with a unique column (id), so a row
never repeats or disappears between two pages.
"""
from math import ceil
from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100

T = TypeVar("T")


class PageParams(BaseModel):
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def page_params(page: int = Query(1, ge=1), page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)) -> PageParams:
    """FastAPI dependency: `?page=2&page_size=50`."""
    return PageParams(page=page, page_size=page_size)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


def paginate(db: Session, statement: Select, params: PageParams) -> tuple[list, int]:
    """The rows of one page of an ordered statement, and the total of the whole statement."""
    total = int(db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0)
    rows = list(db.scalars(statement.offset(params.offset).limit(params.page_size))) if total else []
    return rows, total


def page_of(items: list, total: int, params: PageParams) -> dict:
    return dict(items=items, total=total, page=params.page, page_size=params.page_size,
                pages=ceil(total / params.page_size) if total else 0)
