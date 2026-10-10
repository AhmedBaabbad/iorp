"""The product types procurement stores (MD-001): the specification key of a purchased material. Registered at the
composition root so master data can show and map legacy values without touching this table itself."""
from app.core.interfaces.product_types import holder_for
from app.procurement.infrastructure.models import Material

HOLDER = holder_for("procurement", (
    (Material, Material.spec_product_type, lambda org: Material.organization_id == org),
))
