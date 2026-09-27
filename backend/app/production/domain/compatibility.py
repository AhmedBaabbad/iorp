"""Product-independent compatibility policy; inject a subclass for industry rules."""
from dataclasses import dataclass


class AllocationError(ValueError):
    def __init__(self, code, status=400, **detail):
        super().__init__(code)
        self.code, self.status, self.detail = code, status, detail


class IncompatibleDemandItemsError(AllocationError):
    def __init__(self, reason):
        super().__init__("INCOMPATIBLE_DEMAND_ITEMS", reason=reason)


@dataclass(frozen=True)
class DemandItemSummary:
    product_type: str
    unit: str
    target_spec_json: dict | None


class DemandItemCompatibilityChecker:
    def validate_compatibility(self, items):
        if not items:
            return
        base = items[0]
        for item in items[1:]:
            if item.product_type != base.product_type:
                raise IncompatibleDemandItemsError("DIFFERENT_PRODUCT_TYPE")
            if item.unit != base.unit:
                raise IncompatibleDemandItemsError("DIFFERENT_UNIT")
            if not self._specs_compatible(base.target_spec_json, item.target_spec_json):
                raise IncompatibleDemandItemsError("INCOMPATIBLE_SPECIFICATIONS")

    def _specs_compatible(self, spec_a, spec_b):
        return spec_a == spec_b
