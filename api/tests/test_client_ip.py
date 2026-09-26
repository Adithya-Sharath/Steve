"""Real client IP behind proxies (D31): forwarding headers are trusted only with TRUST_PROXY=true."""

import pytest
from fastapi import Request
from test_api import MANGLISH, _flow

from app.clientip import client_ip
from app.settings import settings

PEER = "10.0.0.7"


def req(headers: dict[str, str] | None = None, peer: str | None = PEER) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "method": "GET", "path": "/", "headers": raw, "client": (peer, 5555) if peer else None})


@pytest.fixture(autouse=True)
def defaults(monkeypatch):
    monkeypatch.setattr(settings, "trust_proxy", False)
    monkeypatch.setattr(settings, "trusted_proxies", [])


@pytest.mark.parametrize(
    "headers",
    [
        {"X-Forwarded-For": "6.6.6.6"},
        {"CF-Connecting-IP": "6.6.6.6"},
        {"X-Forwarded-For": "6.6.6.6, 7.7.7.7", "CF-Connecting-IP": "8.8.8.8"},
    ],
)
def test_headers_are_ignored_when_proxy_is_not_trusted(headers):
    """Anyone can send these headers; believing them would let a client pick its own rate-limit bucket."""
    assert client_ip(req(headers)) == PEER


def test_no_client_at_all_is_still_a_string():
    assert client_ip(req(peer=None)) == "unknown"


class TestTrustedProxy:
    @pytest.fixture(autouse=True)
    def on(self, monkeypatch):
        monkeypatch.setattr(settings, "trust_proxy", True)

    def test_cloudflare_header_wins(self):
        assert client_ip(req({"CF-Connecting-IP": "203.0.113.9", "X-Forwarded-For": "6.6.6.6, 198.51.100.4"})) == "203.0.113.9"

    def test_invalid_cloudflare_header_is_ignored(self):
        assert client_ip(req({"CF-Connecting-IP": "not-an-ip", "X-Forwarded-For": "198.51.100.4"})) == "198.51.100.4"

    def test_rightmost_entry_is_the_client_as_seen_by_our_proxy(self):
        # a spoofed left part ("6.6.6.6") is what the client wrote; the right-most was appended by our proxy
        assert client_ip(req({"X-Forwarded-For": "6.6.6.6, 203.0.113.9"})) == "203.0.113.9"

    def test_a_spoofed_prefix_cannot_beat_the_proxy(self):
        assert client_ip(req({"X-Forwarded-For": "1.1.1.1, 2.2.2.2, 203.0.113.9"})) == "203.0.113.9"

    def test_known_extra_proxies_are_skipped_from_the_right(self, monkeypatch):
        monkeypatch.setattr(settings, "trusted_proxies", ["198.51.100.0/24", "192.0.2.5"])
        assert client_ip(req({"X-Forwarded-For": "6.6.6.6, 203.0.113.9, 198.51.100.4, 192.0.2.5"})) == "203.0.113.9"

    def test_all_hops_trusted_falls_back_to_the_peer(self, monkeypatch):
        monkeypatch.setattr(settings, "trusted_proxies", ["198.51.100.0/24"])
        assert client_ip(req({"X-Forwarded-For": "198.51.100.4, 198.51.100.9"})) == PEER

    def test_garbage_where_a_proxy_should_have_written_an_address_stops_the_walk(self):
        # never fall through to the (client-controlled) left side
        assert client_ip(req({"X-Forwarded-For": "6.6.6.6, banana"})) == PEER

    def test_ports_ipv6_and_whitespace(self):
        assert client_ip(req({"X-Forwarded-For": " 203.0.113.9:4711 "})) == "203.0.113.9"
        assert client_ip(req({"X-Forwarded-For": "[2001:db8::1]:443"})) == "2001:db8::1"
        assert client_ip(req({"X-Forwarded-For": "2001:db8::2"})) == "2001:db8::2"

    def test_no_headers_uses_the_peer(self):
        assert client_ip(req()) == PEER

    def test_a_bad_trusted_proxies_entry_does_not_crash(self, monkeypatch):
        monkeypatch.setattr(settings, "trusted_proxies", ["nonsense", "198.51.100.0/24"])
        assert client_ip(req({"X-Forwarded-For": "203.0.113.9, 198.51.100.4"})) == "203.0.113.9"


def test_the_reply_rate_limit_buckets_by_the_real_ip(client, monkeypatch):
    """Behind a trusted proxy two visitors have their own allowance, and one visitor cannot dodge it with a header."""
    monkeypatch.setattr(settings, "reply_rate_limit", 1)
    monkeypatch.setattr(settings, "trust_proxy", True)
    _, _, conf = _flow(client)
    url = f"/r/{conf['reader_token']}/reply"

    def post(ip: str) -> int:
        return client.post(url, data={"text": MANGLISH}, headers={"CF-Connecting-IP": ip}).status_code

    assert post("203.0.113.1") == 200
    assert post("203.0.113.1") == 429  # same visitor
    assert post("203.0.113.2") == 200  # a different visitor
    monkeypatch.setattr(settings, "trust_proxy", False)
    assert post("203.0.113.3") == 200  # header ignored: everyone is the socket peer, one shared bucket ...
    assert post("203.0.113.4") == 429  # ... so changing the header does not buy a new allowance
