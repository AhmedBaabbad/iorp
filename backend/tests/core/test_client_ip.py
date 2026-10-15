"""PHASE-4: the client's address behind our proxy chain (Traefik → web → API), never one a client can choose."""
from types import SimpleNamespace

import pytest

from app.core import rate_limit
from app.core.config import settings


def request(peer, forwarded=None):
    headers = {"x-forwarded-for": forwarded} if forwarded else {}
    return SimpleNamespace(client=SimpleNamespace(host=peer), headers=headers)


@pytest.fixture(autouse=True)
def proxies(monkeypatch):
    # Traefik on 172.30.0.0/24, the web container on 172.31.0.0/24
    monkeypatch.setattr(settings, "trusted_proxy_ips", "172.30.0.0/24,172.31.0.0/24")


def test_the_real_client_behind_two_of_our_proxies():
    # Traefik adds the client; the web server adds Traefik; the API is reached from the web container.
    assert rate_limit.get_client_ip(request("172.31.0.5", "203.0.113.7, 172.30.0.2")) == "203.0.113.7"


def test_a_forged_left_entry_is_ignored():
    # The client sent "1.1.1.1" itself; Traefik appended the real address.
    assert rate_limit.get_client_ip(request("172.31.0.5", "1.1.1.1, 203.0.113.7, 172.30.0.2")) == "203.0.113.7"


def test_an_untrusted_peer_cannot_choose_its_address():
    assert rate_limit.get_client_ip(request("198.51.100.9", "10.0.0.1")) == "198.51.100.9"


@pytest.mark.parametrize("value", ["*", "not-an-address", ""])
def test_wildcards_and_garbage_trust_nobody(monkeypatch, value):
    monkeypatch.setattr(settings, "trusted_proxy_ips", value)
    assert rate_limit.get_client_ip(request("172.31.0.5", "203.0.113.7")) == "172.31.0.5"


def test_a_single_trusted_proxy_still_works():
    assert rate_limit.get_client_ip(request("172.30.0.2", "203.0.113.7")) == "203.0.113.7"
