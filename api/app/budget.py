"""Daily spending caps on the two paid / quota-limited services (D33).

    LLM_DAILY_CAP (default 200)  Gemini fact-suggestion calls per UTC day, across all users
    STT_DAILY_CAP (default 300)  Sarvam speech-to-text calls per UTC day, across all users

A cap is a global safety net against a bill or a quota surprise, on top of the per-IP rate limits. `0` blocks the service
entirely (a kill switch); a negative value means unlimited. A call is counted when it is *attempted* (a failed call may
still be billed), and the counter resets at 00:00 UTC. Counters live in this process: a restart starts a new day's budget
(so the real provider quota, not this counter, is the last line of defence).
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import UTC, date, datetime

from .settings import settings


def _utc_today() -> date:
    return datetime.now(UTC).date()


class DailyBudget:
    def __init__(self, cap: Callable[[], int], today: Callable[[], date] = _utc_today):
        self._cap = cap
        self._today = today
        self._day: date | None = None
        self._used = 0
        self._lock = threading.Lock()

    def _roll(self) -> None:
        today = self._today()
        if today != self._day:
            self._day, self._used = today, 0

    @property
    def cap(self) -> int:
        return self._cap()

    def try_spend(self) -> bool:
        """Use one call of today's budget. False (and nothing used) when the cap is reached."""
        with self._lock:
            self._roll()
            cap = self._cap()
            if 0 <= cap <= self._used:
                return False
            self._used += 1
            return True

    def remaining(self) -> int:
        """Calls left today; -1 when unlimited."""
        with self._lock:
            self._roll()
            cap = self._cap()
            return -1 if cap < 0 else max(0, cap - self._used)

    def reset(self) -> None:
        with self._lock:
            self._day, self._used = None, 0


llm_budget = DailyBudget(lambda: settings.llm_daily_cap)
stt_budget = DailyBudget(lambda: settings.stt_daily_cap)


def snapshot() -> dict[str, int]:
    """Numbers only, for /health."""
    return {
        "llm_cap": llm_budget.cap,
        "llm_remaining": llm_budget.remaining(),
        "stt_cap": stt_budget.cap,
        "stt_remaining": stt_budget.remaining(),
    }
