"""Where procurement stores reference-list values (MD-002): a supplier's country and city. Registered at the composition
root so master data can show and map legacy texts without touching this table itself."""
from app.core.interfaces.reference_lists import holder_for
from app.procurement.infrastructure.models import Material, Supplier

HOLDERS = tuple(holder_for("procurement", list_name, ((Supplier, column, lambda org: Supplier.organization_id == org),))
                for list_name, column in (("country", Supplier.country), ("city", Supplier.city), ("supplier_category", Supplier.category)))
HOLDERS += (holder_for("procurement", "material_category", ((Material, Material.category, lambda org: Material.organization_id == org),)),)
