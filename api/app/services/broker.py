"""Tiny in-process pub/sub for Server-Sent Events (one queue per subscriber)."""

from __future__ import annotations

import asyncio
from collections import defaultdict


class Broker:
    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue]] = defaultdict(set)

    def subscribe(self, key: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subs[key].add(q)
        return q

    def unsubscribe(self, key: str, q: asyncio.Queue) -> None:
        self._subs[key].discard(q)
        if not self._subs[key]:
            self._subs.pop(key, None)

    def publish(self, key: str, event: dict) -> int:
        n = 0
        for q in list(self._subs.get(key, ())):
            try:
                q.put_nowait(event)
                n += 1
            except asyncio.QueueFull:
                pass
        return n


broker = Broker()
