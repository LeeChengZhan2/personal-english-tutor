"""What every request shares: where the files are, the lesson cache, and a way to open the database."""

from __future__ import annotations

import contextlib
import sqlite3
import statistics
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from fastapi import Request

from coach import accounts, config as coach_config, db, insights, srs
from coach.lessons import LessonStore


@dataclass(frozen=True)
class Paths:
    root: Path
    batches: Path
    grammar: Path
    patterns: Path
    db: Path
    backups: Path
    inbox: Path
    web_dist: Path
    accounts: Path

    @classmethod
    def default(cls) -> Paths:
        return cls(root=coach_config.ROOT, batches=coach_config.BATCHES, grammar=coach_config.GRAMMAR,
                   patterns=coach_config.PATTERNS_FILE, db=coach_config.DB_FILE, backups=coach_config.BACKUPS,
                   inbox=coach_config.INBOX, web_dist=coach_config.WEB_DIST, accounts=accounts.ACCOUNTS_FILE)

    @classmethod
    def under(cls, root: Path) -> Paths:
        """The same layout under another folder (tests)."""
        data = root / "data"
        return cls(root=root, batches=data / "batches", grammar=data / "grammar", patterns=data / "patterns.json",
                   db=data / "tutor.db", backups=data / "backups", inbox=data / "inbox",
                   web_dist=root / "web" / "dist", accounts=data / "accounts.json")


class AppContext:
    def __init__(self, paths: Paths, config: dict | None = None, clock: Callable[[], int] | None = None):
        self.paths = paths
        self.config = config if config is not None else coach_config.load_config()
        self.clock = clock or srs.now_ms
        self.lessons = LessonStore(paths.batches, paths.patterns)
        self._migrated = False
        self._migrate_lock = threading.Lock()
        self.accounts_lock = threading.Lock()   # one change to data/accounts.json at a time

    @contextlib.contextmanager
    def conn(self) -> Iterator[sqlite3.Connection]:
        """A connection to the progress database (created and migrated on first use)."""
        if not self._migrated:
            with self._migrate_lock:
                if not self._migrated:
                    self.paths.db.parent.mkdir(parents=True, exist_ok=True)
                    first = db.connect(self.paths.db)
                    try:
                        db.migrate(first, self.paths.backups)
                    finally:
                        first.close()
                    self._migrated = True
        conn = db.connect(self.paths.db)
        try:
            yield conn
        finally:
            conn.close()

    def view(self, conn: sqlite3.Connection) -> insights.View:
        """The lessons plus the learner's progress, read in one consistent snapshot."""
        snap = self.lessons.snapshot()
        now = self.clock()
        with db.read_tx(conn):
            states = db.load_states(conn)
            days = db.day_totals(conn)
            rounds = db.rounds(conn)
            settings = db.get_settings(conn)
            new_today = db.cards_first_seen_on(conn, srs.day_key(now))
            seconds = db.recent_answer_seconds(conn)
        per_item = min(60.0, max(5.0, statistics.median(seconds))) if len(seconds) >= 5 else 15.0
        return insights.View(snap=snap, states=states, days=days, rounds=rounds, settings=settings, now_ms=now,
                             cards_new_today=new_today, sec_per_item=per_item)

    def accounts(self) -> list[accounts.Account]:
        return accounts.load_accounts(self.paths.accounts)

    def save_accounts(self, items: list[accounts.Account]) -> None:
        accounts.save_accounts(items, self.paths.accounts)


def get_ctx(request: Request) -> AppContext:
    return request.app.state.ctx
