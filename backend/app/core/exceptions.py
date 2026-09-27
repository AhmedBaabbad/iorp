"""Application exception placeholders.

Domain and HTTP exception mapping will be added with future slices.
"""
class OrganizationCodeTakenError(RuntimeError):
    """Raised by the organization owner when a code is already allocated."""


class EmailAlreadyExistsError(RuntimeError):
    """Raised when a provisioning identity email is already allocated."""
