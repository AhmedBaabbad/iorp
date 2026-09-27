from collections import defaultdict, deque
from time import monotonic

from fastapi import Request

from app.core.config import settings

_attempts: dict[tuple[str, str], deque[float]] = defaultdict(deque)


class LoginRateLimitError(RuntimeError):
    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__("Too many login attempts.")


def get_client_ip(request: Request) -> str:
    direct_host = request.client.host if request.client else "unknown"
    trusted_proxies = {value.strip() for value in settings.trusted_proxy_ips.split(",") if value.strip()}
    forwarded = request.headers.get("x-forwarded-for")
    if direct_host in trusted_proxies and forwarded:
        # Use the hop immediately before our trusted proxy. Earlier entries may
        # have been supplied by an untrusted client or proxy.
        return forwarded.split(",")[-1].strip() or direct_host
    return direct_host


def check_rate_limit(request: Request, scope: str, *, limit: int = 5, window_seconds: float = 60) -> None:
    client_host = get_client_ip(request)
    key = (scope, client_host)
    now = monotonic()
    attempts = _attempts[key]
    while attempts and attempts[0] <= now - window_seconds:
        attempts.popleft()
    if len(attempts) >= limit:
        retry_after = max(1, int(window_seconds - (now - attempts[0]) + 0.999))
        raise LoginRateLimitError(retry_after)
    attempts.append(now)
