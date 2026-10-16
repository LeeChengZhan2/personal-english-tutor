"""Paths, settings and the Claude Code binary."""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BATCHES = DATA / "batches"
PATTERNS_FILE = DATA / "patterns.json"
DB_FILE = DATA / "tutor.db"     # the app's practice progress (git-ignored)
BACKUPS = DATA / "backups"
# Everything personal lives under data/, which git ignores as a whole: a fresh clone has no one's data.
INBOX = DATA / "inbox"               # captured messages, the model's raw answers, capture offsets
LOGS = DATA / "logs"
STATE_FILE = INBOX / "state.json"    # how far each conversation file has been read
CONFIG_FILE = DATA / "config.json"
BASE_CATALOG = Path(__file__).with_name("catalog.json")  # the mistake patterns every new user starts with
PROMPTS = ROOT / "prompts"
WEB_DIST = ROOT / "web" / "dist"    # the built app (pnpm -C web build)

CLAUDE_HOME = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
TRANSCRIPTS = CLAUDE_HOME / "projects"

DEFAULTS = {
    # Model for finding mistakes; sonnet keeps the analysis off the user's Opus limits.
    "analyze_model": "sonnet",
    # Messages per analysis call.
    "batch_size": 30,
    # Projects (folder names under ~/.claude/projects) never captured.
    "skip_projects": [],
    # The local app (uv run tutor serve).
    "server_host": "127.0.0.1",
    "server_port": 8765,
    # Models for the app's AI checks: quick answers (typed-answer check) and the rest.
    "ai_models": {"quick": "haiku", "default": "sonnet"},
    "ai_timeout_seconds": 75,
    "ai_concurrency": 2,
}


def app_url(config: dict | None = None) -> str:
    config = config or load_config()
    host = config.get("server_host") or "127.0.0.1"
    if host in ("0.0.0.0", "::"):
        host = "127.0.0.1"
    return f"http://{host}:{config.get('server_port') or 8765}"


def load_config() -> dict:
    config = dict(DEFAULTS)
    try:
        config.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
    except FileNotFoundError:
        pass
    return config


def save_config(config: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _version_key(path: Path) -> tuple:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", str(path))
    return tuple(int(n) for n in match.groups()) if match else (0, 0, 0)


def find_claude() -> str | None:
    """The newest Claude Code binary: $ENGLISH_TUTOR_CLAUDE, PATH, or the VS Code extension."""
    explicit = os.environ.get("ENGLISH_TUTOR_CLAUDE")
    if explicit and Path(explicit).exists():
        return explicit
    on_path = shutil.which("claude")
    if on_path:
        return on_path
    candidates = list((Path.home() / ".vscode" / "extensions").glob("anthropic.claude-code-*/resources/native-binary/claude*"))
    candidates += list((Path.home() / ".local" / "bin").glob("claude*"))
    candidates = [c for c in candidates if c.is_file() and c.suffix.lower() in (".exe", "")]
    if not candidates:
        return None
    return str(max(candidates, key=_version_key))
