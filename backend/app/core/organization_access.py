class OrganizationAccessError(RuntimeError):
    """Organization denial with writable exception metadata for context managers."""

    def __init__(self, organization_status: str) -> None:
        self.organization_status = organization_status
        super().__init__(self.message)

    @property
    def code(self) -> str:
        return f"ORGANIZATION_{self.organization_status.upper()}"

    @property
    def message(self) -> str:
        return {
            "suspended": "Your organization has been suspended. Contact your administrator.",
            "inactive": "Your organization is currently inactive.",
            "archived": "Your organization has been archived.",
            "provisioning": "Your organization is still being provisioned.",
        }.get(self.organization_status, "Your organization is not active.")


def ensure_organization_access(status: str) -> None:
    if status != "active":
        raise OrganizationAccessError(status)
