"""CSAT: the one-question survey sent after a ticket is resolved (1 = very unhappy ... 5 = very happy)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from casework.models import Ticket


@dataclass(frozen=True)
class CsatSummary:
    responses: int
    average: float | None
    satisfied_share: float | None  # share of 4s and 5s, the number the board pack uses


def summarize(tickets: list[Ticket]) -> CsatSummary:
    scores = [t.csat for t in tickets if t.csat is not None]
    if not scores:
        return CsatSummary(0, None, None)
    return CsatSummary(
        responses=len(scores),
        average=round(sum(scores) / len(scores), 2),
        satisfied_share=round(sum(1 for s in scores if s >= 4) / len(scores), 3),
    )


def by_category(tickets: list[Ticket]) -> dict[str, CsatSummary]:
    groups: dict[str, list[Ticket]] = defaultdict(list)
    for t in tickets:
        groups[t.category].append(t)
    return {category: summarize(group) for category, group in sorted(groups.items())}


def record_response(score: int) -> int:
    if not 1 <= int(score) <= 5:
        raise ValueError(f"CSAT score must be 1-5, got {score!r}")
    return int(score)
