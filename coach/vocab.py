"""Vocabulary for a lesson batch: words the user mistypes, words to know, and words that say it clearer.

A second pass over an analyzed batch: it reads each message with its fixed and polished versions and
the mistakes found, and adds `batch["vocab"]`.
"""

from __future__ import annotations

import hashlib
import json
import logging
from concurrent.futures import ThreadPoolExecutor

from . import llm, store
from .config import BATCHES, INBOX, PROMPTS

log = logging.getLogger("coach")

KINDS = ("spelling", "know", "clearer")
RAW = INBOX / "raw-vocab"

_STR = {"type": "string"}
SCHEMA = {
    "type": "object",
    "properties": {
        "vocab": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "word": _STR,
                    "kind": {"type": "string", "enum": list(KINDS)},
                    "pos": _STR,
                    "meaning": _STR,
                    "meaning_zh": _STR,
                    "example": _STR,
                    "you_wrote": _STR,
                    "message_id": _STR,
                    "distractors": {"type": "array", "items": _STR},
                },
                "required": ["word", "kind", "pos", "meaning", "meaning_zh", "example", "you_wrote", "message_id", "distractors"],
            },
        }
    },
    "required": ["vocab"],
}


def vocab_id(kind: str, word: str) -> str:
    """The same word of the same kind is one card, whichever message it came from."""
    return hashlib.sha1(f"vocab|{kind}|{store.norm(word)}".encode("utf-8")).hexdigest()[:10]


def distinct(values, exclude) -> list[str]:
    """The non-empty values, squashed, without repeats or anything in `exclude` (compared normalized)."""
    seen = {store.norm(x) for x in exclude}
    out = []
    for value in values:
        value = store.squash(str(value))
        if value and store.norm(value) not in seen:
            seen.add(store.norm(value))
            out.append(value)
    return out


def build_prompt(batch: dict) -> str:
    by_msg: dict[str, list[str]] = {}
    for f in batch.get("findings", []):
        by_msg.setdefault(f["message_id"], []).append(f'{f["wrong"]} -> {f["right"]} ({f["pattern"]})')
    payload = [
        {"id": m["id"], "text": m["text"], "fixed": m.get("fixed", ""), "polished": m.get("polished", ""), "mistakes": by_msg.get(m["id"], [])}
        for m in batch.get("messages", [])
    ]
    template = (PROMPTS / "vocab.md").read_text(encoding="utf-8")
    return template.replace("{MESSAGES}", json.dumps(payload, ensure_ascii=False, indent=1))


def clean(batch: dict, answer: dict) -> list[dict]:
    """Validated vocabulary items for the batch."""
    messages = {m["id"]: m for m in batch.get("messages", [])}
    items: dict[str, dict] = {}
    for v in answer.get("vocab", []):
        word = store.squash(str(v.get("word", "")))
        kind = v.get("kind")
        m = messages.get(v.get("message_id"))
        if not word or kind not in KINDS or not m or len(word.split()) > 4 or len(word) > 40:
            continue
        you_wrote = store.squash(str(v.get("you_wrote", "")))
        if kind == "spelling" and (not you_wrote or store.norm(you_wrote) == store.norm(word)):
            continue  # a spelling item needs the wrong spelling, and a real difference
        if you_wrote and you_wrote.lower() not in m["text"].lower():
            you_wrote = ""  # only show what the user really wrote
        distractors = distinct(v.get("distractors", []), {word, you_wrote})
        item_id = vocab_id(kind, word)
        if item_id in items:
            continue
        items[item_id] = {
            "id": item_id,
            "kind": kind,
            "word": word,
            "pos": store.squash(str(v.get("pos", ""))).lower(),
            "meaning": store.squash(str(v.get("meaning", ""))),
            "meaning_zh": store.squash(str(v.get("meaning_zh", ""))),
            "example": store.squash(str(v.get("example", ""))),
            "you_wrote": you_wrote,
            "message_id": m["id"],
            "ts": m.get("ts", ""),
            "distractors": distractors[:3],
        }
    return list(items.values())


def vocab_for(batch: dict, accounts=None, cancel=None) -> tuple[list[dict], dict]:
    answer, _ = llm.ask_json(build_prompt(batch), SCHEMA, tier="analysis", accounts=accounts, cancel=cancel)
    return clean(batch, answer), answer


def add_vocab(batch: dict, accounts=None, cancel=None) -> dict:
    """The batch with `vocab` filled in; the raw answer is kept in data/inbox/raw-vocab/."""
    items, answer = vocab_for(batch, accounts, cancel)
    store.write_json(RAW / f"{batch['id']}.json", answer)
    batch["vocab"] = items
    return batch


def batches_without(key: str) -> list[dict]:
    """Lesson batches that have no `key` yet (lessons saved from Check writing never get word lists)."""
    todo = []
    for path in store.batch_paths():
        if path.stem.startswith("app-"):
            continue
        try:
            batch = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            log.warning("can't read %s: %s", path.name, e)
            continue
        if key not in batch and batch.get("messages"):
            todo.append(batch)
    return todo


def missing() -> list[dict]:
    """Lesson batches that have no vocabulary yet."""
    return batches_without("vocab")


def fill(todo: list[dict], add, key: str, *, parallel: int = 2, cancel=None, on_batch=None) -> int:
    """Run `add(batch)` (which fills `batch[key]`) on each batch and save it. Returns how many batches were filled.
    `on_batch(done, total)` is called after each batch; setting `cancel` stops before the next one."""
    if not todo:
        return 0
    done = 0

    def work(batch: dict) -> bool:
        nonlocal done
        if cancel is not None and cancel.is_set():
            return False
        try:
            add(batch)
        except llm.LLMError as e:
            if e.kind in ("cancelled", "not_configured"):
                return False
            log.warning("%s failed for %s: %s", key, batch["id"], e)
            return False
        finally:
            done += 1
            if on_batch:
                on_batch(done, len(todo))
        store.write_json(BATCHES / f"{batch['id']}.json", batch)
        log.info("%s for %s: %d words", key, batch["id"], len(batch[key]))
        return True

    with ThreadPoolExecutor(max_workers=max(1, parallel)) as pool:
        return sum(pool.map(work, todo))


def fill_missing(parallel: int = 2, accounts=None, cancel=None, on_batch=None) -> int:
    """Add vocabulary to every batch that has none yet. Returns how many batches were filled."""
    return fill(missing(), lambda batch: add_vocab(batch, accounts, cancel), "vocab",
                parallel=parallel, cancel=cancel, on_batch=on_batch)


def rebuild_all() -> int:
    """Rebuild every batch's vocabulary from the saved raw answers (no model calls)."""
    count = 0
    for path in store.batch_paths():
        raw = RAW / path.name
        if not raw.exists():
            continue
        batch = json.loads(path.read_text(encoding="utf-8"))
        batch["vocab"] = clean(batch, json.loads(raw.read_text(encoding="utf-8")))
        store.write_json(path, batch)
        count += 1
    return count
