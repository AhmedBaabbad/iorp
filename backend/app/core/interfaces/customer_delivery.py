"""Commercial owns customer contacts and sites, shared with Shipping through plain data."""
from typing import Protocol

class CustomerDelivery(Protocol):
    def options(self,db,org,customer_id,kind,search='')->list[dict]: ...
    def resolve(self,db,org,customer_id,kind,record_id)->dict: ...

_provider:CustomerDelivery|None=None

def register_customer_delivery(provider:CustomerDelivery):
    global _provider
    _provider=provider

def directory()->CustomerDelivery:
    if _provider is None:raise RuntimeError('Customer delivery provider unavailable')
    return _provider
