"""Health, the app's opening data (bootstrap), diagnostics (status) and practice settings."""

from __future__ import annotations

import threading
import time
from datetime import datetime

from fastapi import APIRouter, Depends

from coach import accounts, db, insights
from coach.config import app_url, find_claude

from .. import __version__
from ..context import AppContext, get_ctx
from ..models import ApiError, Bootstrap, Health, PracticeSettings, SettingsUpdate, Status

router = APIRouter(prefix="/api", tags=["meta"], responses={422: {"model": ApiError}, 500: {"model": ApiError}})

_claude_cache: tuple[float, str | None] = (0.0, None)
_claude_lock = threading.Lock()


def claude_path() -> str | None:
    """find_claude() searches folders, so its answer is kept for a minute."""
    global _claude_cache
    with _claude_lock:
        when, path = _claude_cache
        if time.monotonic() - when > 60:
            path = find_claude()
            _claude_cache = (time.monotonic(), path)
        return path


def account_ready(account: accounts.Account) -> bool:
    """Can be used for analysis now: an API key is saved, or Claude Code is installed and signed in."""
    if account.method == "api-key":
        return bool(account.api_key)
    return bool(claude_path()) and accounts.signed_in(account)


def ai_info(ctx: AppContext) -> dict:
    infos = []
    for account in ctx.accounts():
        limited = accounts.limited_info(account)
        infos.append({
            "id": account.id, "name": account.name, "method": account.method,
            "email": accounts.account_email(account) if account.method == "claude-code" else None,
            "ready": account_ready(account), "limited_until": (limited[1] or "soon") if limited else None,
        })
    available = any(i["ready"] for i in infos)
    reason = None
    if not infos:
        reason = "Add your Claude account in Settings to make lessons and use the AI checks."
    elif not available:
        reason = "None of your accounts can reach Claude right now. Check them in Settings."
    return {"available": available, "reason": reason, "accounts": infos}


@router.get("/health", response_model=Health)
def health() -> dict:
    return {"version": __version__}


@router.get("/bootstrap", response_model=Bootstrap)
def bootstrap(ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.conn() as conn:
        view = ctx.view(conn)
    return {
        "version": __version__, "lessons_version": view.snap.version, "app_url": app_url(ctx.config),
        "settings": view.settings, "counts": insights.counts(view), "streak": insights.streak(view.days, view.now_ms),
        "today": insights.today_totals(view.days, view.now_ms), "ai": ai_info(ctx),
        "pipeline": insights.pipeline_status(ctx.paths.inbox, view.snap),
    }


@router.get("/status", response_model=Status)
def status(ctx: AppContext = Depends(get_ctx)) -> dict:
    snap = ctx.lessons.snapshot()
    with ctx.conn() as conn:
        db_version = conn.execute("PRAGMA user_version").fetchone()[0]
    return {
        "version": __version__, "root": str(ctx.paths.root), "db_path": str(ctx.paths.db), "db_version": db_version,
        "claude_path": claude_path(),
        "lessons": {"batches": snap.batches, "app_lessons": snap.app_lessons, "messages": len(snap.messages),
                    "cards": len(snap.cards), "words": len(snap.words),
                    "loaded_at": datetime.fromtimestamp(snap.loaded_at).astimezone().isoformat(timespec="seconds"),
                    "errors": snap.errors},
        "ai": ai_info(ctx), "pipeline": insights.pipeline_status(ctx.paths.inbox, snap),
    }


@router.get("/settings", response_model=PracticeSettings)
def get_settings(ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.conn() as conn:
        return db.get_settings(conn)


@router.put("/settings", response_model=PracticeSettings)
def put_settings(update: SettingsUpdate, ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.conn() as conn, db.write_tx(conn):
        return db.put_settings(conn, update.model_dump(exclude_none=True))
