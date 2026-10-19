"""What the app's pages show, computed from the lessons (a Snapshot) and the learner's progress.

Ported from the original app's views (Today, Patterns, Words, Messages, Progress), with these fixes:
- the focus pattern looks at the last 7 days (then all time), typos and style notes excluded;
- the daily new-card allowance counts grammar cards only;
- "latest chat" means the latest Claude Code chat (not a message checked in the app).
Every function returns plain dicts shaped like the API's response models.
"""

from __future__ import annotations

import base64
import binascii
import json
import math
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from . import grammar, srs
from .lessons import WORD_GROUPS, Card, Message, Snapshot, Word
from .srs import DAY, MASTERED, State


@dataclass(slots=True)
class View:
    """Everything a page needs: the lessons, the learner's progress, and the moment it is computed for."""
    snap: Snapshot
    states: dict[str, State]
    days: dict[str, dict]           # local day -> {answered, correct, seconds}
    rounds: int
    settings: dict
    now_ms: int
    cards_new_today: int = 0        # grammar cards first answered today
    sec_per_item: float = 15.0
    _due_cards: list[Card] | None = field(default=None, repr=False)

    def state(self, item_id: str) -> State | None:
        return self.states.get(item_id)

    def due_cards(self) -> list[Card]:
        if self._due_cards is None:
            self._due_cards = [c for c in self.snap.cards if srs.is_due(self.states.get(c.id), self.now_ms)]
        return self._due_cards

    def due_words(self) -> list[Word]:
        return [w for w in self.snap.words if srs.is_due(self.states.get(w.id), self.now_ms)]

    def fresh_cards(self) -> list[Card]:
        return [c for c in self.snap.cards if c.id not in self.states]


# ---------- small helpers ----------

def _iso_ms(ms: int | None) -> str | None:
    return datetime.fromtimestamp(ms / 1000).astimezone().isoformat(timespec="seconds") if ms else None


def _local_day(iso: str) -> str:
    try:
        return srs.day_key(srs.parse_ms(iso))
    except (ValueError, TypeError):
        return (iso or "")[:10]


def _mastery(view: View, cards: list[Card]) -> dict:
    mastered = learning = 0
    for c in cards:
        st = view.states.get(c.id)
        if st is None:
            continue
        if st.box >= MASTERED:
            mastered += 1
        else:
            learning += 1
    return {"total": len(cards), "mastered": mastered, "learning": learning, "new": len(cards) - mastered - learning}


def _example(card: Card) -> dict:
    ex = card.examples[-1]
    return {"sentence": ex.sentence, "wrong": ex.wrong, "right": ex.right, "corrected": ex.corrected}


def _page(items: list, page: int, page_size: int) -> tuple[list, int, int]:
    pages = max(1, math.ceil(len(items) / page_size))
    page = min(max(1, page), pages)
    start = (page - 1) * page_size
    return items[start:start + page_size], page, pages


# ---------- counts, streak, today ----------

def new_left_today(view: View) -> int:
    return max(0, int(view.settings.get("new_per_day", 12)) - view.cards_new_today)


def counts(view: View) -> dict:
    fresh = view.fresh_cards()
    left = new_left_today(view)
    snap = view.snap
    return {
        "cards_due": len(view.due_cards()),
        "words_due": len(view.due_words()),
        "new_left_today": left,
        "new_cards_ready": min(len(fresh), left),
        "cards_total": len(snap.cards),
        "words_total": len(snap.words),
        "cards_mastered": sum(1 for c in snap.cards if (view.states.get(c.id) or _NEVER).box >= MASTERED),
        "words_mastered": sum(1 for w in snap.words if (view.states.get(w.id) or _NEVER).box >= MASTERED),
    }


_NEVER = State(box=0, due_ms=0, seen=0, right=0, wrong=0, lapses=0, first_ms=0, last_ms=0)


def streak(days: dict[str, dict], now_ms: int) -> int:
    """Days in a row with at least one answer, counting back from today (or from yesterday before today's first)."""
    n = 0
    t = now_ms
    if not (days.get(srs.day_key(t)) or {}).get("answered"):
        t -= DAY
    while (days.get(srs.day_key(t)) or {}).get("answered"):
        n += 1
        t -= DAY
    return n


def today_totals(days: dict[str, dict], now_ms: int) -> dict:
    d = days.get(srs.day_key(now_ms)) or {}
    return {"answered": d.get("answered", 0), "correct": d.get("correct", 0), "seconds": d.get("seconds", 0)}


# ---------- home ----------

def practice_summary(view: View) -> dict:
    due = len(view.due_cards())
    new = min(len(view.fresh_cards()), new_left_today(view))
    size = int(view.settings.get("round_size", 8))
    planned = min(size, due + new) if due + new else size
    return {
        "mode": "review" if due else "new" if new else "extra",
        "cards_due": due,
        "new_cards": new,
        "words_due": len(view.due_words()),
        "round_size": size,
        "est_minutes": max(1, round(planned * view.sec_per_item / 60)),
    }


def focus(view: View) -> dict | None:
    """The pattern to work on: most mistakes in the last 7 days (else of all time), typos and style aside."""
    since = view.now_ms - 7 * DAY
    recent: dict[str, int] = {}
    overall: dict[str, int] = {}
    for c in view.snap.cards:
        if c.severity in ("typo", "style"):
            continue
        overall[c.pattern] = overall.get(c.pattern, 0) + c.times
        n = 0
        for e in c.examples:
            try:
                if srs.parse_ms(e.ts) >= since:
                    n += 1
            except (ValueError, TypeError):
                pass
        if n:
            recent[c.pattern] = recent.get(c.pattern, 0) + n
    window, ranked = ("week", recent) if recent else ("all", overall)
    if not ranked:
        return None
    key, count = max(ranked.items(), key=lambda kv: kv[1])
    p = view.snap.patterns.get(key) or {}
    cards = [c for c in view.snap.cards if c.pattern == key]
    card = max(cards, key=lambda c: c.times) if cards else None
    return {
        "pattern": key, "title": view.snap.pattern_title(key), "rule": p.get("rule", ""), "rule_zh": p.get("rule_zh", ""),
        "window": window, "count": count, "example": _example(card) if card and card.examples else None,
    }


def latest_chat(view: View) -> dict | None:
    latest = next((m for m in view.snap.messages if m.source == "claude-code"), None)
    if latest is None:
        return None
    day = _local_day(latest.ts)
    same_day = [m for m in view.snap.messages if m.source == "claude-code" and _local_day(m.ts) == day]
    card_ids: dict[str, None] = {}
    for m in same_day:
        for cid in view.snap.cards_by_message.get(m.id, []):
            card_ids[cid] = None
    per_pattern: dict[str, int] = {}
    for cid in card_ids:
        c = view.snap.card_by_id.get(cid)
        if c:
            per_pattern[c.pattern] = per_pattern.get(c.pattern, 0) + 1
    top = sorted(per_pattern.items(), key=lambda kv: -kv[1])[:3]
    sample = next((m for m in same_day if m.issues > 0 and m.fixed), None)
    return {
        "day": day, "messages": len(same_day), "cards": len(card_ids),
        "top_patterns": [{"pattern": k, "title": view.snap.pattern_title(k), "count": n} for k, n in top],
        "sample": {"id": sample.id, "text": sample.text, "fixed": sample.fixed} if sample else None,
    }


def word_brief(view: View, w: Word) -> dict:
    st = view.states.get(w.id)
    return {
        "id": w.id, "kind": w.kind, "word": w.word, "pos": w.pos, "meaning": w.meaning, "meaning_zh": w.meaning_zh,
        "example": w.example, "wrote": list(w.wrote), "times": w.times, "last": w.last or None,
        "level": w.level or None, "rewrite": w.rewrite,
        "status": srs.status(st), "strength": srs.strength(st), "due_at": _iso_ms(st.due_ms) if st else None,
    }


def word_of_the_day(view: View) -> dict | None:
    """A word not mastered yet, the same all day: a new word when there are any, else one that isn't a typo."""
    words = view.snap.words
    if not words:
        return None
    learning = [w for w in words if (view.states.get(w.id) or _NEVER).box < MASTERED]
    pool = [w for w in learning if w.kind == "new"] or [w for w in learning if w.kind != "spelling"]
    pool = sorted(pool or words, key=lambda w: w.id)
    today = srs.day_key(view.now_ms)
    return word_brief(view, pool[zlib.crc32(today.encode()) % len(pool)])


def home(view: View) -> dict:
    return {
        "empty": not view.snap.cards,
        "practice": practice_summary(view),
        "focus": focus(view),
        "latest_chat": latest_chat(view),
        "word_of_the_day": word_of_the_day(view),
        "writing": writing_trend(view),
    }


# ---------- mistakes (patterns) ----------

def pattern_list(view: View) -> dict:
    snap = view.snap
    by_category: dict[str, list[dict]] = {}
    cards_by_pattern: dict[str, list[Card]] = {}
    for c in snap.cards:
        cards_by_pattern.setdefault(c.pattern, []).append(c)
    for key, cards in cards_by_pattern.items():
        category = (snap.patterns.get(key) or {}).get("category") or "words"
        by_category.setdefault(category, []).append({
            "key": key, "title": snap.pattern_title(key),
            "times": sum(c.times for c in cards),
            "last": max((c.last for c in cards if c.last), default="") or None,
            "mastery": _mastery(view, cards),
        })
    order = list(snap.categories)
    rank = {k: i for i, k in enumerate(order)}
    groups = []
    for cat in sorted(by_category, key=lambda k: rank.get(k, 99 + len(order))):
        info = snap.categories.get(cat) or {}
        groups.append({"key": cat, "title": info.get("title") or cat, "zh": info.get("zh", ""),
                       "patterns": sorted(by_category[cat], key=lambda r: -r["times"])})
    return {"categories": groups}


def card_row(view: View, c: Card) -> dict:
    st = view.states.get(c.id)
    ex = c.examples[-1]
    return {
        "id": c.id, "pattern": c.pattern, "severity": c.severity, "times": c.times, "last": c.last or None,
        "status": srs.status(st), "strength": srs.strength(st), "due_at": _iso_ms(st.due_ms) if st else None,
        "sentence": ex.sentence, "corrected": ex.corrected, "wrong": ex.wrong, "right": ex.right,
        "explain": c.explain, "explain_zh": c.explain_zh,
    }


def pattern_detail(view: View, key: str, page: int = 1, page_size: int = 20) -> dict | None:
    snap = view.snap
    p = snap.patterns.get(key)
    cards = [c for c in snap.cards if c.pattern == key]
    if p is None and not cards:
        return None
    p = p or {}
    cards.sort(key=lambda c: (c.times, c.last or ""), reverse=True)
    shown, page, pages = _page(cards, page, page_size)
    category, category_title = _category(snap, key)
    return {
        "key": key, "title": snap.pattern_title(key), "category": category, "category_title": category_title,
        "rule": p.get("rule", ""), "rule_zh": p.get("rule_zh", ""), "mastery": _mastery(view, cards),
        "more_examples": [{"wrong": e.get("wrong", ""), "right": e.get("right", "")} for e in p.get("examples") or []],
        "cards": [card_row(view, c) for c in shown], "total": len(cards), "page": page, "pages": pages,
    }


# ---------- grammar ----------

def grammar_list(view: View, docs: dict[str, dict]) -> dict:
    """The saved grammar lessons, the point that needs work most first, and how many top points have none yet."""
    snap = view.snap
    ranked = grammar.ranked(snap, view.now_ms)
    order = {key: i for i, (key, _) in enumerate(ranked)}
    points = grammar.by_point(snap)
    rows = []
    for key, doc in docs.items():
        cards = points.get(key, [])
        category, category_title = _category(snap, key)
        rows.append({
            "pattern": key, "title": doc["lesson"].get("title") or snap.pattern_title(key),
            "summary": doc["lesson"].get("summary", ""), "category": category, "category_title": category_title,
            "mistakes": grammar.mistakes(cards), "last": max((c.last for c in cards if c.last), default="") or None,
            "mastery": _mastery(view, cards),
        })
    rows.sort(key=lambda r: (order.get(r["pattern"], len(order)), -r["mistakes"]))
    return {"lessons": rows, "coming": sum(1 for key, _ in ranked[:grammar.MAX_LESSONS] if key not in docs)}


def grammar_lesson(view: View, key: str, doc: dict) -> dict:
    """One saved lesson, with the learner's latest real mistakes on the point."""
    snap = view.snap
    cards = sorted(grammar.by_point(snap).get(key, []), key=lambda c: c.last or "", reverse=True)
    category, category_title = _category(snap, key)
    return {
        **doc["lesson"],
        "pattern": key, "category": category, "category_title": category_title,
        "mistakes": grammar.mistakes(cards), "last": (cards[0].last or None) if cards else None,
        "mastery": _mastery(view, cards),
        "from_you": [_example(c) for c in cards if c.examples[-1].located][:4],
        "written_at": doc.get("written_at"),
    }


def _category(snap: Snapshot, pattern: str) -> tuple[str, str]:
    """A pattern's category key and title."""
    category = (snap.patterns.get(pattern) or {}).get("category") or "words"
    return category, (snap.categories.get(category) or {}).get("title") or category


# ---------- words ----------

def word_list(view: View, group: str, page: int = 1, page_size: int = 24) -> dict:
    """One of the Words page's lists (lessons.WORD_GROUPS): new words, or typos & fixes."""
    words = view.snap.words
    in_group = sorted((w for w in words if w.kind in WORD_GROUPS[group]), key=lambda w: (w.times, w.last or ""), reverse=True)
    shown, page, pages = _page(in_group, page, page_size)
    return {
        "group": group,
        "groups": [{"group": g, "count": sum(1 for w in words if w.kind in kinds)} for g, kinds in WORD_GROUPS.items()],
        "due": len(view.due_words()),
        "mastered": sum(1 for w in words if (view.states.get(w.id) or _NEVER).box >= MASTERED),
        "total": len(words),
        "words": [word_brief(view, w) for w in shown],
        "total_in_group": len(in_group), "page": page, "pages": pages,
    }


# ---------- messages ----------

def message_row(view: View, m: Message) -> dict:
    return {
        "id": m.id, "ts": m.ts, "day": _local_day(m.ts), "project": m.project or "chat",
        "source": "app" if m.source == "app" else "claude-code",
        "text": m.text, "fixed": m.fixed, "polished": m.polished, "words": m.words, "issues": m.issues,
    }


def _encode_cursor(m: Message) -> str:
    return base64.urlsafe_b64encode(f"{m.ts}|{m.id}".encode()).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[str, str]:
    raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
    ts, _, mid = raw.rpartition("|")
    if not mid:
        raise ValueError("bad cursor")
    return ts, mid


def message_page(view: View, filter: str = "mistakes", cursor: str | None = None, limit: int = 30) -> dict:
    """Newest first; `cursor` (from the previous page) continues after the last message shown.
    Raises ValueError for a cursor that can't be read."""
    ordered = sorted(view.snap.messages, key=lambda m: (m.ts, m.id), reverse=True)
    with_mistakes = [m for m in ordered if m.issues > 0]
    items = with_mistakes if filter == "mistakes" else ordered
    if cursor:
        try:
            after = _decode_cursor(cursor)
        except (ValueError, binascii.Error, UnicodeDecodeError) as e:
            raise ValueError("bad cursor") from e
        items = [m for m in items if (m.ts, m.id) < after]
    shown = items[:limit]
    return {
        "messages": [message_row(view, m) for m in shown],
        "next_cursor": _encode_cursor(shown[-1]) if len(items) > limit else None,
        "counts": {"mistakes": len(with_mistakes), "all": len(ordered)},
    }


# ---------- progress ----------

def _week_start(iso: str) -> datetime:
    d = datetime.fromtimestamp(srs.parse_ms(iso) / 1000)
    d = d.replace(hour=0, minute=0, second=0, microsecond=0)
    return d - timedelta(days=d.weekday())


def writing_trend(view: View) -> dict:
    """Mistakes per 100 words you wrote to Claude Code, by week (Monday start), last 12 weeks with 40+ words."""
    weeks: dict[datetime, dict] = {}
    for m in view.snap.messages:
        if m.source != "claude-code" or not m.words:
            continue
        try:
            w = _week_start(m.ts)
        except (ValueError, TypeError):
            continue
        rec = weeks.setdefault(w, {"words": 0, "issues": 0, "messages": 0})
        rec["words"] += m.words
        rec["issues"] += m.issues
        rec["messages"] += 1
    points = [
        {"week_start": w.strftime("%Y-%m-%d"), "per_100_words": round(100 * r["issues"] / r["words"], 2),
         "messages": r["messages"], "words": r["words"], "issues": r["issues"]}
        for w, r in sorted(weeks.items())[-12:] if r["words"] >= 40
    ]
    latest = points[-1]["per_100_words"] if points else None
    average = (sum(p["per_100_words"] for p in points[:-1]) / (len(points) - 1)) if len(points) >= 2 else None
    verdict = None
    if latest is not None and average is not None:
        verdict = "fewer" if latest < average * 0.9 else "more" if latest > average * 1.1 else "same"
    return {"points": points, "latest": latest, "average_before": round(average, 2) if average is not None else None,
            "verdict": verdict}


def progress(view: View) -> dict:
    snap = view.snap
    last7 = [view.days.get(srs.day_key(view.now_ms - i * DAY)) or {} for i in range(7)]
    a7 = sum(d.get("answered", 0) for d in last7)
    c7 = sum(d.get("correct", 0) for d in last7)
    practice = []
    for i in range(27, -1, -1):
        day = srs.day_key(view.now_ms - i * DAY)
        d = view.days.get(day) or {}
        practice.append({"day": day, "answered": d.get("answered", 0), "correct": d.get("correct", 0)})
    mastery = []
    for key, cat in snap.categories.items():
        cards = [c for c in snap.cards if ((snap.patterns.get(c.pattern) or {}).get("category") or "words") == key]
        if cards:
            mx = _mastery(view, cards)
            mastery.append({"key": key, "title": cat.get("title") or key, "zh": cat.get("zh", ""),
                            "total": mx["total"], "mastered": mx["mastered"], "learning": mx["learning"]})
    repeated = sorted((c for c in snap.cards if c.times > 1 and c.severity != "style"), key=lambda c: -c.times)[:10]
    c = counts(view)
    return {
        "kpis": {
            "streak": streak(view.days, view.now_ms),
            "right_pct_7d": round(100 * c7 / a7) if a7 else None,
            "cards_mastered": c["cards_mastered"], "cards_total": c["cards_total"],
            "words_mastered": c["words_mastered"], "words_total": c["words_total"],
            "answers_total": sum(d.get("answered", 0) for d in view.days.values()),
            "rounds": view.rounds,
        },
        "writing": writing_trend(view),
        "practice": practice,
        "mastery": mastery,
        "repeated": [
            {"card_id": r.id, "pattern": r.pattern, "pattern_title": snap.pattern_title(r.pattern), "wrong": r.wrong,
             "right": r.right, "times": r.times, "status": srs.status(view.states.get(r.id))}
            for r in repeated
        ],
    }


# ---------- the pipeline (capture and analysis) ----------

def pipeline_status(inbox: Path, snap: Snapshot) -> dict:
    """How the lesson pipeline is doing, read from its files in inbox/ (written by Update my lessons)."""
    captured: set[str] = set()
    try:
        with open(inbox / "messages.jsonl", encoding="utf-8") as f:
            for line in f:
                try:
                    captured.add(json.loads(line)["id"])
                except (ValueError, KeyError, TypeError):
                    continue
    except FileNotFoundError:
        pass
    try:
        analyzed = {line.strip() for line in (inbox / "analyzed.txt").read_text(encoding="utf-8").splitlines()}
    except FileNotFoundError:
        analyzed = set()
    lock = inbox / "run.lock"
    try:
        analyzing = (datetime.now().timestamp() - lock.stat().st_mtime) < 1800
    except FileNotFoundError:
        analyzing = False
    return {
        "captured": len(captured), "waiting": len(captured - analyzed), "batches": snap.batches,
        "app_lessons": snap.app_lessons, "analyzing": analyzing, "last_analysis_at": snap.last_batch_at or None,
    }
