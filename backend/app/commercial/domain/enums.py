from enum import Enum


class CustomerStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ON_HOLD = "on_hold"
    ARCHIVED = "archived"
    BLACKLISTED = "blacklisted"


class RelationshipStage(str, Enum):
    LEAD = "lead"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    PROSPECT = "prospect"
    NEGOTIATING = "negotiating"
    TRIAL_CUSTOMER = "trial_customer"
    ACTIVE_CUSTOMER = "active_customer"
    REPEAT_CUSTOMER = "repeat_customer"
    STRATEGIC_CUSTOMER = "strategic_customer"


class PriorityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class InteractionType(str, Enum):
    CALL = "call"
    VISIT = "visit"
    WHATSAPP = "whatsapp"
    EMAIL = "email"
    MEETING = "meeting"


class FollowUpStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class FollowUpPriority(str, Enum):
    """Dedicated priority scale for FollowUp -- intentionally NOT the shared
    PriorityLevel used by Customer, so adding URGENT here can never leak
    into customer_priority_level (they are separate Postgres enum types)."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class SampleStatus(str, Enum):
    REQUESTED = "requested"
    IN_PREPARATION = "in_preparation"
    DELIVERED = "delivered"
    EVALUATED = "evaluated"
    CANCELLED = "cancelled"


class SampleDecision(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class SampleEvaluationResultStatus(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    NEEDS_MODIFICATION = "needs_modification"


class SampleEvaluationNextAction(str, Enum):
    PROCEED_TO_QUOTE = "proceed_to_quote"
    REVISE_SAMPLE = "revise_sample"
    CLOSE_REQUEST = "close_request"
    FURTHER_REVIEW = "further_review"


class QuoteStatus(str, Enum):
    DRAFT = "draft"
    ISSUED = "issued"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"


class CommercialOrderStatus(str, Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    CONVERTED_TO_PRODUCTION = "converted_to_production"
