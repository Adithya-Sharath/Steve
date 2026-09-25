"""Negation scope, per language.

English / Tagalog / Arabizi put the negator BEFORE what it negates ("don't stop", "huwag itigil", "ma waqqif").
Malayalam and Hindi/Urdu often put it AFTER or between ("nirthanam venda", "band mat karo", "do goli nahi leni"),
so their scope is bidirectional. Each negator claims exactly one target: the closest one in scope.
Some lexicon words carry their own negation (`negates: true`, e.g. Malayalam "nirthanda" = "don't stop").
"""

from __future__ import annotations

from dataclasses import dataclass

from .matcher import Ctx, Match


@dataclass(frozen=True)
class Scope:
    both: bool  # may the negator reach BACKWARDS to a target that came before it?
    window: int  # max content-token distance
    prefer: str  # on a tie: "before" (target precedes the negator) or "after"


SCOPES: dict[str, Scope] = {
    "en": Scope(both=False, window=3, prefer="after"),
    "tl": Scope(both=False, window=3, prefer="after"),
    "ar": Scope(both=False, window=3, prefer="after"),
    "ml": Scope(both=True, window=3, prefer="before"),
    "hi": Scope(both=True, window=3, prefer="after"),
}
DEFAULT_SCOPE = Scope(both=False, window=3, prefer="after")


def negators(ctx: Ctx) -> list[Match]:
    return [m for m in ctx.matches if m.category == "negation"]


def assign(ctx: Ctx, targets: list[tuple[int, int]]) -> dict[int, Match]:
    """targets: (first_token_idx, last_token_idx). Returns {target_index: negator_match}."""
    result: dict[int, Match] = {}
    best_dist: dict[int, int] = {}
    for neg in negators(ctx):
        scope = SCOPES.get(neg.lang, DEFAULT_SCOPE)
        choice: tuple[tuple[int, int], int] | None = None
        for ti, (a, b) in enumerate(targets):
            if a <= neg.j and neg.i <= b:
                continue  # negator sits inside the target itself
            if ctx.tokens[a].sent != ctx.tokens[neg.i].sent:
                continue
            if b < neg.i:
                if not scope.both:
                    continue
                dist, direction = ctx.cidx[neg.i] - ctx.cidx[b], "before"
            else:
                dist, direction = ctx.cidx[a] - ctx.cidx[neg.j], "after"
            if dist > scope.window:
                continue
            key = (dist, 0 if direction == scope.prefer else 1)
            if choice is None or key < choice[0]:
                choice = (key, ti)
        if choice is not None:
            ti = choice[1]
            if ti not in result or choice[0][0] < best_dist[ti]:
                result[ti] = neg
                best_dist[ti] = choice[0][0]
    return result
