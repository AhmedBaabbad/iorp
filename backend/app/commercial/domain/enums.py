from enum import Enum


class CustomerStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class RelationshipStage(str, Enum):
    LEAD = "lead"
    PROSPECT = "prospect"
    CUSTOMER = "customer"


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
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class SampleStatus(str, Enum):
    REQUESTED = "requested"
    IN_PREPARATION = "in_preparation"
    DELIVERED = "delivered"
    EVALUATED = "evaluated"
    CANCELLED = "cancelled"


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
