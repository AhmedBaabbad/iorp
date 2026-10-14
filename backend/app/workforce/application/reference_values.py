"""Where the workforce stores reference-list values (MD-003): a member's primary skill (its name, as written)."""
from app.core.interfaces.reference_lists import holder_for
from app.workforce.infrastructure.models import WorkforceMember

HOLDERS = (holder_for("workforce", "workforce_skill", ((WorkforceMember, WorkforceMember.primary_skill, lambda org: WorkforceMember.organization_id == org),)),)
