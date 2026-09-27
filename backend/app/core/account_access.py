from dataclasses import dataclass


@dataclass(frozen=True)
class AccountAccessError(RuntimeError):
    code: str
    message: str
