"""The Claude accounts this person uses, kept in data/accounts.json (private: never committed).

Each account says where its conversations are (a Claude Code folder: the normal ~/.claude, or another folder
used with CLAUDE_CONFIG_DIR) and how the app may call Claude with it: that folder's Claude Code sign-in, or an
Anthropic API key. Analysis tries the accounts in order and moves on when one hits its usage limit.

An API key is stored as typed (the file is private to this PC) and is only ever shown masked.
Only the account's email is read from Claude Code's settings; its credentials are never opened.
"""

from __future__ import annotations

import json
import os
import secrets
import threading
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from . import store
from .config import CLAUDE_HOME, DATA

ACCOUNTS_FILE = DATA / "accounts.json"
METHODS = ("claude-code", "api-key")
LIMIT_MEMO_SECONDS = 15 * 60   # an account that just hit its limit is tried last for a while


@dataclass(frozen=True)
class Account:
    id: str
    name: str
    folder: str = ""              # Claude Code folder; "" = the normal one (~/.claude)
    method: str = "claude-code"   # "claude-code" (its sign-in) or "api-key"
    api_key: str = ""

    @property
    def uses_default_folder(self) -> bool:
        return not self.folder

    @property
    def home(self) -> Path:
        """The Claude Code folder: settings, sign-in and conversations."""
        return Path(os.path.expandvars(os.path.expanduser(self.folder))) if self.folder else CLAUDE_HOME

    @property
    def projects(self) -> Path:
        """Where Claude Code keeps this account's conversations (one folder per project)."""
        return self.home / "projects"


def new_id() -> str:
    return secrets.token_hex(4)


def load_accounts(path: Path = ACCOUNTS_FILE) -> list[Account]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    accounts = []
    for a in raw.get("accounts") or []:
        if isinstance(a, dict) and a.get("id") and str(a.get("name") or "").strip():
            method = a.get("method") if a.get("method") in METHODS else "claude-code"
            accounts.append(Account(id=str(a["id"]), name=str(a["name"]).strip(), folder=str(a.get("folder") or "").strip(),
                                    method=method, api_key=str(a.get("api_key") or "").strip()))
    return accounts


def save_accounts(accounts: list[Account], path: Path = ACCOUNTS_FILE) -> None:
    store.write_json(path, {"accounts": [asdict(a) for a in accounts]})


def update(account: Account, **changes) -> Account:
    return replace(account, **{k: v for k, v in changes.items() if v is not None})


def masked_key(key: str) -> str | None:
    """'sk-ant-…a1b2' style, enough to recognise a key without showing it."""
    if not key:
        return None
    return f"{key[:7]}…{key[-4:]}" if len(key) > 14 else "…" + key[-2:]


def settings_file(account: Account) -> Path:
    """Claude Code's settings file with the signed-in account: ~/.claude.json for the normal folder (unless
    CLAUDE_CONFIG_DIR moves it), <folder>/.claude.json for another folder."""
    if account.folder or os.environ.get("CLAUDE_CONFIG_DIR"):
        for name in (".claude.json", ".config.json"):
            if (account.home / name).exists():
                return account.home / name
        return account.home / ".claude.json"
    return Path.home() / ".claude.json"


def child_env(account: Account) -> dict[str, str]:
    """The environment for a `claude` child process signed in with this account's folder."""
    env = dict(os.environ)
    if account.folder:
        env["CLAUDE_CONFIG_DIR"] = str(account.home)
    return env


_email_cache: dict[str, tuple[float, str | None]] = {}
_lock = threading.Lock()


def account_email(account: Account) -> str | None:
    """The email Claude Code is signed in with in this account's folder (cached for a minute)."""
    path = settings_file(account)
    key = str(path)
    now = time.monotonic()
    with _lock:
        cached = _email_cache.get(key)
        if cached and now - cached[0] < 60:
            return cached[1]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        email = (data.get("oauthAccount") or {}).get("emailAddress") or None
    except (OSError, ValueError, AttributeError):
        email = None
    with _lock:
        _email_cache[key] = (now, email)
    return email


def signed_in(account: Account) -> bool:
    """Claude Code has a sign-in in this account's folder (the credentials file exists; it is never opened)."""
    return (account.home / ".credentials.json").exists() or account_email(account) is not None


def can_analyze(account: Account) -> bool:
    return bool(account.api_key) if account.method == "api-key" else signed_in(account)


def conversation_files(account: Account) -> list[Path]:
    """Claude Code's conversation files in this account's folder (top-level sessions only)."""
    try:
        return sorted(account.projects.glob("*/*.jsonl"))
    except OSError:
        return []


# ---------- usage limits ----------

_limited: dict[str, tuple[float, str | None]] = {}   # account id -> (when, reset text)


def mark_limited(account: Account, resets: str | None = None) -> None:
    with _lock:
        _limited[account.id] = (time.time(), resets)


def clear_limited(account: Account) -> None:
    with _lock:
        _limited.pop(account.id, None)


def limited_info(account: Account) -> tuple[float, str | None] | None:
    """(when it hit its limit, the reset time text) if that was in the last 15 minutes."""
    with _lock:
        info = _limited.get(account.id)
    if info and time.time() - info[0] < LIMIT_MEMO_SECONDS:
        return info
    return None


def ordered(accounts: list[Account]) -> list[Account]:
    """The order to try them: as configured, with the ones that just hit a limit last."""
    return sorted(accounts, key=lambda a: limited_info(a) is not None)
