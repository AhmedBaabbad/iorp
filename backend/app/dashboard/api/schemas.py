from pydantic import AwareDatetime, BaseModel


class DashboardSummaryResponse(BaseModel):
    """Org-scoped counts for the dashboard KPI cards.

    Each field is None when the current user lacks the read permission for
    that module -- the frontend renders that as "no data" rather than "zero".
    """

    customers_count: int | None = None
    samples_count: int | None = None
    workforce_count: int | None = None
    workforce_active_count: int | None = None
    workforce_by_type: dict[str, int] | None = None
    workforce_by_status: dict[str, int] | None = None
    users_count: int | None = None
    roles_count: int | None = None
    quality_checks_count: int | None = None
    production_orders_count: int | None = None
    production_by_status: dict[str, int] | None = None
    quality_checks_by_result: dict[str, int] | None = None
    follow_ups_due_today: int | None = None
    follow_ups_overdue: int | None = None
    follow_ups_upcoming_7days: int | None = None
    follow_ups_completed_today: int | None = None
    follow_ups_needing_assignment: int | None = None
    last_updated_at: AwareDatetime | None = None
