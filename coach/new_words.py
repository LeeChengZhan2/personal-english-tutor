"""New words: vocabulary the learner hasn't used yet, picked from their own messages.

A third pass over an analyzed batch, after vocab.py. Where a message says something in a plain, vague or long way,
Claude suggests the word a fluent professional would use there, with the learner's sentence rewritten around it.
Only level B2 and above is kept, and a word the learner has typed in any message is dropped, so every item is one
they haven't used yet. Adds `batch["new_words"]` (kind "new"); the raw answer is kept in data/inbox/raw-new-words/.
"""

from __future__ import annotations

import json
import re
import threading
from collections.abc import Iterable

from . import llm, srs, store, vocab
from .config import INBOX, PROMPTS

KIND = "new"
LEVELS = ("A2", "B1", "B2", "C1", "C2")
KEEP_LEVELS = ("B2", "C1", "C2")   # the learner already knows the easier words
MAX_ITEMS = 8
TAUGHT_IN_PROMPT = 300             # the newest words already in a list, so Claude doesn't suggest them again
RAW = INBOX / "raw-new-words"

_STR = {"type": "string"}
SCHEMA = {
    "type": "object",
    "properties": {
        "new_words": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "word": _STR,
                    "pos": _STR,
                    "level": {"type": "string", "enum": list(LEVELS)},
                    "meaning": _STR,
                    "meaning_zh": _STR,
                    "you_wrote": _STR,
                    "rewrite": _STR,
                    "example": _STR,
                    "message_id": _STR,
                    "distractors": {"type": "array", "items": _STR},
                },
                "required": ["word", "pos", "level", "meaning", "meaning_zh", "you_wrote", "rewrite", "example",
                             "message_id", "distractors"],
            },
        }
    },
    "required": ["new_words"],
}


# ---------- what the learner has typed ----------

_TOKEN = re.compile(r"[a-z][a-z'-]*")
_ENDINGS = (("ies", "y"), ("ied", "y"), ("ing", ""), ("ing", "e"), ("ed", ""), ("ed", "e"), ("es", ""), ("s", ""), ("ly", ""))


def _forms(word: str) -> set[str]:
    """The word and the stems it may come from: 'clarified' -> {'clarified', 'clarify', ...}."""
    forms = {word}
    for ending, base in _ENDINGS:
        if word.endswith(ending) and len(word) - len(ending) >= 3:
            stem = word[: -len(ending)] + base
            forms.add(stem)
            if not base and stem[-1] == stem[-2]:
                forms.add(stem[:-1])  # planned -> plan
    return forms


class Known:
    """The words and phrases the learner has typed. A suggestion they have used before isn't new to them."""

    def __init__(self, texts: Iterable[str]):
        self.text = "\n".join(store.norm(t) for t in texts)
        self.forms = {form for token in _TOKEN.findall(self.text) for form in _forms(token)}

    def has(self, word: str) -> bool:
        w = store.norm(word)
        if " " in w:
            return re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", self.text) is not None
        return bool(_forms(w) & self.forms)


def typed_words(messages: list[dict] | None = None, until: str = "") -> Known:
    """Every word in the captured messages, or only in those typed by `until` (an ISO time)."""
    messages = store.read_messages() if messages is None else messages
    if until:
        cutoff = srs.parse_ms(until)
        messages = [m for m in messages if _typed_by(m.get("ts", ""), cutoff)]
    return Known(m.get("text", "") for m in messages)


def _typed_by(ts: str, cutoff: int) -> bool:
    try:
        return srs.parse_ms(ts) <= cutoff
    except ValueError:
        return True


# ---------- one batch ----------

def _payload(batch: dict) -> list[dict]:
    """The messages long enough to have something worth saying in a better way."""
    return [{"id": m["id"], "text": m["text"], "polished": m.get("polished", "")}
            for m in batch.get("messages", []) if len(m.get("text", "").split()) >= 4]


def build_prompt(batch: dict, taught: list[str]) -> str:
    template = (PROMPTS / "new_words.md").read_text(encoding="utf-8")
    return (template.replace("{TAUGHT}", ", ".join(taught) or "(none yet)")
            .replace("{MESSAGES}", json.dumps(_payload(batch), ensure_ascii=False, indent=1)))


def _uses(text: str, word: str) -> bool:
    """Whether `text` uses `word`, allowing another ending ('deprecate' in 'it is deprecated')."""
    low = text.lower()
    return all(part[: max(3, len(part) - 2)] in low for part in store.norm(word).split())


def clean(batch: dict, answer: dict, typed: Known) -> list[dict]:
    """Validated new words: level B2 and above, from a real message, and never typed by the learner."""
    messages = {m["id"]: m for m in batch.get("messages", [])}
    items: dict[str, dict] = {}
    for v in answer.get("new_words", []):
        word = store.squash(str(v.get("word", "")))
        m = messages.get(v.get("message_id"))
        if not word or not m or len(word.split()) > 4 or len(word) > 40:
            continue
        if v.get("level") not in KEEP_LEVELS or typed.has(word):
            continue
        item_id = vocab.vocab_id(KIND, word)
        if item_id in items:
            continue
        you_wrote = store.squash(str(v.get("you_wrote", "")))
        if you_wrote and you_wrote.lower() not in m["text"].lower():
            you_wrote = ""  # only show what the user really wrote
        rewrite = store.squash(str(v.get("rewrite", "")))
        example = store.squash(str(v.get("example", "")))
        items[item_id] = {
            "id": item_id,
            "kind": KIND,
            "word": word,
            "pos": store.squash(str(v.get("pos", ""))).lower(),
            "level": v["level"],
            "meaning": store.squash(str(v.get("meaning", ""))),
            "meaning_zh": store.squash(str(v.get("meaning_zh", ""))),
            "you_wrote": you_wrote,
            "rewrite": rewrite if _uses(rewrite, word) else "",
            "example": example if _uses(example, word) else "",
            "message_id": m["id"],
            "ts": m.get("ts", ""),
            "distractors": vocab.distinct(v.get("distractors", []), {word, you_wrote})[:3],
        }
    return list(items.values())[:MAX_ITEMS]


def add_new_words(batch: dict, typed: Known, taught: list[str], accounts=None, cancel=None) -> dict:
    """The batch with `new_words` filled in; the raw answer is kept in data/inbox/raw-new-words/."""
    items: list[dict] = []
    if _payload(batch):
        answer, _ = llm.ask_json(build_prompt(batch, taught), SCHEMA, tier="analysis", accounts=accounts, cancel=cancel)
        store.write_json(RAW / f"{batch['id']}.json", answer)
        items = clean(batch, answer, typed)
    batch["new_words"] = items
    batch["new_words_at"] = store.now_iso()  # what counted as typed then: rebuild_all uses the same messages
    return batch


# ---------- every batch ----------

def missing() -> list[dict]:
    """Lesson batches that have no new words yet."""
    return vocab.batches_without("new_words")


def _taught() -> list[str]:
    """The words already in a list that says things better (new words and clearer words), oldest first."""
    words: dict[str, tuple[str, str]] = {}
    for path in store.batch_paths():
        try:
            batch = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for v in (batch.get("vocab") or []) + (batch.get("new_words") or []):
            if v.get("kind") in ("clearer", KIND) and v.get("word"):
                words.setdefault(store.norm(v["word"]), (v.get("ts") or "", v["word"]))
    return [word for _, word in sorted(words.values())]


def fill_missing(parallel: int = 2, accounts=None, cancel=None, on_batch=None) -> int:
    """Add new words to every batch that has none yet. Returns how many batches were filled."""
    todo = missing()
    if not todo:
        return 0
    typed = typed_words()
    taught = _taught()
    lock = threading.Lock()

    def add(batch: dict) -> None:
        with lock:
            newest = taught[-TAUGHT_IN_PROMPT:]
        add_new_words(batch, typed, newest, accounts, cancel)
        with lock:
            taught.extend(v["word"] for v in batch["new_words"])

    return vocab.fill(todo, add, "new_words", parallel=parallel, cancel=cancel, on_batch=on_batch)


def rebuild_all() -> int:
    """Rebuild every batch's new words from the saved raw answers (no model calls), with the messages typed by then."""
    messages = store.read_messages()
    count = 0
    for path in store.batch_paths():
        raw = RAW / path.name
        if not raw.exists():
            continue
        batch = json.loads(path.read_text(encoding="utf-8"))
        typed = typed_words(messages, until=batch.get("new_words_at", ""))
        batch["new_words"] = clean(batch, json.loads(raw.read_text(encoding="utf-8")), typed)
        store.write_json(path, batch)
        count += 1
    return count
