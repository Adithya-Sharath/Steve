"""In-memory sliding-window rate limits behind ONE reusable dependency factory (D32).

    Depends(limit("messages", per_minute=lambda: settings.rl_messages_per_min, per_day=lambda: settings.rl_messages_per_day))

* Keyed by client IP by default (see `clientip.client_ip`, which only believes proxy headers when TRUST_PROXY=true); pass
  `key=` for another key (the sender-key hash, `token+ip`, ...).
* A hit is recorded only when it is ALLOWED, and only if every rule of the call passes, so rejected requests never use up
  the allowance and a minute rule cannot be starved by a day rule.
* Limits are read through callables at request time, so they come from env-driven settings and tests can change them.
* Blocked: `429` with a friendly `detail` and a `Retry-After` header (whole seconds, at least 1).
* State lives in this process (a restart or a second worker starts from zero): it is an abuse brake, not billing.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request

from .clientip import client_ip

DAY = 86_400.0
MINUTE = 60.0
_SWEEP_EVERY = 500  # allowed hits between clean-ups of keys nobody has used for a day


@dataclass(frozen=True)
class Rule:
    limit: int
    window: float  # seconds


def too_many(retry_after: float, window: float) -> HTTPException:
    seconds = max(1, math.ceil(retry_after))
    if window >= DAY / 2:
        detail = "You have reached today's limit for this. Please try again later."
    elif seconds <= 60:
        detail = f"That was a lot of requests in a short time. Please wait {seconds} second{'s' if seconds != 1 else ''} and try again."
    else:
        detail = f"Too many requests. Please try again in about {math.ceil(seconds / 60)} minutes."
    return HTTPException(429, detail, headers={"Retry-After": str(seconds)})


class SlidingWindowLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self.clock = clock
        self._hits: dict[tuple[str, str], deque[float]] = {}
        self._lock = threading.Lock()
        self._allowed = 0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
            self._allowed = 0

    def check(self, bucket: str, key: str, rules: list[Rule]) -> tuple[float, float] | None:
        """Record one hit if every rule allows it. Otherwise record nothing and return (retry_after_s, window_s)."""
        rules = [r for r in rules if r.limit > 0]  # a limit of 0 or less means "not enforced"
        if not rules:
            return None
        now = self.clock()
        longest = max(r.window for r in rules)
        with self._lock:
            q = self._hits.setdefault((bucket, key), deque())
            while q and now - q[0] >= longest:
                q.popleft()
            worst: tuple[float, float] | None = None
            for r in rules:
                inside = [t for t in q if now - t < r.window]
                if len(inside) >= r.limit:
                    # allowed again once the hit at this index leaves the window
                    retry = inside[len(inside) - r.limit] + r.window - now
                    if worst is None or retry > worst[0]:
                        worst = (retry, r.window)
            if worst is not None:
                return worst
            q.append(now)
            self._allowed += 1
            if self._allowed % _SWEEP_EVERY == 0:
                self._sweep(now)
            return None

    def _sweep(self, now: float) -> None:
        dead = [k for k, q in self._hits.items() if not q or now - q[-1] >= DAY]
        for k in dead:
            del self._hits[k]

    def enforce(self, bucket: str, key: str, rules: list[Rule]) -> None:
        blocked = self.check(bucket, key, rules)
        if blocked:
            raise too_many(*blocked)


limiter = SlidingWindowLimiter()


def limit(
    bucket: str,
    *,
    per_minute: Callable[[], int] | None = None,
    per_day: Callable[[], int] | None = None,
    key: Callable[[Request], str] = client_ip,
) -> Callable[[Request], None]:
    """Build a FastAPI dependency that enforces per-minute and/or per-day limits for `bucket`."""

    def dependency(request: Request) -> None:
        rules = []
        if per_minute:
            rules.append(Rule(per_minute(), MINUTE))
        if per_day:
            rules.append(Rule(per_day(), DAY))
        limiter.enforce(bucket, key(request), rules)

    dependency.__name__ = f"rate_limit_{bucket}"
    return dependency


def limit_sender(bucket: str, *, per_day: Callable[[], int]) -> Callable[..., None]:
    """Per sender key (its hash), not per IP: one browser cannot spread its allowance across many addresses."""
    from .auth import sender_hash

    def dependency(owner: str = Depends(sender_hash)) -> None:
        limiter.enforce(bucket, owner, [Rule(per_day(), DAY)])

    dependency.__name__ = f"rate_limit_{bucket}"
    return dependency


# Routes that have their own, stricter (or different) limit are exempt from the catch-all below.
SPECIFIC_ROUTES = {
    ("POST", "/messages"),
    ("POST", "/r/{token}/reply"),
    ("POST", "/check"),
    ("POST", "/analyze"),
    ("POST", "/demo/seed"),
}


def default_ip_limit(request: Request) -> None:
    """Catch-all: `RL_DEFAULT_PER_MIN` (120) per IP for every route without a specific limit."""
    from .settings import settings

    route = request.scope.get("route")
    if (request.method, getattr(route, "path", None)) in SPECIFIC_ROUTES:
        return
    limiter.enforce("default", client_ip(request), [Rule(settings.rl_default_per_min, MINUTE)])
