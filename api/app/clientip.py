"""The caller's IP address, for rate limits. Behind a reverse proxy the socket peer is the PROXY, so every visitor would
share one bucket; the real address is in a header. But those headers are written by the client too, so they are trusted
only when the operator says a proxy really sits in front (TRUST_PROXY=true). Otherwise they are ignored (spoofing, D31).

With TRUST_PROXY=true:
  1. `CF-Connecting-IP` (set by Cloudflare, including `cloudflared` tunnels) wins when present and valid;
  2. else `X-Forwarded-For`: every proxy appends the address it saw, so the RIGHT-MOST entries were written by our own
     infrastructure and the left-most by the client. We walk from the right, skip addresses listed in TRUSTED_PROXIES
     (a comma list of IPs/CIDRs for extra hops such as a CDN), and take the first one that is not trusted;
  3. anything malformed, or no header at all, falls back to the socket peer.
"""

from __future__ import annotations

import ipaddress

from fastapi import Request

from .settings import settings

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


def _parse(raw: str | None) -> IPAddress | None:
    """A clean IP from a header token (tolerates `1.2.3.4:5678` and `[::1]:80`); None if it is not an IP."""
    if not raw:
        return None
    s = raw.strip()
    if s.startswith("["):
        s = s[1:].split("]", 1)[0]
    elif s.count(":") == 1:  # ipv4:port (a bare IPv6 has several colons)
        s = s.split(":", 1)[0]
    try:
        return ipaddress.ip_address(s)
    except ValueError:
        return None


def _trusted_networks() -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    nets = []
    for item in settings.trusted_proxies:
        try:
            nets.append(ipaddress.ip_network(item, strict=False))
        except ValueError:
            continue  # a typo in TRUSTED_PROXIES must not crash requests; that hop just counts as untrusted
    return nets


def client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    if not settings.trust_proxy:
        return peer  # never read forwarding headers unless the operator opted in
    cf = _parse(request.headers.get("cf-connecting-ip"))
    if cf is not None:
        return str(cf)
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        trusted = _trusted_networks()
        for part in reversed(forwarded.split(",")):
            ip = _parse(part)
            if ip is None:
                break  # garbage where a proxy should have written an address: do not look further left
            if any(ip in net for net in trusted):
                continue
            return str(ip)
    return peer
