"""The product types quality stores (MD-001): on product specifications. Registered at the composition root so master
data can show and map legacy values without touching this table itself."""
from app.core.interfaces.product_types import holder_for
from app.quality.infrastructure.models import QualitySpecification

HOLDER = holder_for("quality", (
    (QualitySpecification, QualitySpecification.product_type, lambda org: QualitySpecification.organization_id == org),
))
