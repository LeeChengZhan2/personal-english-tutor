"""Run a headless Claude Code (`claude -p`) and read its JSON result."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

from .config import INBOX, find_claude

NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


class ClaudeError(RuntimeError):
    """`kind` is one of: usage_limit, auth, overloaded, cancelled, timeout, not_installed, failed."""

    def __init__(self, message: str, kind: str = "failed", resets: str | None = None):
        super().__init__(message)
        self.kind = kind
        self.resets = resets


def classify(result: dict, text: str) -> tuple[str, str | None]:
    """What went wrong, from the result's error fields (newer Claude Code) or its message."""
    status = result.get("api_error_status")
    api_error = str(result.get("api_error") or "")
    resets = re.search(r"resets? ([^.\n·|]+)", text)
    if api_error in ("usage_limit_reached", "model_requires_usage_credits") or status == 429 or re.search(
            r"usage limit|hit your (\w+ )?limit|limit reached|rate.?limit|out of (extra )?usage|credit balance", text, re.I):
        return "usage_limit", resets.group(1).strip() if resets else None
    if status in (401, 403) or api_error in ("gateway_signin_required", "gateway_session_expired", "invalid_credential_header") \
            or re.search(r"/login|not logged in|log ?in again|invalid api key|oauth token|authentication|unauthori[sz]ed", text, re.I):
        return "auth", None
    if status in (500, 502, 503, 529) or re.search(r"overloaded|api error: 5\d\d", text, re.I):
        return "overloaded", None
    return "failed", None


def _kill(proc: subprocess.Popen) -> None:
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, creationflags=NO_WINDOW)
    try:
        proc.kill()
    except OSError:
        pass
    try:
        proc.communicate(timeout=5)
    except (subprocess.TimeoutExpired, ValueError, OSError):
        pass


def run(
    prompt: str,
    *,
    model: str,
    schema: dict | None = None,
    tools: str | None = "",
    workdir: Path | None = None,
    timeout: float = 1200,
    config_dir: str | None = None,
    cancel: threading.Event | None = None,
) -> dict:
    """One headless turn. Returns the CLI's result object (with `structured_output` when `schema` is given).

    --safe-mode turns off hooks, CLAUDE.md, skills and MCP; --no-session-persistence keeps this run out
    of the user's session history (so it is never read back as the user's own writing).
    tools="" gives the model no tools at all. `config_dir` runs it signed in with another Claude Code folder.
    Setting `cancel` stops the run at once (the process is killed).
    """
    exe = find_claude()
    if not exe:
        raise ClaudeError("Claude Code was not found. Install it, or set ENGLISH_TUTOR_CLAUDE to the claude executable.",
                          kind="not_installed")
    args = [exe, "-p", "--safe-mode", "--no-session-persistence", "--model", model, "--output-format", "json"]
    if schema is not None:
        args += ["--json-schema", json.dumps(schema, separators=(",", ":"))]
    if tools is not None:
        args += ["--tools", tools]
    if workdir is None:
        workdir = INBOX / "headless"
    workdir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    if config_dir:
        env["CLAUDE_CONFIG_DIR"] = config_dir
    proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            encoding="utf-8", errors="replace", cwd=workdir, env=env, creationflags=NO_WINDOW)
    deadline = time.monotonic() + timeout
    first = True
    while True:
        try:
            out, err = proc.communicate(input=prompt if first else None, timeout=0.5)
            break
        except subprocess.TimeoutExpired:
            first = False
            if cancel is not None and cancel.is_set():
                _kill(proc)
                raise ClaudeError("stopped", kind="cancelled") from None
            if time.monotonic() > deadline:
                _kill(proc)
                raise ClaudeError(f"claude timed out after {int(timeout)}s", kind="timeout") from None
    out = (out or "").strip()
    try:
        result = json.loads(out[out.index("{"):]) if out else {}
    except ValueError:
        result = {}
    if proc.returncode != 0 or not result or result.get("is_error"):
        detail = str(result.get("result") or (err or out)[-800:])
        kind, resets = classify(result, detail)
        raise ClaudeError(f"claude failed (exit {proc.returncode}): {detail}", kind=kind, resets=resets)
    return result
