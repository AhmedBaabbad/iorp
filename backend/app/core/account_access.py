class AccountAccessError(RuntimeError):
    """Account denial; traceback metadata must stay writable during dependency cleanup."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
