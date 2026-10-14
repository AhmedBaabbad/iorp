"""Quality owns NCR creation; the caller owns the shared transaction."""
from typing import Callable

_create: Callable | None = None


def register_complaint_quality(create: Callable) -> None:
    global _create
    _create = create


def refer_complaint(db, tenant, *, number, title, statement, customer_id, customer_name):
    if _create is None:
        raise RuntimeError('Complaint quality provider is not registered')
    return _create(db, tenant, number=number, title=title, statement=statement,
                   customer_id=customer_id, customer_name=customer_name)
