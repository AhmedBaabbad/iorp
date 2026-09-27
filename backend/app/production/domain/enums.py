from enum import Enum


class ProductionRunStatus(str, Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ShiftRosterStatus(str, Enum):
    ACTIVE = "active"
    CLOSED = "closed"


class ProductionDemandStatus(str, Enum):
    DRAFT = "draft"
    READY_FOR_PLANNING = "ready_for_planning"
    PARTIALLY_PLANNED = "partially_planned"
    PLANNED = "planned"
    CANCELLED = "cancelled"


class ProductionAllocationStatus(str, Enum):
    ACTIVE = "active"
    RELEASED = "released"


class ProductionDemandPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class WorkCenterType(str, Enum):
    EXTRUSION = "extrusion"
    REWINDING = "rewinding"
    PACKING = "packing"
    QUALITY_STATION = "quality_station"
    GENERIC = "generic"


class WorkCenterStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    UNDER_MAINTENANCE = "under_maintenance"


class ShiftType(str, Enum):
    MORNING = "morning"
    EVENING = "evening"
    NIGHT = "night"
    CUSTOM = "custom"


class ShiftDefinitionStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class ShiftReportStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"


class ProductionOrderStatus(str, Enum):
    DRAFT = "draft"
    RELEASED = "released"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ProductionOrderPriority(str, Enum):
    HIGH = "high"
    URGENT = "urgent"
    NORMAL = "normal"
    LOW = "low"


class ProductionOutputStatus(str, Enum):
    RECORDED = "recorded"
    VERIFIED = "verified"
    POSTED = "posted"  # reserved for future inventory integration


class DowntimeCategory(str, Enum):
    MACHINE = "machine"
    MATERIAL = "material"
    MANPOWER = "manpower"
    QUALITY = "quality"
    UTILITIES = "utilities"
    SETUP = "setup"
    OTHER = "other"


class DowntimeStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


class WasteCategory(str, Enum):
    STARTUP_LOSS = "startup_loss"
    TRIM_LOSS = "trim_loss"
    SETUP_LOSS = "setup_loss"
    REJECTED_OUTPUT = "rejected_output"
    BREAKAGE = "breakage"
    REWINDING_LOSS = "rewinding_loss"
    END_OF_ROLL_LOSS = "end_of_roll_loss"
    MATERIAL_LOSS = "material_loss"
    CONTAMINATION_LOSS = "contamination_loss"
    OTHER = "other"
