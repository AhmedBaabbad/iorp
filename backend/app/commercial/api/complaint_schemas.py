from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class PropertyInput(Input):
    key: str = Field(min_length=1, max_length=120)
    # Typed by hand only when the item has no source (a sales order line or a sample gives the agreed values itself).
    expected: str = Field(default='', max_length=1000)
    reported: str = Field(default='', max_length=1000)


class ItemInput(Input):
    # Present when an existing line is edited; absent for a new line.
    id: UUID | None = None
    product_key: str = Field(min_length=1, max_length=120)
    # The agreed specification: from a sales order line or a sample of this customer, or typed by hand.
    source_kind: Literal['order', 'sample', 'manual'] = 'manual'
    source_id: UUID | None = None
    batch_reference: str | None = Field(None, max_length=255)
    unit: str = Field(min_length=1, max_length=32)
    delivered_quantity: Decimal = Field(ge=0, max_digits=15, decimal_places=3)
    reported_quantity: Decimal = Field(ge=0, max_digits=15, decimal_places=3)
    properties: list[PropertyInput] = Field(default_factory=list, max_length=100)

    @model_validator(mode='after')
    def checks(self):
        if self.reported_quantity > self.delivered_quantity:
            raise ValueError('REPORTED_EXCEEDS_DELIVERED')
        if (self.source_kind == 'manual') != (self.source_id is None):
            raise ValueError('SOURCE_INVALID')
        return self


class ComplaintCreate(Input):
    customer_id: UUID
    title: str = Field(min_length=1, max_length=255)
    statement: str = Field(min_length=1, max_length=10000)
    contact: str | None = Field(None, max_length=255)
    channel: Literal['phone', 'email', 'visit', 'message', 'other'] = 'email'
    received_date: date
    category: str = Field(pattern=r'^[a-z][a-z0-9_]{1,59}$')  # MD-003: a key of the organization's complaint categories
    priority: Literal['low', 'medium', 'high', 'critical'] = 'medium'
    response_due_date: date | None = None
    due_date: date | None = None
    external_reference: str | None = Field(None, max_length=255)
    items: list[ItemInput] = Field(default_factory=list, max_length=100)

    @model_validator(mode='after')
    def dates(self):
        if any(d and d < self.received_date for d in (self.response_due_date, self.due_date)):
            raise ValueError('DUE_BEFORE_RECEIPT')
        return self


class Versioned(Input):
    version: int = Field(ge=1)


class Items(Versioned):
    """All the complaint's product lines: an existing line keeps its id (and its measurements); a missing one is removed."""
    items: list[ItemInput] = Field(default_factory=list, max_length=100)


class Assignment(Versioned):
    owner_user_id: UUID
    department: Literal['commercial', 'quality', 'shipping', 'production']
    due_date: date
    reason: str = Field(min_length=1, max_length=2000)


class Measurement(Input):
    key: str = Field(min_length=1, max_length=120)
    measured: str = Field(default='', max_length=1000)


class ItemFinding(Input):
    """What the investigation established for one line: the quantity confirmed as affected and the measured values."""
    item_id: UUID
    confirmed_quantity: Decimal | None = Field(None, ge=0, max_digits=15, decimal_places=3)
    measurements: list[Measurement] = Field(default_factory=list, max_length=100)


class Investigation(Versioned):
    finding: Literal['pending', 'verified', 'not_verified', 'inconclusive']
    investigation: str = Field(min_length=1, max_length=10000)
    containment: str = Field(default='', max_length=10000)
    items: list[ItemFinding] = Field(default_factory=list, max_length=100)


class Resolution(Versioned):
    resolution: str = Field(min_length=1, max_length=10000)
    implementation_evidence: str = Field(min_length=1, max_length=10000)
    customer_response: str = Field(min_length=1, max_length=10000)


class Transition(Versioned):
    action: Literal['request_close', 'approve_close', 'return', 'reopen', 'cancel']
    reason: str = Field(min_length=1, max_length=2000)


class Note(Versioned):
    notes: str = Field(min_length=1, max_length=10000)


class Communication(Note):
    # True when this was sent to the customer (it counts as the reply the response deadline waits for).
    to_customer: bool = False


class LinkInput(Versioned):
    kind: Literal['order', 'shipment', 'return', 'ncr']
    record_id: UUID
