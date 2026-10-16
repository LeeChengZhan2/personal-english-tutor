"""Lessons as the app sees them: cards, words and messages derived from data/batches/*.json.

A port of the original app's derive()/deriveWords(): the same mistake (same pattern, same wrong -> right) made
in several messages is one card with several examples; the same word of the same kind is one word.
LessonStore keeps the derived snapshot in memory and rebuilds it only when a lesson file changes, so new
batches written by the pipeline (another process) show up on the next request without a restart.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import store

SEV_WEIGHT = {"error": 3, "unnatural": 2, "style": 1, "typo": 1}
WORD_KINDS = ("spelling", "know", "clearer")
FALLBACK_CATEGORIES = {
    "verbs": {"title": "Verbs", "zh": "动词"},
    "structure": {"title": "Sentence structure", "zh": "句子结构"},
    "nouns": {"title": "Nouns & articles", "zh": "名词与冠词"},
    "words": {"title": "Word choice", "zh": "用词"},
    "mechanics": {"title": "Spelling & punctuation", "zh": "拼写与标点"},
    "tone": {"title": "Tone & clarity", "zh": "语气与清晰度"},
}


@dataclass(slots=True)
class Example:
    sentence: str
    wrong: str
    right: str
    corrected: str
    ts: str
    message_id: str
    before: str = ""   # sentence = before + wrong + after, when located
    after: str = ""
    located: bool = False


@dataclass(slots=True)
class Card:
    id: str
    pattern: str
    severity: str
    wrong: str
    right: str
    explain: str
    explain_zh: str
    first: str
    last: str
    source: str
    distractors: list[str] = field(default_factory=list)
    examples: list[Example] = field(default_factory=list)
    times: int = 0     # distinct messages it came from


@dataclass(slots=True)
class Word:
    id: str
    kind: str
    word: str
    pos: str
    meaning: str
    meaning_zh: str
    example: str
    first: str
    last: str
    wrote: list[str] = field(default_factory=list)
    distractors: list[str] = field(default_factory=list)
    times: int = 0


@dataclass(slots=True)
class Message:
    id: str
    ts: str
    project: str
    text: str
    fixed: str
    polished: str
    words: int
    issues: int
    batch: str
    source: str


@dataclass(slots=True)
class Snapshot:
    version: str
    categories: dict[str, dict]
    patterns: dict[str, dict]
    cards: list[Card]
    card_by_id: dict[str, Card]
    words: list[Word]
    word_by_id: dict[str, Word]
    messages: list[Message]                 # newest first
    message_by_id: dict[str, Message]
    cards_by_message: dict[str, list[str]]  # message id -> card ids, in finding order
    batches: int = 0
    app_lessons: int = 0
    last_batch_at: str = ""      # when the pipeline last made a batch (its `created`)
    errors: list[str] = field(default_factory=list)
    loaded_at: float = 0.0

    def pattern_title(self, key: str) -> str:
        return (self.patterns.get(key) or {}).get("title") or key.replace("-", " ")


# ---------- repairing examples ----------

_WORD_BEFORE = r"(?<![^\W_])(?<!['’])"
_WORD_AFTER = r"(?![^\W_]|['’])"


def _locate_loose(sentence: str, wrong: str) -> int:
    """Index of `wrong` in `sentence` as whole words, ignoring case; -1 if absent."""
    core = wrong.strip()
    if not core:
        return -1
    pattern = re.escape(core)
    if store._is_word_char(core[0]):
        pattern = _WORD_BEFORE + pattern
    if store._is_word_char(core[-1]):
        pattern += _WORD_AFTER
    match = re.search(pattern, sentence, re.I)
    return match.start() if match else -1


def repair_example(sentence: str, wrong: str, right: str, corrected: str) -> tuple[str, str, str, str, bool]:
    """(sentence, corrected, before, after, located) for an example, fixing ones the model already corrected.

    Older batches matched `wrong` as a plain substring, so "Pleas" was found inside "Please" and the stored
    correction became "Pleasee". Here `wrong` must be whole words; if only `right` is there, the learner's words
    are put back. An example that still can't be located keeps its stored text and is never used for practice.
    """
    at = store.find_phrase(sentence, wrong)
    if at < 0:
        restored = store.put_back(sentence, wrong, right)
        if restored is not None:
            sentence = restored
            at = store.find_phrase(sentence, wrong)
    if at < 0:
        at = _locate_loose(sentence, wrong)
        if at >= 0 and sentence[at:at + len(wrong)].lower() != wrong.lower():
            at = -1
    if at < 0:
        return sentence, corrected or sentence, "", "", False
    before, after = sentence[:at], sentence[at + len(wrong):]
    return sentence, before + right + after, before, after, True


# ---------- derive ----------

def _first_ts(batch: dict) -> str:
    messages = batch.get("messages") or []
    return (messages[0].get("ts") if messages else "") or batch.get("created") or ""


def derive(batches: list[dict], catalog: dict) -> Snapshot:
    """Cards, words and messages from lesson batches (any order) and the pattern catalog."""
    categories = {**FALLBACK_CATEGORIES, **(catalog.get("categories") or {})}
    patterns = dict(catalog.get("patterns") or {})
    ordered = sorted(batches, key=_first_ts)
    cards: dict[str, Card] = {}
    messages: dict[str, Message] = {}
    by_message: dict[str, list[str]] = {}
    for b in ordered:
        for key, p in (b.get("patterns") or {}).items():
            patterns.setdefault(key, p)
        for m in b.get("messages") or []:
            if m.get("id") and m["id"] not in messages:
                messages[m["id"]] = Message(
                    id=m["id"], ts=m.get("ts", ""), project=m.get("project", ""), text=m.get("text", ""),
                    fixed=m.get("fixed", ""), polished=m.get("polished", ""), words=int(m.get("words") or 0),
                    issues=int(m.get("issues") or 0), batch=b.get("id", ""), source=b.get("source", ""),
                )
        for f in b.get("findings") or []:
            if not f or not f.get("card") or not f.get("sentence") or not f.get("wrong"):
                continue
            c = cards.get(f["card"])
            ts = f.get("ts") or ""
            if c is None:
                c = Card(id=f["card"], pattern=f.get("pattern", ""), severity=f.get("severity", "error"),
                         wrong=f["wrong"], right=f.get("right", ""), explain=f.get("explain", ""),
                         explain_zh=f.get("explain_zh", ""), first=ts, last=ts, source=b.get("source", ""))
                cards[c.id] = c
            sentence, corrected, before, after, located = repair_example(
                f["sentence"], f["wrong"], f.get("right", ""), f.get("corrected", ""))
            c.examples.append(Example(sentence=sentence, wrong=f["wrong"], right=f.get("right", ""), corrected=corrected,
                                      ts=ts, message_id=f.get("message_id", ""), before=before, after=after,
                                      located=located))
            for d in f.get("distractors") or []:
                if d and d not in c.distractors:
                    c.distractors.append(d)
            if ts >= (c.last or ""):
                c.last = ts
                if f.get("explain"):
                    c.explain = f["explain"]
                    c.explain_zh = f.get("explain_zh") or c.explain_zh
            if SEV_WEIGHT.get(f.get("severity"), 0) > SEV_WEIGHT.get(c.severity, 0):
                c.severity = f["severity"]
            by_message.setdefault(f.get("message_id", ""), []).append(c.id)
    for c in cards.values():
        if c.pattern not in patterns:
            patterns[c.pattern] = {"category": "words", "title": c.pattern.replace("-", " "), "rule": "", "rule_zh": ""}
        c.times = len({e.message_id for e in c.examples})
    card_list = list(cards.values())
    words = _derive_words(ordered, card_list)
    message_list = sorted(messages.values(), key=lambda m: m.ts, reverse=True)
    return Snapshot(
        version="", categories=categories, patterns=patterns, cards=card_list, card_by_id=cards,
        words=list(words.values()), word_by_id=words, messages=message_list, message_by_id=messages,
        cards_by_message=by_message, batches=sum(1 for b in batches if b.get("source") != "app"),
        app_lessons=sum(1 for b in batches if b.get("source") == "app"),
        last_batch_at=max((b.get("created") or "" for b in batches if b.get("source") != "app"), default=""),
    )


def _derive_words(ordered: list[dict], cards: list[Card]) -> dict[str, Word]:
    words: dict[str, Word] = {}
    for b in ordered:
        for v in b.get("vocab") or []:
            if not v or not v.get("id") or not v.get("word") or v.get("kind") not in WORD_KINDS:
                continue
            w = words.get(v["id"])
            ts = v.get("ts") or ""
            if w is None:
                w = Word(id=v["id"], kind=v["kind"], word=v["word"], pos=v.get("pos") or "", meaning=v.get("meaning") or "",
                         meaning_zh=v.get("meaning_zh") or "", example=v.get("example") or "", first=ts, last=ts)
                words[w.id] = w
            w.times += 1
            if v.get("you_wrote") and v["you_wrote"] not in w.wrote:
                w.wrote.append(v["you_wrote"])
            for d in v.get("distractors") or []:
                if d and d not in w.distractors:
                    w.distractors.append(d)
            if ts >= (w.last or ""):
                w.last = ts
                if v.get("example"):
                    w.example = v["example"]
                if v.get("meaning"):
                    w.meaning = v["meaning"]
                    w.meaning_zh = v.get("meaning_zh") or w.meaning_zh
    # a misspelling counts every time the user typed it, not once per batch
    typos: dict[str, int] = {}
    for c in cards:
        if c.pattern in ("spelling", "apostrophes"):
            key = store.norm(c.right)
            typos[key] = typos.get(key, 0) + len(c.examples)
    for w in words.values():
        if w.kind == "spelling":
            w.times = max(w.times, typos.get(store.norm(w.word), 0))
    return words


# ---------- the store ----------

class LessonStore:
    """The current Snapshot of data/batches + data/patterns.json, rebuilt when a file changes."""

    def __init__(self, batches_dir: Path, patterns_file: Path):
        self.batches_dir = Path(batches_dir)
        self.patterns_file = Path(patterns_file)
        self._lock = threading.Lock()
        self._parsed: dict[str, tuple[tuple, dict]] = {}   # file name -> (stat signature, parsed json)
        self._snapshot: Snapshot | None = None
        self._signature: tuple | None = None

    def _scan(self) -> tuple[list[tuple[str, tuple]], tuple]:
        files = []
        try:
            with os.scandir(self.batches_dir) as it:
                for entry in it:
                    if entry.is_file() and entry.name.endswith(".json"):
                        st = entry.stat()
                        files.append((entry.name, (st.st_mtime_ns, st.st_size)))
        except FileNotFoundError:
            pass
        files.sort()
        try:
            st = self.patterns_file.stat()
            catalog_sig = (st.st_mtime_ns, st.st_size)
        except FileNotFoundError:
            catalog_sig = (0, 0)
        return files, (tuple(files), catalog_sig)

    def snapshot(self) -> Snapshot:
        files, signature = self._scan()
        if self._snapshot is not None and signature == self._signature:
            return self._snapshot
        with self._lock:
            if self._snapshot is not None and signature == self._signature:
                return self._snapshot
            errors: list[str] = []
            parsed: dict[str, tuple[tuple, dict]] = {}
            complete = True
            for name, sig in files:
                cached = self._parsed.get(name)
                if cached and cached[0] == sig:
                    parsed[name] = cached
                    continue
                try:
                    data = json.loads((self.batches_dir / name).read_bytes().decode("utf-8"))
                    if not isinstance(data, dict):
                        raise ValueError("not a lesson batch")
                    parsed[name] = (sig, data)
                except (OSError, ValueError) as e:  # being written by the pipeline, or broken
                    complete = False
                    errors.append(f"{name}: {e}")
                    if cached:
                        parsed[name] = cached  # keep the previous version until it reads cleanly
            try:
                catalog = store.merge_catalog(store.read_user_patterns(self.patterns_file))
            except (OSError, ValueError) as e:
                complete = False
                errors.append(f"{self.patterns_file.name}: {e}")
                catalog = {"categories": self._snapshot.categories, "patterns": self._snapshot.patterns} if self._snapshot else {}
            snap = derive([data for _, data in parsed.values()], catalog)
            snap.version = hashlib.sha1(repr(signature).encode()).hexdigest()[:12]
            snap.errors = errors
            snap.loaded_at = time.time()
            self._parsed = parsed
            self._snapshot = snap
            # an unreadable file leaves the signature unrecorded, so the next request tries again
            self._signature = signature if complete else None
            return snap

    def invalidate(self) -> None:
        with self._lock:
            self._signature = None
