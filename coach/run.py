"""One update: read new messages from the accounts' Claude Code conversations, find the mistakes, add vocabulary
and new words, and write the grammar lessons that are due.

Started by the app's "Update my lessons" button (or `python -m coach run`). Each conversation file is read from
where the last update stopped, and only messages not analyzed yet are sent to Claude, so nothing is done twice.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from pathlib import Path

from . import analyze, capture, grammar, new_words, srs, store, vocab
from .accounts import Account
from .llm import LLMError

log = logging.getLogger("coach")

# (stage, done, total); stages: reading, analyzing, vocabulary, new_words, grammar, done
Progress = Callable[[str, int, int], None]


def folders_of(accounts: list[Account]) -> list[Path]:
    """Each account's conversations folder, once (two accounts can share Claude Code's normal folder)."""
    seen: dict[str, Path] = {}
    for a in accounts:
        if a.projects.is_dir():
            seen.setdefault(str(a.projects.resolve()).lower(), a.projects)
    return list(seen.values())


def run(accounts: list[Account], *, parallel: int = 2, on_progress: Progress | None = None,
        cancel: threading.Event | None = None) -> dict:
    """Raises TimeoutError if another update is running, LLMError if no account can analyze."""
    if not accounts:
        raise LLMError("No Claude account is set up. Add one in Settings.", kind="not_configured")
    report: Progress = on_progress or (lambda stage, done, total: None)
    stopped = lambda: cancel is not None and cancel.is_set()  # noqa: E731
    with store.lock("run", wait=0, stale=1800):
        roots = folders_of(accounts)
        report("reading", 0, len(roots))
        captured = 0
        for i, root in enumerate(roots, 1):
            if stopped():
                break
            captured += capture.backfill(root)
            report("reading", i, len(roots))
        waiting = len(store.pending_messages())
        batches: list[str] = []
        if waiting and not stopped():
            report("analyzing", 0, 1)
            batches = analyze.analyze_pending(parallel=parallel, accounts=accounts, cancel=cancel,
                                              on_batch=lambda d, t: report("analyzing", d, t))
        filled = 0
        if not stopped() and vocab.missing():
            report("vocabulary", 0, 1)
            filled = vocab.fill_missing(parallel=parallel, accounts=accounts, cancel=cancel,
                                        on_batch=lambda d, t: report("vocabulary", d, t))
        fresh = 0
        if not stopped() and new_words.missing():
            report("new_words", 0, 1)
            fresh = new_words.fill_missing(parallel=parallel, accounts=accounts, cancel=cancel,
                                           on_batch=lambda d, t: report("new_words", d, t))
        written = 0
        if not stopped():
            snap = grammar.snapshot()
            keys = grammar.due(snap, srs.now_ms())
            if keys:
                report("grammar", 0, len(keys))
                written = grammar.write_lessons(snap, keys, parallel=parallel, accounts=accounts, cancel=cancel,
                                                on_done=lambda d, t: report("grammar", d, t))
        left = len(store.pending_messages())
        report("done", 1, 1)
    log.info("update: %d new messages read, %d analyzed into %d batches, %d still waiting",
             captured, waiting - left, len(batches), left)
    return {"captured": captured, "analyzed": waiting - left, "batches": batches, "vocabulary": filled,
            "new_words": fresh, "grammar": written, "waiting": left, "stopped": stopped()}
