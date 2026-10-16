"""Keep what the user typed: new messages in Claude Code's conversation files go to data/inbox/messages.jsonl."""

from __future__ import annotations

from pathlib import Path

from . import store
from .config import TRANSCRIPTS, load_config
from .transcripts import all_transcripts, read_messages


def _keep(messages: list[dict], seen: set[str]) -> list[dict]:
    kept = []
    for m in messages:
        m["id"] = store.message_id(m["text"], m["ts"])
        if m["id"] in seen:
            continue
        seen.add(m["id"])
        kept.append({k: m[k] for k in ("id", "ts", "session", "project", "text")})
    return kept


def capture_transcript(path: Path) -> int:
    """New user messages in one transcript since the last capture. Returns how many were added."""
    config = load_config()
    if path.parent.name in config["skip_projects"] or not path.exists():
        return 0
    with store.lock("capture", wait=15):
        state = store.read_state()
        offsets = state.setdefault("offsets", {})
        key = str(path)
        messages, offset = read_messages(path, offsets.get(key, 0))
        seen = {m["id"] for m in store.read_messages()}
        kept = _keep(messages, seen)
        store.append_messages(kept)
        offsets[key] = offset
        store.write_state(state)
    return len(kept)


def backfill(root: Path = TRANSCRIPTS) -> int:
    """Every conversation file under `root` (a Claude Code projects folder), from where the last read stopped.
    Safe to repeat: files are read from their saved offsets and known messages are skipped."""
    added = 0
    for path in all_transcripts(root):
        added += capture_transcript(path)
    return added
