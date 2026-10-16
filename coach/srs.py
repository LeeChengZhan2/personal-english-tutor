"""Spaced repetition, as in the original app: a right answer moves a card up one box, a wrong one sends it
back to box 1. Box n comes back after INTERVALS[n]; box 5 (16 days) and up counts as mastered."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import datetime

MIN = 60_000
DAY = 86_400_000
INTERVALS = (0, 10 * MIN, DAY, 3 * DAY, 7 * DAY, 16 * DAY, 35 * DAY, 90 * DAY)
MAX_BOX = len(INTERVALS) - 1
MASTERED = 5
SEV_WEIGHT = {"error": 3, "unnatural": 2, "style": 1, "typo": 1}


@dataclass(slots=True, frozen=True)
class State:
    box: int
    due_ms: int
    seen: int
    right: int
    wrong: int
    lapses: int
    first_ms: int
    last_ms: int


def grade(prev: State | None, correct: bool, now_ms: int) -> State:
    """The card's state after one answer (the original app's grade())."""
    st = prev or State(box=0, due_ms=0, seen=0, right=0, wrong=0, lapses=0, first_ms=now_ms, last_ms=now_ms)
    if correct:
        box = min(st.box + 1, MAX_BOX)
        st = replace(st, box=box, due_ms=now_ms + INTERVALS[box], right=st.right + 1)
    else:
        st = replace(st, box=1, due_ms=now_ms + INTERVALS[1], wrong=st.wrong + 1, lapses=st.lapses + 1)
    return replace(st, seen=st.seen + 1, last_ms=now_ms, first_ms=st.first_ms or now_ms)


def is_due(state: State | None, now_ms: int) -> bool:
    """Seen before and its time has come (a card never answered is new, not due)."""
    return state is not None and state.due_ms <= now_ms


def status(state: State | None) -> str:
    if state is None:
        return "new"
    return "mastered" if state.box >= MASTERED else "learning"


def strength(state: State | None) -> int:
    """0-5 for the strength dots: how far the card is on its way to mastered."""
    return 0 if state is None else min(state.box, MASTERED)


def priority(severity: str, times: int, last_iso: str, now_ms: int) -> float:
    """New cards worth learning first: serious, repeated and recent mistakes."""
    try:
        days = (now_ms - parse_ms(last_iso)) / DAY if last_iso else 99
    except ValueError:
        days = 99
    return SEV_WEIGHT.get(severity, 1) * (1 + math.log2(1 + (times or 1))) + max(0.0, 3 - days / 7)


def parse_ms(iso: str) -> int:
    """Epoch milliseconds of an ISO timestamp ('Z' or an offset)."""
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)


def day_key(ms: int) -> str:
    """The local calendar day of a moment, YYYY-MM-DD (the day used for streaks and daily stats)."""
    return datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d")


def now_ms() -> int:
    return int(datetime.now().timestamp() * 1000)
