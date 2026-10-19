"""Grammar lessons: a short lesson for each grammar point the learner gets wrong most, written from their mistakes.

The learner's own messages decide which lessons there are (their most frequent grammar mistakes, recent ones
counting more) and what each one says about their habit. The rules, examples and quiz are new sentences, so a
lesson teaches the point beyond the learner's own cases. Lessons are written by the Update my lessons job, after
new words, and rewritten when a point's mistakes have grown a lot since. Each is data/grammar/<pattern>.json; the
raw answer is kept in data/inbox/raw-grammar/.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import llm, srs, store, vocab
from .config import BATCHES, GRAMMAR, INBOX, PATTERNS_FILE, PROMPTS
from .lessons import Card, LessonStore, Snapshot

CATEGORIES = ("verbs", "structure", "nouns", "words")   # not spelling & punctuation, and not tone
SKIP = ("word-choice",)        # vocabulary: the Words page covers it
MIN_MISTAKES = 3               # fewer isn't a habit yet
MAX_LESSONS = 12               # lessons for the points that need work most
HALF_LIFE_DAYS = 14            # a mistake from two weeks ago counts half as much as one from today
REWRITE_GROWTH = 1.5           # rewrite when a point has 1.5x the mistakes its lesson was written from (and 5 more)
MISTAKES_IN_PROMPT = 25
RAW = INBOX / "raw-grammar"
_KEY = re.compile(r"[a-z0-9][a-z0-9-]{0,60}")
_GAP = re.compile(r"_{2,}")

_STR = {"type": "string"}


def _items(**properties) -> dict:
    return {"type": "array", "items": {"type": "object", "properties": properties, "required": list(properties)}}


SCHEMA = {
    "type": "object",
    "properties": {
        "title": _STR,
        "summary": _STR,
        "summary_zh": _STR,
        "your_habit": _STR,
        "rules": _items(rule=_STR, example=_STR),
        "examples": _items(sentence=_STR, note=_STR),
        "watch_out": _items(wrong=_STR, right=_STR, why=_STR),
        "quiz": _items(sentence=_STR, answer=_STR, options={"type": "array", "items": _STR}, why=_STR),
        "tip": _STR,
        "tip_zh": _STR,
    },
    "required": ["title", "summary", "summary_zh", "your_habit", "rules", "examples", "watch_out", "quiz", "tip",
                 "tip_zh"],
}


# ---------- which points need a lesson ----------

def by_point(snap: Snapshot) -> dict[str, list[Card]]:
    """The learner's cards for each grammar point (a mistake pattern in a grammar category)."""
    points: dict[str, list[Card]] = {}
    for c in snap.cards:
        category = (snap.patterns.get(c.pattern) or {}).get("category") or "words"
        if category in CATEGORIES and c.pattern not in SKIP and _KEY.fullmatch(c.pattern):
            points.setdefault(c.pattern, []).append(c)
    return points


def mistakes(cards: list[Card]) -> int:
    return sum(len(c.examples) for c in cards)


def need(cards: list[Card], now_ms: int) -> float:
    """How much a point needs work now: every mistake counts, a recent one more (half after HALF_LIFE_DAYS)."""
    score = 0.0
    for c in cards:
        for e in c.examples:
            try:
                age_days = max(0, now_ms - srs.parse_ms(e.ts)) / srs.DAY
            except ValueError:
                age_days = 365.0
            score += 0.5 ** (age_days / HALF_LIFE_DAYS)
    return score


def ranked(snap: Snapshot, now_ms: int) -> list[tuple[str, list[Card]]]:
    """The grammar points made often enough to be a habit, the one that needs work most first."""
    points = [(key, cards) for key, cards in by_point(snap).items() if mistakes(cards) >= MIN_MISTAKES]
    return sorted(points, key=lambda kv: need(kv[1], now_ms), reverse=True)


def due(snap: Snapshot, now_ms: int, folder: Path = GRAMMAR) -> list[str]:
    """The points whose lesson should be written now: a top point without one, or with many new mistakes since."""
    keys = []
    for key, cards in ranked(snap, now_ms)[:MAX_LESSONS]:
        doc = read(folder, key)
        based_on = doc.get("based_on", 0) if doc else 0
        if doc is None or mistakes(cards) >= max(based_on * REWRITE_GROWTH, based_on + 5):
            keys.append(key)
    return keys


# ---------- one lesson ----------

def build_prompt(snap: Snapshot, key: str, cards: list[Card]) -> str:
    p = snap.patterns.get(key) or {}
    point = {"key": key, "title": p.get("title") or key, "rule": p.get("rule", ""), "mistakes": mistakes(cards)}
    shown, seen = [], set()
    for e in sorted((e for c in cards for e in c.examples), key=lambda e: e.ts, reverse=True):
        if e.located and store.norm(e.sentence) not in seen:
            seen.add(store.norm(e.sentence))
            shown.append({"sentence": e.sentence, "wrong": e.wrong, "right": e.right})
    template = (PROMPTS / "grammar.md").read_text(encoding="utf-8")
    return (template.replace("{POINT}", json.dumps(point, ensure_ascii=False))
            .replace("{MISTAKES}", json.dumps(shown[:MISTAKES_IN_PROMPT], ensure_ascii=False, indent=1)))


def _text(value) -> str:
    return store.squash(str(value or ""))


def _pair(w: dict) -> dict | None:
    wrong, right = _text(w.get("wrong")), _text(w.get("right"))
    if not wrong or not right or store.norm(wrong) == store.norm(right):
        return None
    return {"wrong": wrong, "right": right, "why": _text(w.get("why"))}


def _question(q: dict) -> dict | None:
    """A quiz question with exactly one gap, the answer and one or two wrong options."""
    sentence = _GAP.sub("___", _text(q.get("sentence")))
    answer = _text(q.get("answer"))
    options = vocab.distinct(q.get("options") or [], {answer})[:2]
    if sentence.count("___") != 1 or not answer or not options:
        return None
    return {"sentence": sentence, "answer": answer, "options": options, "why": _text(q.get("why"))}


def clean(answer: dict) -> dict | None:
    """The validated lesson, or None without its essentials (a title, a summary and a rule)."""
    rules = [{"rule": _text(r.get("rule")), "example": _text(r.get("example"))} for r in answer.get("rules") or []]
    lesson = {
        "title": _text(answer.get("title"))[:80],
        "summary": _text(answer.get("summary")),
        "summary_zh": _text(answer.get("summary_zh")),
        "your_habit": _text(answer.get("your_habit")),
        "rules": [r for r in rules if r["rule"]][:4],
        "examples": [{"sentence": _text(e.get("sentence")), "note": _text(e.get("note"))}
                     for e in answer.get("examples") or [] if _text(e.get("sentence"))][:8],
        "watch_out": [p for p in map(_pair, answer.get("watch_out") or []) if p][:4],
        "quiz": [q for q in map(_question, answer.get("quiz") or []) if q][:6],
        "tip": _text(answer.get("tip")),
        "tip_zh": _text(answer.get("tip_zh")),
    }
    return lesson if lesson["title"] and lesson["summary"] and lesson["rules"] else None


def write(snap: Snapshot, key: str, accounts=None, cancel=None, folder: Path = GRAMMAR) -> dict:
    """Ask Claude for the lesson on `key` and save it. Raises LLMError (invalid_output if it comes back incomplete)."""
    cards = by_point(snap).get(key, [])
    answer, _ = llm.ask_json(build_prompt(snap, key, cards), SCHEMA, tier="analysis", accounts=accounts, cancel=cancel)
    store.write_json(RAW / f"{key}.json", answer)
    lesson = clean(answer)
    if lesson is None:
        raise llm.LLMError("the lesson came back without a title, a summary or a rule", kind="invalid_output")
    doc = {"pattern": key, "written_at": store.now_iso(), "based_on": mistakes(cards), "lesson": lesson}
    store.write_json(folder / f"{key}.json", doc)
    return doc


# ---------- the saved lessons ----------

def read(folder: Path, key: str) -> dict | None:
    """The saved lesson for `key`, or None (no lesson, a broken file, or a key that isn't a pattern name)."""
    if not _KEY.fullmatch(key):
        return None
    try:
        doc = json.loads((folder / f"{key}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) and isinstance(doc.get("lesson"), dict) else None


def read_all(folder: Path = GRAMMAR) -> dict[str, dict]:
    """Every saved lesson, by pattern."""
    docs = {}
    for path in sorted(folder.glob("*.json")):
        doc = read(folder, path.stem)
        if doc:
            docs[path.stem] = doc
    return docs


# ---------- the update ----------

def snapshot() -> Snapshot:
    return LessonStore(BATCHES, PATTERNS_FILE).snapshot()


def write_lessons(snap: Snapshot, keys: list[str], parallel: int = 2, accounts=None, cancel=None, on_done=None) -> int:
    """Write the lessons for `keys` (usually `due(...)`). Returns how many were written."""
    return llm.each(keys, lambda key: write(snap, key, accounts, cancel), label=lambda key: f"grammar lesson {key}",
                    parallel=parallel, cancel=cancel, on_done=on_done)


def rebuild_all(folder: Path = GRAMMAR) -> int:
    """Re-validate every saved lesson from its raw answer (no model calls)."""
    count = 0
    for raw in sorted(RAW.glob("*.json")):
        doc = read(folder, raw.stem)
        lesson = clean(json.loads(raw.read_text(encoding="utf-8")))
        if doc and lesson:
            doc["lesson"] = lesson
            store.write_json(folder / raw.name, doc)
            count += 1
    return count
