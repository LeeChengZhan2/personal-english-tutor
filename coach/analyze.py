"""Find the English mistakes in captured messages and turn them into lesson batches (data/batches/*.json)."""

from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from . import llm, store, vocab
from .config import BATCHES, INBOX, PROMPTS, load_config

RAW = INBOX / "raw"  # the model's answers, machine-local, for rebuilding batches without new calls

log = logging.getLogger("coach")

SEVERITIES = ("error", "unnatural", "style", "typo")
CATEGORIES = ("verbs", "structure", "nouns", "words", "mechanics", "tone")
MAX_BATCH_CHARS = 14000
# Pattern keys the model invented that duplicate a catalog pattern.
ALIASES = {"typo": "spelling", "typos": "spelling", "repeated-words": "spelling", "pronoun-possessive": "prepositions",
           "verb-preposition": "prepositions", "subject-verb-agreement": "subject-verb", "article": "articles",
           "plurals": "plural-nouns", "particles": "singlish-particles", "word-forms": "word-form"}

_STR = {"type": "string"}
SCHEMA = {
    "type": "object",
    "properties": {
        "messages": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": _STR,
                    "keep": {"type": "boolean"},
                    "fixed": _STR,
                    "polished": _STR,
                    "redact": {"type": "array", "items": _STR},
                },
                "required": ["id", "keep", "fixed", "polished", "redact"],
            },
        },
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "message_id": _STR,
                    "pattern": _STR,
                    "severity": {"type": "string", "enum": list(SEVERITIES)},
                    "sentence": _STR,
                    "wrong": _STR,
                    "right": _STR,
                    "explain": _STR,
                    "explain_zh": _STR,
                    "distractors": {"type": "array", "items": _STR},
                },
                "required": ["message_id", "pattern", "severity", "sentence", "wrong", "right", "explain", "explain_zh", "distractors"],
            },
        },
        "new_patterns": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"key": _STR, "category": _STR, "title": _STR, "rule": _STR, "rule_zh": _STR},
                "required": ["key", "category", "title", "rule", "rule_zh"],
            },
        },
    },
    "required": ["messages", "findings", "new_patterns"],
}


def _short_project(project: str) -> str:
    """c--Users-Me-Code-aibe-operator -> aibe-operator"""
    match = re.search(r"-Code-(.+)$", project)
    return match.group(1) if match else project


def make_batches(messages: list[dict], size: int) -> list[list[dict]]:
    """Messages in session order (each session's messages together, in time order), packed into
    batches of up to `size` messages or MAX_BATCH_CHARS characters."""
    first_seen: dict[str, str] = {}
    for m in messages:
        first_seen.setdefault(m["session"], m["ts"])
    ordered = sorted(messages, key=lambda m: (first_seen[m["session"]], m["session"], m["ts"]))
    batches: list[list[dict]] = []
    current: list[dict] = []
    chars = 0
    for m in ordered:
        if current and (len(current) >= size or chars + len(m["text"]) > MAX_BATCH_CHARS):
            batches.append(current)
            current, chars = [], 0
        current.append(m)
        chars += len(m["text"])
    if current:
        batches.append(current)
    return batches


def _pattern_list(catalog: dict) -> str:
    lines = []
    for key, p in catalog["patterns"].items():
        lines.append(f"- {key} ({p['category']}): {p['title']}. {p['rule']}")
    return "\n".join(lines)


def build_prompt(messages: list[dict], catalog: dict) -> str:
    payload = [
        {"id": m["id"], "date": m["ts"][:10], "project": _short_project(m["project"]), "text": store.redact(m["text"])}
        for m in messages
    ]
    template = (PROMPTS / "analyze.md").read_text(encoding="utf-8")
    return template.replace("{PATTERNS}", _pattern_list(catalog)).replace(
        "{MESSAGES}", json.dumps(payload, ensure_ascii=False, indent=1)
    )


_WORD_BEFORE = r"(?<![^\W_])(?<!['’])"   # not right after a letter, digit or apostrophe
_WORD_AFTER = r"(?![^\W_]|['’])"


def _locate(sentence: str, wrong: str) -> str | None:
    """`wrong` as whole words in `sentence` (case or spacing may differ in the model's copy)."""
    if store.find_phrase(sentence, wrong) >= 0:
        return wrong
    core = wrong.strip()
    if not core:
        return None
    pattern = re.escape(core).replace(r"\ ", r"\s+")
    if store._is_word_char(core[0]):
        pattern = _WORD_BEFORE + pattern
    if store._is_word_char(core[-1]):
        pattern += _WORD_AFTER
    match = re.search(pattern, sentence, re.I)
    return match.group(0) if match else None


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def repair(sentence: str, wrong: str, right: str) -> tuple[str, str, str] | None:
    """Make a finding usable as an exercise, or None.

    The model sometimes fixes the mistake inside `sentence` too (then `right` is there and `wrong`
    is not: put the learner's words back), or gives an empty `right` for a word to delete (then
    take the neighbouring word into both sides: "first gua" -> "first").
    """
    found = _locate(sentence, wrong)
    if not found and right and wrong.strip():
        restored = store.put_back(sentence, wrong.strip(), right)
        if restored is not None:
            sentence, found = restored, wrong.strip()
    if not found:
        return None
    if not right.strip():
        at = store.find_phrase(sentence, found)
        if at < 0:
            at = sentence.find(found)
        before = sentence[:at].rstrip()
        after = sentence[at + len(found):]
        prev = re.search(r"(\S+)$", before)
        if prev:
            start = at - (len(sentence[:at]) - len(before)) - len(prev.group(1))
            found = sentence[start:at + len(found)]
            right = prev.group(1)
        else:
            nxt = re.match(r"\s*(\S+)", after)
            if not nxt:
                return None
            found = sentence[at:at + len(found) + len(nxt.group(0))]
            right = nxt.group(1)
    if store.squash(found) == store.squash(right):
        return None
    return sentence, found, right


def build_batch(messages: list[dict], result: dict, catalog: dict) -> dict:
    """Validate the model's answer and shape it as one lesson batch."""
    by_id = {m["id"]: m for m in messages}
    secrets: dict[str, list[str]] = {}
    out_messages = []
    for r in result.get("messages", []):
        m = by_id.get(r.get("id"))
        if not m or not r.get("keep"):
            continue
        secrets[m["id"]] = [s for s in r.get("redact", []) if isinstance(s, str)]
        text = store.redact(m["text"], secrets[m["id"]])
        out_messages.append({
            "id": m["id"],
            "ts": m["ts"],
            "project": _short_project(m["project"]),
            "text": text,
            "fixed": store.redact(r.get("fixed", ""), secrets[m["id"]]),
            "polished": store.redact(r.get("polished", ""), secrets[m["id"]]),
            "words": len(text.split()),
            "issues": 0,
        })
    kept = {m["id"]: m for m in out_messages}

    new_patterns = {}
    for p in result.get("new_patterns", []):
        key = re.sub(r"[^a-z0-9-]+", "-", str(p.get("key", "")).lower()).strip("-")
        rule = str(p.get("rule", ""))
        if (key and key not in catalog["patterns"] and key not in ALIASES and p.get("category") in CATEGORIES
                and len(rule) >= 25 and "placeholder" not in (key + rule + str(p.get("title", ""))).lower()):
            new_patterns[key] = {k: p.get(k, "") for k in ("category", "title", "rule", "rule_zh")}
            new_patterns[key]["examples"] = []

    findings = []
    for f in result.get("findings", []):
        m = kept.get(f.get("message_id"))
        if not m:
            continue
        hide = secrets.get(m["id"], [])
        sentence = store.redact(str(f.get("sentence", "")).strip(), hide)
        fixed = repair(sentence, store.redact(str(f.get("wrong", "")), hide), store.redact(str(f.get("right", "")).strip(), hide))
        if fixed:
            sentence, wrong, right = fixed
        # the sentence must really come from this message, not be invented
        words = set(_words(sentence))
        if not fixed or len(words) < 2 or len(words & set(_words(m["text"]))) < 0.4 * len(words):
            log.info("dropped finding %r -> %r in %r", f.get("wrong"), f.get("right"), sentence[:80])
            continue
        pattern = ALIASES.get(f.get("pattern"), f.get("pattern"))
        if pattern not in catalog["patterns"] and pattern not in new_patterns:
            pattern = "word-choice"
        severity = f.get("severity") if f.get("severity") in SEVERITIES else "error"
        distractors = []
        for d in f.get("distractors", []):
            d = store.squash(str(d))
            if d and d not in {store.squash(wrong), store.squash(right), *distractors}:
                distractors.append(d)
        findings.append({
            "card": store.card_id(pattern, wrong, right),
            "message_id": m["id"],
            "ts": m["ts"],
            "pattern": pattern,
            "severity": severity,
            "sentence": sentence,
            "wrong": wrong,
            "right": right,
            "corrected": store.replace_phrase(sentence, wrong, right) or sentence.replace(wrong, right, 1),
            "explain": str(f.get("explain", "")).strip(),
            "explain_zh": str(f.get("explain_zh", "")).strip(),
            "distractors": distractors[:3],
        })
        if severity != "style":
            m["issues"] += 1

    first = messages[0]
    stamp = datetime.fromisoformat(first["ts"].replace("Z", "+00:00")).strftime("%Y%m%d-%H%M%S") if first["ts"] else "unknown"
    batch_id = f"b{stamp}-{first['session'][:8]}-{first['id'][:4]}"
    return {
        "id": batch_id,
        "v": 1,
        "created": store.now_iso(),
        "source": "claude-code",
        "project": _short_project(first["project"]),
        "messages": out_messages,
        "findings": findings,
        "patterns": new_patterns,
    }


def analyze_batch(messages: list[dict], catalog: dict, accounts=None, cancel=None) -> tuple[dict, dict]:
    """The lesson batch, and the model's raw answer (kept locally so batches can be rebuilt)."""
    answer, _ = llm.ask_json(build_prompt(messages, catalog), SCHEMA, tier="analysis", accounts=accounts, cancel=cancel)
    return build_batch(messages, answer, catalog), answer


def rebuild_all() -> int:
    """Rebuild every batch from the saved raw answers (after improving the validation). No model calls."""
    by_id = {m["id"]: m for m in store.read_messages()}
    catalog = store.read_patterns()
    count = 0
    for raw_path in sorted(RAW.glob("*.json")):
        saved = json.loads(raw_path.read_text(encoding="utf-8"))
        messages = [by_id[i] for i in saved["input_ids"] if i in by_id]
        if not messages:
            continue
        batch = build_batch(messages, saved["answer"], catalog)
        batch["id"] = raw_path.stem
        raw_vocab = vocab.RAW / raw_path.name
        if raw_vocab.exists():
            batch["vocab"] = vocab.clean(batch, json.loads(raw_vocab.read_text(encoding="utf-8")))
        store.write_json(BATCHES / f"{batch['id']}.json", batch)
        count += 1
    return count


def _save(batch: dict, input_ids: list[str], answer: dict) -> None:
    store.write_json(RAW / f"{batch['id']}.json", {"input_ids": input_ids, "answer": answer})
    store.write_json(BATCHES / f"{batch['id']}.json", batch)
    if batch["patterns"]:
        with store.lock("patterns"):
            store.add_patterns(batch["patterns"])
    store.add_ids(store.ANALYZED, input_ids)


def analyze_pending(limit: int | None = None, parallel: int = 1, accounts=None, cancel=None, on_batch=None) -> list[str]:
    """Analyze waiting messages. Returns the new batch ids. A failed batch stays pending for the next run.

    `on_batch(done, total)` is called after each batch. Setting `cancel` stops before the next batch (and the
    running ones as soon as possible). If every account is out of usage or not signed in, the LLMError is raised.
    """
    config = load_config()
    pending = store.pending_messages()
    batches = make_batches(pending, int(config["batch_size"]))
    if limit:
        batches = batches[:limit]
    if not batches:
        return []
    catalog = store.read_patterns()
    done: list[str] = []
    finished = 0
    blocking: list[llm.LLMError] = []

    def work(group: list[dict]) -> str | None:
        nonlocal finished
        if (cancel is not None and cancel.is_set()) or blocking:
            return None
        try:
            batch, answer = analyze_batch(group, catalog, accounts, cancel)
            if batch["messages"]:
                try:
                    vocab.add_vocab(batch, accounts, cancel)
                except llm.LLMError as e:  # vocab.fill_missing retries it on the next update
                    log.warning("vocabulary failed for %s: %s", batch["id"], e)
            _save(batch, [m["id"] for m in group], answer)
            log.info("batch %s: %d messages, %d findings", batch["id"], len(batch["messages"]), len(batch["findings"]))
            return batch["id"]
        except llm.LLMError as e:
            if e.kind in ("usage_limit", "auth", "not_configured", "not_installed"):
                blocking.append(e)  # no account can go on: stop starting new batches
            elif e.kind != "cancelled":
                log.warning("analysis failed for %d messages: %s", len(group), e)
            return None
        finally:
            finished += 1
            if on_batch:
                on_batch(finished, len(batches))

    with ThreadPoolExecutor(max_workers=max(1, parallel)) as pool:
        for batch_id in pool.map(work, batches):
            if batch_id:
                done.append(batch_id)
    if blocking and not done:
        raise blocking[0]
    return done
