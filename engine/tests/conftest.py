import pytest

from samjha_engine import Status, check_reply


def mk(id, type, value, unit=None, label=""):
    return {"id": id, "type": type, "value": value, "unit": unit, "label": label or str(value)}


def cond(id, trigger, action, text=""):
    return mk(id, "condition", {"trigger": trigger, "action": action, "text": text or f"{action} if {trigger}"})


@pytest.fixture
def rx_facts():
    """Scenario 1 (pharmacy) as gold facts."""
    return [
        mk("dose", "dose", 2, "tablet", "2 tablets"),
        mk("timing", "timing", "after_food", None, "after food"),
        mk("freq", "frequency", 2, None, "twice a day"),
        mk("dur", "duration", 5, "day", "5 days"),
        cond("rash", "rash", "stop", "stop if rash"),
    ]


@pytest.fixture
def run():
    def _run(facts, reply, lang_hint=None):
        return {r.fact_id: r for r in check_reply(facts, reply, lang_hint)}

    return _run


def statuses(results):
    return {k: v.status for k, v in results.items()}


U, W, M, N, C = Status.understood, Status.wrong, Status.missing, Status.negated, Status.unclear
