"""Word rounds: which words a round brings in, how each one is asked, and recording the answers.

A port of the original app's buildWordRound() and wordExercise(), with these changes:
- the plain round (no list chosen) brings in new words first, with only a few typos & fixes;
- a new word gets harder as it is learned: choose its meaning, then choose it for a gap in the learner's own
  sentence (said better) and in another sentence, then type it (unless the learner practises tap-only);
- a gap is cut only where the word stands whole, so "trim" is never cut out of "trimmed".
A round is saved in the sessions table with everything it asks, and each answer is checked against it.
Every function returns plain dicts shaped like the API's response models.
"""

from __future__ import annotations

import math
import random
import re
import secrets
import sqlite3

from . import db, srs, store
from .insights import View, iso_ms, word_brief
from .lessons import WORD_GROUPS, Word
from .srs import State
from .vocab import distinct

MAX_OPTIONS = 4
FIXES_SHARE = 6        # a plain round keeps one place in six for typos & fixes never practised
MAX_SECONDS = 120.0    # an answer that took longer counts as this much time: the learner stepped away


# ---------- one word ----------

def gap(sentence: str, word: str, source: str) -> dict | None:
    """`sentence` around the first place `word` stands whole (any case), or None when it isn't there."""
    core = store.squash(word)
    if not sentence or not core:
        return None
    pattern = re.escape(core).replace(r"\ ", r"\s+")
    m = re.search(rf"(?<![\w'’-]){pattern}(?![\w'’-])", sentence, re.IGNORECASE)
    if m is None:
        return None
    return {"before": sentence[:m.start()], "match": m.group(0), "after": sentence[m.end():], "source": source}


def word_options(w: Word) -> list[str]:
    """The choices for "which word?": the word and up to three wrong ones. For a misspelled word, the learner's own
    misspellings come first; a new word never offers what the learner wrote (it isn't wrong, only plainer)."""
    if w.kind == "spelling":
        pool = [w.word, *w.wrote, *w.distractors]
    elif w.kind == "new":
        pool = [w.word, *w.distractors]
    else:
        pool = [w.word, *w.distractors, *w.wrote]
    return distinct(pool, ())[:MAX_OPTIONS]


def _group(kind: str) -> str:
    return next(group for group, kinds in WORD_GROUPS.items() if kind in kinds)


_FILLER = frozenset("that this with from what when where which something someone your they them their there have been "
                    "does into about more very than then only also some make made thing things doing being used using".split())


def _gist(meaning: str) -> set[str]:
    """The telling words of a meaning, plurals folded: "rules or limits that stop you" -> {"rule", "limit", "stop"}."""
    return {t[:-1] if t.endswith("s") else t for t in re.findall(r"[a-z]{4,}", meaning.lower()) if t not in _FILLER}


def meaning_options(w: Word, words: list[Word], rng: random.Random) -> list[str]:
    """The word's meaning and up to three others, first from words of the same part of speech and list
    (a verb's meaning starts with "to", so the wrong ones should too). A meaning that shares two telling words
    with the right one could pass for it, so it is left out."""
    gist = _gist(w.meaning)
    others = [x for x in words if x.meaning and store.norm(x.word) != store.norm(w.word) and len(gist & _gist(x.meaning)) < 2]
    rng.shuffle(others)
    others.sort(key=lambda x: (x.pos != w.pos, _group(x.kind) != _group(w.kind)))
    return distinct([w.meaning, *(x.meaning for x in others[:12])], ())[:MAX_OPTIONS]


def exercise(w: Word, st: State | None, tap_only: bool = False) -> tuple[str, dict | None]:
    """How to ask about `w` now: "meaning", "choose" or "type", and the sentence with its gap (None for a meaning
    question, or for a word chosen or typed from its meaning alone)."""
    box = st.box if st else 0
    can_choose = len(word_options(w)) >= 2
    other = gap(w.example, w.word, "example")
    if w.kind == "new":
        own = gap(w.rewrite, w.word, "rewrite")
        if box == 0:
            return "meaning", None
        if box >= 3 and not tap_only:
            return "type", (own or other) if box % 2 else (other or own)
        if not can_choose:
            return "meaning", None
        return "choose", (own or other) if box == 1 else (other or own)
    if w.kind == "spelling":
        if not tap_only and (box >= 2 or not can_choose):
            return "type", other
        return ("choose", other) if can_choose else ("meaning", None)
    if not can_choose:
        return "meaning", None
    if w.kind == "know":
        return ("meaning", None) if box <= 1 or other is None else ("choose", other)
    return ("choose", other) if other and box != 2 else ("meaning", None)  # clearer


# ---------- a round ----------

def pick_words(view: View, group: str | None, size: int) -> list[Word]:
    """The words for a round: those due first (soonest first), then words never practised, then the weakest others.
    Up to half the round is kept for words never practised. A list's own round takes only that list
    (lessons.WORD_GROUPS); the plain round (`group` None) brings in new words first."""
    pool = [w for w in view.snap.words if group is None or w.kind in WORD_GROUPS[group]]
    due = sorted((w for w in pool if srs.is_due(view.state(w.id), view.now_ms)), key=lambda w: view.states[w.id].due_ms)
    fresh = sorted((w for w in pool if w.id not in view.states), key=lambda w: (w.times, w.last or ""), reverse=True)
    chosen = due[: size - min(len(fresh), math.ceil(size / 2))]
    room = size - len(chosen)
    if group is None:
        fresh = _new_first(fresh, room, math.ceil(size / FIXES_SHARE))
    chosen += fresh[:room]
    if len(chosen) < size:
        taken = {w.id for w in chosen}
        weakest = sorted((w for w in pool if w.id in view.states and w.id not in taken),
                         key=lambda w: (view.states[w.id].box, view.states[w.id].due_ms))
        chosen += weakest[: size - len(chosen)]
    return chosen


def _new_first(fresh: list[Word], room: int, fixes: int) -> list[Word]:
    """Words never practised for `room` places: new words, and typos & fixes in `fixes` of the places (in none when
    there are fewer than three places; in more when the new words run out)."""
    new = [w for w in fresh if w.kind == "new"]
    rest = [w for w in fresh if w.kind != "new"]
    n_new = min(len(new), room - min(fixes, room // 3, len(rest)))
    return new[:n_new] + rest[: room - n_new]


def build_word_round(view: View, group: str | None = None, tap_only: bool = False, seed: str = "") -> list[dict]:
    """The questions of a word round, in a mixed order that `seed` fixes."""
    rng = random.Random(seed)
    words = pick_words(view, group, int(view.settings.get("round_size", 8)))
    rng.shuffle(words)
    items = []
    for w in words:
        kind, sentence = exercise(w, view.state(w.id), tap_only)
        options = meaning_options(w, view.snap.words, rng) if kind == "meaning" else word_options(w) if kind == "choose" else []
        if kind == "meaning" and len(options) < 2 and len(word_options(w)) >= 2:  # no other meanings to choose from
            kind, sentence, options = "choose", gap(w.example, w.word, "example"), word_options(w)
        rng.shuffle(options)
        items.append({"item_id": w.id, "exercise": kind, "word": word_brief(view, w), "gap": sentence,
                      "options": options, "answer": w.meaning if kind == "meaning" else w.word})
    return items


def start_word_round(conn: sqlite3.Connection, view: View, group: str | None = None, tap_only: bool = False,
                     client_id: str | None = None) -> dict:
    """A new word round, saved with its questions. The same `client_id` (a page that asked twice) gets the same round.
    A round with no words to ask isn't saved."""
    with db.write_tx(conn):
        saved = db.session_for_client(conn, client_id) if client_id else None
        if saved is not None:
            return {"id": saved["id"], "group": saved["word_kind"], "items": saved["items"]}
        round_id = secrets.token_hex(8)
        items = build_word_round(view, group, tap_only, seed=round_id)
        if items:
            db.add_session(conn, round_id, client_id=client_id, mode="words", word_kind=group, created_ms=view.now_ms,
                           items=items)
    return {"id": round_id, "group": group, "items": items}


# ---------- answers ----------

def is_right(item: dict, given: str) -> bool:
    """The right choice, or the word typed with any case, spacing and end punctuation (store.norm)."""
    typed = store.norm(given or "")
    return bool(typed) and typed == store.norm(item["answer"])


def answer(conn: sqlite3.Connection, round_id: str, item_id: str, given: str, seconds: float, now_ms: int) -> dict:
    """Check and record an answer: the word's new schedule, the day's totals and the answer itself. Only the first
    answer to a question counts; sending it again changes nothing. Raises LookupError for a question not in the round."""
    with db.write_tx(conn):
        session = db.get_session(conn, round_id)
        item = next((it for it in (session or {}).get("items", []) if it["item_id"] == item_id), None)
        if item is None:
            raise LookupError("That question isn't part of this round.")
        first = db.answer_of(conn, round_id, item_id)
        if first is not None:
            correct = bool(first["correct"])
            st = db.load_state(conn, item_id)
        else:
            correct = is_right(item, given)
            seconds = min(max(seconds, 0.0), MAX_SECONDS)
            day = srs.day_key(now_ms)
            st = srs.grade(db.load_state(conn, item_id), correct, now_ms)
            db.put_state(conn, item_id, "word", st)
            db.add_answer(conn, round_id, item_id, ref_type="word", kind=item["exercise"], correct=correct,
                          seconds=seconds, answered_ms=now_ms, day=day, box_after=st.box)
            db.add_day(conn, day, correct, seconds)
    return {"item_id": item_id, "correct": correct, "answer": item["answer"], "status": srs.status(st),
            "strength": srs.strength(st), "due_at": iso_ms(st.due_ms) if st else None}


def finish(conn: sqlite3.Connection, round_id: str, now_ms: int) -> dict:
    """End a round: it counts as one round (once) when at least one answer was given. Raises LookupError for a round
    that doesn't exist."""
    with db.write_tx(conn):
        if db.get_session(conn, round_id) is None:
            raise LookupError("That round doesn't exist.")
        answered, correct = db.session_score(conn, round_id)
        if answered and db.finish_session(conn, round_id, now_ms):
            db.bump_counter(conn, "rounds.local")
    return {"answered": answered, "correct": correct}
