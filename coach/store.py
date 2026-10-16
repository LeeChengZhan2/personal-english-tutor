"""Local files under data/: captured messages (data/inbox/), lesson batches (data/batches/), and what is done.

Every inbox file is append-only, so capturing and analyzing never rewrite each other's files:
"pending" is computed as captured minus analyzed.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from .config import BASE_CATALOG, BATCHES, INBOX, PATTERNS_FILE, STATE_FILE

MESSAGES = INBOX / "messages.jsonl"   # every captured message
ANALYZED = INBOX / "analyzed.txt"     # ids of messages already analyzed


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def message_id(text: str, ts: str) -> str:
    """Copies of a message (a resumed session repeats it) share its text and timestamp."""
    return hashlib.sha1(f"{ts[:19]}|{text}".encode("utf-8")).hexdigest()[:12]


def _straight_quotes(text: str) -> str:
    return text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", _straight_quotes(text)).strip().strip(".!?,;:").strip().lower()


def squash(text: str) -> str:
    """Whitespace-insensitive, case-sensitive form, for telling a capital-letter fix from no change."""
    return re.sub(r"\s+", " ", text).strip()


def answer_key(text: str) -> str:
    """A typed answer compared with the expected sentence: spacing, curly quotes and a final .!? don't matter,
    capital letters do (the app's answerKey)."""
    return re.sub(r"[.!?]+$", "", squash(_straight_quotes(text))).strip()


# ---------- phrases at word boundaries ----------
# A word character is a letter, digit or apostrophe; "_" is not, so "control" in "user_role_control" counts as a
# word of its own. Matching at word boundaries keeps "Pleas" from matching inside "Please" (which once made
# "Pleasee" out of a fix).

def _is_word_char(ch: str) -> bool:
    return ch.isalnum() or ch in "'’"


def find_phrase(text: str, phrase: str, start: int = 0) -> int:
    """Index of the first occurrence of `phrase` in `text` that doesn't start or end inside a word, or -1."""
    if not phrase:
        return -1
    at = text.find(phrase, start)
    while at >= 0:
        end = at + len(phrase)
        left_ok = at == 0 or not _is_word_char(phrase[0]) or not _is_word_char(text[at - 1])
        right_ok = end == len(text) or not _is_word_char(phrase[-1]) or not _is_word_char(text[end])
        if left_ok and right_ok:
            return at
        at = text.find(phrase, at + 1)
    return -1


def replace_phrase(text: str, phrase: str, replacement: str) -> str | None:
    """`text` with the first whole-word occurrence of `phrase` replaced, or None if there is none."""
    at = find_phrase(text, phrase)
    if at < 0:
        return None
    return text[:at] + replacement + text[at + len(phrase):]


def put_back(sentence: str, wrong: str, right: str) -> str | None:
    """The model sometimes fixes the mistake inside the example sentence too: put the learner's words back.
    None when `wrong` is already there or `right` isn't."""
    if not wrong or find_phrase(sentence, wrong) >= 0:
        return None
    return replace_phrase(sentence, right, wrong) if right else None


def card_id(pattern: str, wrong: str, right: str) -> str:
    """The same mistake made again (same pattern, same wrong -> right) is the same card."""
    w, r = norm(wrong), norm(right)
    if w == r:  # a capital-letter fix: the case is the lesson
        w, r = squash(wrong), squash(right)
    return hashlib.sha1(f"{pattern}|{w}|{r}".encode("utf-8")).hexdigest()[:10]


# ---------- secrets ----------

_SECRETS = [
    (re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+"), "[email]"),
    (re.compile(r"\b(sk|pk|rk)-[A-Za-z0-9_-]{16,}"), "[secret]"),
    (re.compile(r"\b(ghp|gho|ghs|github_pat)_[A-Za-z0-9_]{16,}"), "[secret]"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"), "[secret]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[secret]"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), "[secret]"),
    (re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/-]{16,}=*"), r"\1 [secret]"),
    # share keys in links, e.g. a claude.ai artifact link ...?sk=<key>
    (re.compile(r"(?i)([?&](?:sk|key|sig|signature|access_token|auth|code)=)[^&\s\"'<>)\]]{8,}"), r"\1[secret]"),
    (re.compile(r"(?i)\b(password|passwd|pwd|token|api[_ -]?key|secret)\s*[:=]\s*\S+"), r"\1: [secret]"),
]


def redact(text: str, extra: list[str] | None = None) -> str:
    for secret in sorted(extra or [], key=len, reverse=True):
        if secret and secret.strip():
            text = text.replace(secret, "[secret]")
    for pattern, replacement in _SECRETS:
        text = pattern.sub(replacement, text)
    return text


# ---------- append-only id sets ----------

def read_ids(path: Path) -> set[str]:
    try:
        return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}
    except FileNotFoundError:
        return set()


def add_ids(path: Path, ids) -> None:
    ids = [i for i in ids if i]
    if not ids:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write("".join(f"{i}\n" for i in ids))


# ---------- messages ----------

def read_messages() -> list[dict]:
    """Every captured message, once each, oldest first."""
    seen: dict[str, dict] = {}
    try:
        with open(MESSAGES, encoding="utf-8") as f:
            for line in f:
                try:
                    m = json.loads(line)
                except ValueError:
                    continue
                seen.setdefault(m["id"], m)
    except FileNotFoundError:
        pass
    return sorted(seen.values(), key=lambda m: m.get("ts", ""))


def append_messages(messages: list[dict]) -> None:
    if not messages:
        return
    MESSAGES.parent.mkdir(parents=True, exist_ok=True)
    with open(MESSAGES, "a", encoding="utf-8") as f:
        for m in messages:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")


def pending_messages() -> list[dict]:
    done = read_ids(ANALYZED)
    return [m for m in read_messages() if m["id"] not in done]


# ---------- capture state (offsets per transcript) ----------

def read_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def write_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, STATE_FILE)


# ---------- batches and patterns ----------

def batch_paths() -> list[Path]:
    return sorted(BATCHES.glob("*.json"))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for attempt in range(10):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:  # Windows: another process (the app's server) is reading the file right now
            if attempt == 9:
                raise
            time.sleep(0.05)


def read_user_patterns(path: Path = PATTERNS_FILE) -> dict:
    """Patterns the model added for this user (data/patterns.json), or none yet."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    return {"categories": dict(data.get("categories") or {}), "patterns": dict(data.get("patterns") or {})}


def merge_catalog(user: dict, base_path: Path = BASE_CATALOG) -> dict:
    """The shipped catalog (coach/catalog.json) with the user's own patterns over it."""
    base = json.loads(base_path.read_text(encoding="utf-8"))
    return {"categories": {**base.get("categories", {}), **(user.get("categories") or {})},
            "patterns": {**base.get("patterns", {}), **(user.get("patterns") or {})}}


def read_patterns() -> dict:
    """The full pattern catalog: shipped patterns plus the ones added for this user."""
    return merge_catalog(read_user_patterns())


def add_patterns(new: dict) -> None:
    """Keep new patterns the model invented in the user's own catalog (never overwrites one)."""
    user = read_user_patterns()
    for key, p in new.items():
        user["patterns"].setdefault(key, p)
    write_json(PATTERNS_FILE, user)


def file_hash(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()[:12]


# ---------- locks ----------

def touch_lock(name: str) -> None:
    """Keep a long-held lock from looking stale."""
    try:
        os.utime(INBOX / f"{name}.lock")
    except FileNotFoundError:
        pass


@contextlib.contextmanager
def lock(name: str, wait: float = 10.0, stale: float = 900.0):
    """A lock file in inbox/. Raises TimeoutError when another process holds it longer than `wait`."""
    path = INBOX / f"{name}.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + wait
    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{os.getpid()} {now_iso()}".encode())
            os.close(fd)
            break
        except FileExistsError:
            try:
                if time.time() - path.stat().st_mtime > stale:
                    path.unlink()
                    continue
            except FileNotFoundError:
                continue
            if time.time() >= deadline:
                raise TimeoutError(f"{name} is locked")
            time.sleep(0.2)
    try:
        yield
    finally:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
