"""In-memory clarify state for Decode (D45).

When a decode leaves a clarifying question open, the ORIGINAL TEXT (never audio) and the answers so far are kept here, keyed by an opaque id and by the
worker, so `POST /decode/clarify` can re-run the decoder with the answer. Rules:

* memory only: never written to disk, a database or a log;
* gone after `CLARIFY_TTL_SECONDS` (default 10 minutes; each answer renews it) and as soon as every question is answered;
* an id works only for the worker that made it (anyone else gets the same "expired" answer as for an unknown id, so ids cannot be probed);
* bounded: at most `MAX_PER_WORKER` open per worker and `MAX_TOTAL` overall (oldest evicted first).
"""

from __future__ import annotations

import secrets
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field

from ..settings import settings

MAX_PER_WORKER = 10
MAX_TOTAL = 5000


@dataclass
class Session:
    worker: str
    text: str
    accent_hint: str | None
    path: str  # typed | voice
    reply_language: str | None
    resolved: dict[int, str | None] = field(default_factory=dict)
    expires: float = 0.0


class ClarifyStore:
    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self.clock = clock
        self._items: OrderedDict[str, Session] = OrderedDict()
        self._lock = threading.Lock()

    def _sweep(self, now: float) -> None:
        for k in [k for k, s in self._items.items() if s.expires <= now]:
            del self._items[k]

    def create(self, s: Session) -> str:
        now = self.clock()
        with self._lock:
            self._sweep(now)
            mine = [k for k, v in self._items.items() if v.worker == s.worker]
            for k in mine[: max(0, len(mine) - MAX_PER_WORKER + 1)]:
                del self._items[k]
            while len(self._items) >= MAX_TOTAL:
                self._items.popitem(last=False)
            s.expires = now + settings.clarify_ttl_seconds
            key = secrets.token_urlsafe(12)
            self._items[key] = s
            return key

    def get(self, key: str, worker: str) -> Session | None:
        now = self.clock()
        with self._lock:
            self._sweep(now)
            s = self._items.get(key)
            if s is None or not secrets.compare_digest(s.worker, worker):
                return None
            s.expires = now + settings.clarify_ttl_seconds  # each answer renews the 10 minutes
            return s

    def delete(self, key: str) -> None:
        with self._lock:
            self._items.pop(key, None)

    def count(self) -> int:
        with self._lock:
            self._sweep(self.clock())
            return len(self._items)

    def reset(self) -> None:
        with self._lock:
            self._items.clear()


store = ClarifyStore()
