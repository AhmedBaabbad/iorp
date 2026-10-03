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


class ProductionOrderStatus(str, Enum):
    # Changed only through domain.order_lifecycle / OrderStatusService.
    DRAFT = "draft"
    RELEASED = "released"
    IN_PROGRESS = "in_progress"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class OrderTransitionTrigger(str, Enum):
    MANUAL = "manual"      # a user pressed an action button
    ACTIVITY = "activity"  # first recorded production activity (extension point)
    SCHEDULE = "schedule"  # planned start date reached, when enabled


class ProductionOrderPriority(str, Enum):
    HIGH = "high"
    URGENT = "urgent"
    NORMAL = "normal"
    LOW = "low"


class ResultDisposition(str, Enum):
    """What happened to produced quantity. Fixed and cross-industry; detail goes in reason_code."""
    CUSTOMER_GOOD = "customer_good"  # good, fulfils customer demand (capped by allocation)
    STOCK_GOOD = "stock_good"        # good, beyond demand or made for stock
    SAMPLE = "sample"                # samples / tests; loss or not is chosen per entry
    SCRAP = "scrap"                  # unusable final loss
    REWORK = "rework"                # not final-good, possibly recoverable


class ResultEntryType(str, Enum):
    ORIGINAL = "original"
    CORRECTION = "correction"  # signed delta against an original, only after the order is closed


class DowntimeCategory(str, Enum):
    """Why a machine stopped. Cross-industry; plant detail goes in reason_code.

    Planned stops (the first three) are outside planned production time: they do not reduce
    availability. Every other category is an availability loss, including changeover, which is
    scheduled but still time the machine could have produced (see domain/downtime_rules.py).
    """
    PLANNED_MAINTENANCE = "planned_maintenance"  # scheduled preventive maintenance, cleaning
    BREAK_MEETING = "break_meeting"              # breaks, meetings, training
    NO_ORDERS = "no_orders"                      # idle: nothing scheduled on the machine
    CHANGEOVER_SETUP = "changeover_setup"        # product, die, mould or colour change; setup
    BREAKDOWN = "breakdown"                      # mechanical or electrical failure
    MATERIAL_SHORTAGE = "material_shortage"      # waiting for raw material or components
    WAITING_LABOR = "waiting_labor"              # no operator available
    QUALITY_ISSUE = "quality_issue"              # stopped for a quality problem or adjustment
    UTILITIES = "utilities"                      # power, air, water, steam
    OTHER = "other"


class DowntimeStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


class WasteCategory(str, Enum):
    """Why material was lost during operation. Cross-industry; plant detail goes in reason_code.

    Finished product that turns out defective is not waste: it is scrap in the order's final result.
    """
    STARTUP_SETUP = "startup_setup"      # start-up, warm-up and machine setting
    CHANGEOVER = "changeover"            # product, colour, die or mould change
    PROCESS = "process"                  # normal process loss: trim, edges, cuts, purges
    MATERIAL_DEFECT = "material_defect"  # defective raw material or components
    MACHINE_FAULT = "machine_fault"      # breakdown or malfunction
    HANDLING_DAMAGE = "handling_damage"  # breakage or damage while handling
    CONTAMINATION = "contamination"
    OTHER = "other"