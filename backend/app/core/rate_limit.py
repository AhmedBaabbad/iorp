from collections import defaultdict, deque
from time import monotonic

from ipaddress import ip_address, ip_network

from fastapi import Request

from app.core.config import settings

_attempts: dict[tuple[str, str], deque[float]] = defaultdict(deque)


class LoginRateLimitError(RuntimeError):
    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__("Too many login attempts.")


def _trusted_networks() -> list:
    """IORP_TRUSTED_PROXY_IPS: addresses, CIDR ranges or exact peer names of our own proxies (e.g. Traefik's and the
    web container's networks). "*" is never honoured: trusting everyone would let any client choose its address."""
    trusted = []
    for value in settings.trusted_proxy_ips.split(","):
        value = value.strip()
        if not value or value == "*":
            continue
        try:
            trusted.append(ip_network(value, strict=False))
        except ValueError:
            trusted.append(value)  # an exact peer name (e.g. a test client)
    return trusted


def _is_trusted(host: str, trusted: list) -> bool:
    try:
        address = ip_address(host)
    except ValueError:
        address = None
    return any(entry == host if isinstance(entry, str) else (address is not None and address in entry) for entry in trusted)


def get_client_ip(request: Request) -> str:
    """The client's address. Behind a chain of our proxies (Traefik → web → API) walk X-Forwarded-For from the right,
    skipping our proxies, and stop at the first hop that is not ours: entries further left may be forged by the
    client. Without a trusted direct peer the header is ignored."""
    direct_host = request.client.host if request.client else "unknown"
    networks = _trusted_networks()
    forwarded = request.headers.get("x-forwarded-for")
    if not forwarded or not _is_trusted(direct_host, networks):
        return direct_host
    hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
    for hop in reversed(hops):
        if not _is_trusted(hop, networks):
            return hop
    return hops[0] if hops else direct_host


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
