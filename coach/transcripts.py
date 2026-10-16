"""Read Claude Code session transcripts (~/.claude/projects/*/*.jsonl) and keep only what the user typed."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterator

# Context Claude Code adds around the user's words: never the user's own writing.
_STRIP = [
    re.compile(r"<(ide_opened_file|ide_selection|system-reminder|ide_diagnostics)>.*?</\1>", re.S),
    re.compile(r"<pasted_content\b[^>]*>.*?</pasted_content\b[^>]*>", re.S),
    re.compile(r"^\[Image[^\]]*\]\s*$", re.M),
    re.compile(r"\[Image #\d+\]"),
]
# A message that starts like this was not typed by the user.
_SKIP_PREFIXES = (
    "<command-name>",
    "<command-message>",
    "<local-command",
    "<task-notification>",
    "<bash-input>",
    "<bash-stdout>",
    "This session is being continued",
    "Base directory for this skill",
    "[Request interrupted by user",
    "Caveat: The messages below",
    "[SYSTEM NOTIFICATION",
    "[Artifact comment",
)


def clean_text(text: str) -> str:
    """The user's own words in one message, or "" when there are none."""
    stripped = text.strip()
    if stripped.startswith(_SKIP_PREFIXES):
        return ""
    for pattern in _STRIP:
        stripped = pattern.sub("", stripped)
    stripped = re.sub(r"\n{3,}", "\n\n", stripped).strip()
    return "" if stripped.startswith(_SKIP_PREFIXES) else stripped


def user_text(record: dict) -> str:
    """The typed text of one transcript record, or "" when the record is not a message the user typed."""
    if record.get("type") != "user":
        return ""
    if record.get("isMeta") or record.get("isCompactSummary") or record.get("isSidechain"):
        return ""
    origin = record.get("origin")
    if isinstance(origin, dict) and origin.get("kind") not in (None, "human"):
        return ""
    content = (record.get("message") or {}).get("content")
    if isinstance(content, str):
        blocks = [{"type": "text", "text": content}]
    elif isinstance(content, list):
        blocks = content
    else:
        return ""
    if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in blocks):
        return ""
    parts = [clean_text(b.get("text", "")) for b in blocks if isinstance(b, dict) and b.get("type") == "text"]
    return "\n\n".join(p for p in parts if p)


def message_from(record: dict, path: Path) -> dict | None:
    text = user_text(record)
    if not text:
        return None
    return {
        "uuid": record.get("uuid") or "",
        "session": record.get("sessionId") or path.stem,
        "ts": record.get("timestamp") or "",
        "project": path.parent.name,
        "cwd": record.get("cwd") or "",
        "text": text,
    }


def read_messages(path: Path, offset: int = 0) -> tuple[list[dict], int]:
    """User messages in a transcript from byte `offset` on, and the offset after the last complete line."""
    messages: list[dict] = []
    with open(path, "rb") as f:
        f.seek(offset)
        data = f.read()
    end = data.rfind(b"\n")
    if end < 0:
        return messages, offset
    for line in data[: end + 1].splitlines():
        try:
            record = json.loads(line)
        except (ValueError, UnicodeDecodeError):
            continue
        message = message_from(record, path)
        if message:
            messages.append(message)
    return messages, offset + end + 1


def all_transcripts(root: Path) -> Iterator[Path]:
    """Top-level session files only; subagent transcripts live in subfolders and are not the user's writing."""
    yield from sorted(root.glob("*/*.jsonl"))
