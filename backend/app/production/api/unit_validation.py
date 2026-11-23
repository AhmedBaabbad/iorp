"""Update validation needs the tenant-scoped saved record, unavailable during initial HTTP parsing."""
from pydantic import BaseModel, ValidationError, ValidationInfo, field_validator
from pydantic_core import PydanticCustomError
from app.production.domain.units import checked_unit


def known_new_unit(value: str) -> str:
    try:
        return checked_unit(value)
    except ValueError as exc:
        raise PydanticCustomError("UNIT_UNKNOWN", "UNIT_UNKNOWN") from exc


class ProductionUnitUpdate(BaseModel):
    @field_validator("unit", check_fields=False)
    @classmethod
    def known_changed_unit(cls, value, info: ValidationInfo):
        if value is None:
            raise PydanticCustomError("UNIT_UNKNOWN", "UNIT_UNKNOWN")
        if info.context is not None:
            try:
                checked_unit(value, info.context.get("previous_unit"))
            except ValueError as exc:
                raise PydanticCustomError("UNIT_UNKNOWN", "UNIT_UNKNOWN") from exc
        return value

    def validate_unit_change(self, previous: str | None):
        """Called after loading/locking the saved row, before any data is changed."""
        try:
            type(self).model_validate(self.model_dump(exclude_unset=True), context={"previous_unit": previous})
        except ValidationError as exc:
            if any("UNIT_UNKNOWN" in error["msg"] for error in exc.errors()):
                raise ValueError("UNIT_UNKNOWN") from exc
            raise
        return self
