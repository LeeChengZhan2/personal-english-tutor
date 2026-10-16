"""The "Update my lessons" job: one at a time, in a background thread, with progress the page polls."""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime

from coach import run, store
from coach.accounts import Account, conversation_files
from coach.llm import LLMError

from .context import AppContext
from .errors import ApiException

log = logging.getLogger("tutor")

MESSAGES = {
    "not_configured": "Add your Claude account in Settings first.",
    "not_installed": "Claude Code isn't installed on this PC. Use an account with an API key instead.",
    "auth": "Claude couldn't sign in with {account}. Check that account in Settings.",
    "busy": "Another update is already running.",
}


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class UpdateManager:
    def __init__(self, ctx: AppContext):
        self.ctx = ctx
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_file = ctx.paths.inbox / "last_update.json"
        self._state: dict = self._idle()

    def _idle(self) -> dict:
        return {"state": "idle", "stage": None, "done": 0, "total": 0, "accounts": [], "started_at": None,
                "finished_at": None, "result": None, "error": None}

    def _last_finished(self) -> str | None:
        try:
            return json.loads(self._last_file.read_text(encoding="utf-8")).get("finished_at")
        except (OSError, ValueError):
            return None

    def status(self) -> dict:
        with self._lock:
            return {**self._state, "last_finished_at": self._last_finished()}

    @property
    def running(self) -> bool:
        with self._lock:
            return self._state["state"] == "running"

    def start(self, accounts: list[Account]) -> dict:
        if not accounts:
            raise ApiException(400, "not_configured", MESSAGES["not_configured"])
        with self._lock:
            if self._state["state"] == "running":
                raise ApiException(409, "busy", MESSAGES["busy"])
            self._cancel = threading.Event()
            self._state = {**self._idle(), "state": "running", "stage": "reading", "accounts": [a.name for a in accounts],
                           "started_at": _now()}
            self._thread = threading.Thread(target=self._run, args=(accounts, self._cancel), name="update", daemon=True)
            self._thread.start()
        return self.status()

    def stop(self) -> dict:
        self._cancel.set()
        return self.status()

    def shutdown(self) -> None:
        self._cancel.set()

    def _progress(self, stage: str, done: int, total: int) -> None:
        with self._lock:
            if self._state["state"] == "running":
                self._state.update(stage=stage, done=done, total=total)

    def _run(self, accounts: list[Account], cancel: threading.Event) -> None:
        before = self.ctx.lessons.snapshot()
        cards_before, words_before = len(before.cards), len(before.words)
        state, error, report = "done", None, None
        try:
            report = run.run(accounts, parallel=int(self.ctx.config.get("ai_concurrency") or 2),
                             on_progress=self._progress, cancel=cancel)
            if report.get("stopped"):
                state = "stopped"
        except TimeoutError:
            state, error = "failed", {"code": "busy", "message": "Another update is already running (maybe from the command line)."}
        except LLMError as e:
            if e.kind == "cancelled":
                state = "stopped"
            elif e.kind == "usage_limit":
                when = f" It resets {e.resets}." if e.resets else ""
                state, error = "failed", {"code": "usage_limit",
                                          "message": f"Every account has reached its usage limit.{when} Try again later."}
            else:
                text = MESSAGES.get(e.kind, "The update stopped: {message}").format(account=e.account or "an account",
                                                                                    message=str(e)[:300])
                state, error = "failed", {"code": e.kind, "message": text}
        except Exception as e:  # noqa: BLE001 - shown on the page; details in the log
            log.exception("update failed")
            state, error = "failed", {"code": "failed", "message": f"The update stopped: {e}"}
        self.ctx.lessons.invalidate()
        after = self.ctx.lessons.snapshot()
        result = None
        if report is not None:
            result = {"captured": report["captured"], "analyzed": report["analyzed"], "waiting": report["waiting"],
                      "new_cards": max(0, len(after.cards) - cards_before), "new_words": max(0, len(after.words) - words_before),
                      "batches": len(report["batches"])}
        finished = _now()
        with self._lock:
            self._state.update(state=state, stage="done" if state == "done" else self._state["stage"],
                               finished_at=finished, result=result, error=error)
        if state == "done":
            try:
                store.write_json(self._last_file, {"finished_at": finished, "result": result})
            except OSError as e:
                log.warning("couldn't save the update summary: %s", e)


def preview(accounts: list[Account]) -> dict:
    """How much is new, without reading or analyzing anything: files that grew since the last update."""
    offsets = store.read_state().get("offsets", {})
    rows = []
    for a in accounts:
        files = conversation_files(a)
        changed = 0
        for path in files:
            try:
                if path.stat().st_size > offsets.get(str(path), 0):
                    changed += 1
            except OSError:
                continue
        rows.append({"id": a.id, "name": a.name, "files": len(files), "changed": changed})
    return {"accounts": rows, "waiting": len(store.pending_messages())}
