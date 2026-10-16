"""Practice progress in SQLite (data/tutor.db): card and word states, daily stats, settings, sessions.

Lessons stay in data/batches; only what the learner does is stored here. Each request opens its own
connection; WAL lets the app read while a practice answer is written.
"""

from __future__ import annotations

import contextlib
import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from .srs import State

SCHEMA_VERSION = 1

MIGRATIONS: list[tuple[int, str]] = [
    (1, """
CREATE TABLE item_state (
  item_id   TEXT PRIMARY KEY,
  item_type TEXT NOT NULL CHECK (item_type IN ('card', 'word', 'unknown')),
  box       INTEGER NOT NULL CHECK (box BETWEEN 0 AND 7),
  due_ms    INTEGER NOT NULL,
  n_seen    INTEGER NOT NULL DEFAULT 0,
  n_right   INTEGER NOT NULL DEFAULT 0,
  n_wrong   INTEGER NOT NULL DEFAULT 0,
  n_lapses  INTEGER NOT NULL DEFAULT 0,
  first_ms  INTEGER NOT NULL,
  last_ms   INTEGER NOT NULL,
  first_day TEXT NOT NULL
) STRICT;
CREATE INDEX item_state_due ON item_state(due_ms);
CREATE INDEX item_state_first_day ON item_state(first_day);

CREATE TABLE day_stats (
  day      TEXT NOT NULL,
  source   TEXT NOT NULL CHECK (source IN ('local', 'artifact')),
  answered INTEGER NOT NULL DEFAULT 0,
  correct  INTEGER NOT NULL DEFAULT 0,
  seconds  INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (day, source)
) STRICT;

CREATE TABLE counters (key TEXT PRIMARY KEY, value INTEGER NOT NULL) STRICT;
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL) STRICT;

CREATE TABLE sessions (
  id          TEXT PRIMARY KEY,
  client_id   TEXT,
  mode        TEXT NOT NULL,
  pattern     TEXT,
  word_kind   TEXT,
  created_ms  INTEGER NOT NULL,
  finished_ms INTEGER,
  items       TEXT NOT NULL
) STRICT;
CREATE UNIQUE INDEX sessions_client ON sessions(client_id) WHERE client_id IS NOT NULL;

CREATE TABLE answers (
  session_id  TEXT NOT NULL,
  item_id     TEXT NOT NULL,
  ref_type    TEXT NOT NULL,
  ref_id      TEXT,
  kind        TEXT NOT NULL,
  correct     INTEGER NOT NULL CHECK (correct IN (0, 1)),
  seconds     REAL NOT NULL,
  answered_ms INTEGER NOT NULL,
  day         TEXT NOT NULL,
  box_after   INTEGER,
  PRIMARY KEY (session_id, item_id)
) STRICT;
CREATE INDEX answers_day ON answers(day);

CREATE TABLE imports (
  fingerprint TEXT PRIMARY KEY,
  kind        TEXT NOT NULL,
  imported_ms INTEGER NOT NULL,
  summary     TEXT NOT NULL
) STRICT;
"""),
]

DEFAULT_SETTINGS = {"zh": False, "round_size": 8, "new_per_day": 12}
ROUND_SIZES = (5, 8, 12, 16)
NEW_PER_DAY = (6, 12, 20, 30)


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=5, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate(conn: sqlite3.Connection, backup_dir: Path | None = None) -> int:
    """Bring the schema up to SCHEMA_VERSION. An existing database is copied to backup_dir first."""
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version > SCHEMA_VERSION:
        raise RuntimeError(f"data/tutor.db is from a newer version of the app (schema {version}); update the app")
    if version == SCHEMA_VERSION:
        return version
    conn.execute("PRAGMA journal_mode = WAL")
    if version > 0 and backup_dir is not None:
        backup_to(conn, Path(backup_dir) / f"tutor-v{version}-{time.strftime('%Y%m%d-%H%M%S')}.db")
    for target, sql in MIGRATIONS:
        if target > version:
            conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {target};\nCOMMIT;")
    return SCHEMA_VERSION


@contextlib.contextmanager
def write_tx(conn: sqlite3.Connection):
    """One write transaction, taken up front so two writers queue instead of failing half-way."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


@contextlib.contextmanager
def read_tx(conn: sqlite3.Connection):
    """A consistent view across several queries."""
    conn.execute("BEGIN")
    try:
        yield conn
    finally:
        conn.execute("COMMIT")


def backup_to(conn: sqlite3.Connection, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    target = sqlite3.connect(path)
    try:
        conn.backup(target)
    finally:
        target.close()
    return path


def daily_backup(conn: sqlite3.Connection, backup_dir: Path, keep: int = 14) -> Path | None:
    """At most one backup a day (the app does this on start); keeps the newest `keep`."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    today = time.strftime("%Y%m%d")
    existing = sorted(backup_dir.glob("tutor-daily-*.db"))
    if any(p.name == f"tutor-daily-{today}.db" for p in existing):
        return None
    path = backup_to(conn, backup_dir / f"tutor-daily-{today}.db")
    for old in sorted(backup_dir.glob("tutor-daily-*.db"))[:-keep]:
        with contextlib.suppress(OSError):
            old.unlink()
    return path


def _first_day(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d")


# ---------- item states ----------

def _row_state(row: sqlite3.Row) -> State:
    return State(box=row["box"], due_ms=row["due_ms"], seen=row["n_seen"], right=row["n_right"], wrong=row["n_wrong"],
                 lapses=row["n_lapses"], first_ms=row["first_ms"], last_ms=row["last_ms"])


def load_states(conn: sqlite3.Connection) -> dict[str, State]:
    return {row["item_id"]: _row_state(row) for row in conn.execute("SELECT * FROM item_state")}


def load_state(conn: sqlite3.Connection, item_id: str) -> State | None:
    row = conn.execute("SELECT * FROM item_state WHERE item_id = ?", (item_id,)).fetchone()
    return _row_state(row) if row else None


def put_state(conn: sqlite3.Connection, item_id: str, item_type: str, st: State) -> None:
    conn.execute(
        """INSERT INTO item_state (item_id, item_type, box, due_ms, n_seen, n_right, n_wrong, n_lapses, first_ms, last_ms, first_day)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(item_id) DO UPDATE SET item_type = excluded.item_type, box = excluded.box, due_ms = excluded.due_ms,
             n_seen = excluded.n_seen, n_right = excluded.n_right, n_wrong = excluded.n_wrong, n_lapses = excluded.n_lapses,
             first_ms = excluded.first_ms, last_ms = excluded.last_ms, first_day = excluded.first_day""",
        (item_id, item_type, st.box, st.due_ms, st.seen, st.right, st.wrong, st.lapses, st.first_ms, st.last_ms,
         _first_day(st.first_ms)),
    )


def merge_states(conn: sqlite3.Connection, states: dict[str, tuple[str, State]]) -> tuple[int, int, int]:
    """Add states from an import; where both sides have one, the more recently answered wins.
    Returns (added, updated, kept). Call inside write_tx."""
    added = updated = kept = 0
    for item_id, (item_type, st) in states.items():
        current = load_state(conn, item_id)
        if current is None:
            put_state(conn, item_id, item_type, st)
            added += 1
        elif st.last_ms > current.last_ms:
            put_state(conn, item_id, item_type, st)
            updated += 1
        else:
            kept += 1
    return added, updated, kept


def item_types(conn: sqlite3.Connection) -> dict[str, str]:
    return {row[0]: row[1] for row in conn.execute("SELECT item_id, item_type FROM item_state")}


def cards_first_seen_on(conn: sqlite3.Connection, day: str) -> int:
    """New grammar cards started on `day` (word rounds don't use up the daily new-card allowance)."""
    return conn.execute("SELECT COUNT(*) FROM item_state WHERE first_day = ? AND item_type = 'card'", (day,)).fetchone()[0]


# ---------- daily stats and counters ----------

def day_totals(conn: sqlite3.Connection) -> dict[str, dict[str, int]]:
    """Per local day: answered, correct and seconds, summed over local practice and imported history."""
    rows = conn.execute("SELECT day, SUM(answered), SUM(correct), SUM(seconds) FROM day_stats GROUP BY day")
    return {day: {"answered": a or 0, "correct": c or 0, "seconds": s or 0} for day, a, c, s in rows}


def add_day(conn: sqlite3.Connection, day: str, correct: bool, seconds: float, source: str = "local") -> None:
    conn.execute(
        """INSERT INTO day_stats (day, source, answered, correct, seconds) VALUES (?, ?, 1, ?, ?)
           ON CONFLICT(day, source) DO UPDATE SET answered = answered + 1, correct = correct + excluded.correct,
             seconds = seconds + excluded.seconds""",
        (day, source, 1 if correct else 0, int(round(seconds))),
    )


def merge_day(conn: sqlite3.Connection, day: str, source: str, answered: int, correct: int, seconds: int) -> bool:
    """Imported stats for a day: replaced only by a record with more answers. True if written."""
    row = conn.execute("SELECT answered FROM day_stats WHERE day = ? AND source = ?", (day, source)).fetchone()
    if row is not None and row[0] >= answered:
        return False
    conn.execute(
        """INSERT INTO day_stats (day, source, answered, correct, seconds) VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(day, source) DO UPDATE SET answered = excluded.answered, correct = excluded.correct,
             seconds = excluded.seconds""",
        (day, source, answered, correct, seconds),
    )
    return True


def counter(conn: sqlite3.Connection, key: str) -> int:
    row = conn.execute("SELECT value FROM counters WHERE key = ?", (key,)).fetchone()
    return row[0] if row else 0


def bump_counter(conn: sqlite3.Connection, key: str, by: int = 1) -> None:
    conn.execute("INSERT INTO counters (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = value + ?",
                 (key, by, by))


def max_counter(conn: sqlite3.Connection, key: str, value: int) -> None:
    conn.execute("INSERT INTO counters (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = MAX(value, ?)",
                 (key, value, value))


def rounds(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COALESCE(SUM(value), 0) FROM counters WHERE key LIKE 'rounds.%'").fetchone()[0]


def recent_answer_seconds(conn: sqlite3.Connection, limit: int = 100) -> list[float]:
    return [row[0] for row in conn.execute("SELECT seconds FROM answers ORDER BY answered_ms DESC LIMIT ?", (limit,))]


# ---------- settings ----------

def get_settings(conn: sqlite3.Connection) -> dict:
    settings = dict(DEFAULT_SETTINGS)
    for key, value in conn.execute("SELECT key, value FROM settings"):
        if key in settings:
            try:
                settings[key] = json.loads(value)
            except ValueError:
                pass
    return settings


def put_settings(conn: sqlite3.Connection, values: dict) -> dict:
    for key, value in values.items():
        if key in DEFAULT_SETTINGS:
            conn.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                         (key, json.dumps(value)))
    return get_settings(conn)


# ---------- imports ----------

def import_seen(conn: sqlite3.Connection, fingerprint: str) -> dict | None:
    row = conn.execute("SELECT kind, imported_ms, summary FROM imports WHERE fingerprint = ?", (fingerprint,)).fetchone()
    return {"kind": row[0], "imported_ms": row[1], "summary": json.loads(row[2])} if row else None


def record_import(conn: sqlite3.Connection, fingerprint: str, kind: str, summary: dict) -> None:
    conn.execute("INSERT OR REPLACE INTO imports (fingerprint, kind, imported_ms, summary) VALUES (?, ?, ?, ?)",
                 (fingerprint, kind, int(time.time() * 1000), json.dumps(summary)))


# ---------- export ----------

def export_all(conn: sqlite3.Connection) -> dict:
    """Everything the learner did, as JSON (the progress backup format)."""
    with read_tx(conn):
        items = [
            {"id": r["item_id"], "type": r["item_type"], "box": r["box"], "due_ms": r["due_ms"], "seen": r["n_seen"],
             "right": r["n_right"], "wrong": r["n_wrong"], "lapses": r["n_lapses"], "first_ms": r["first_ms"],
             "last_ms": r["last_ms"]}
            for r in conn.execute("SELECT * FROM item_state ORDER BY item_id")
        ]
        days = [{"day": r[0], "source": r[1], "answered": r[2], "correct": r[3], "seconds": r[4]}
                for r in conn.execute("SELECT day, source, answered, correct, seconds FROM day_stats ORDER BY day, source")]
        counters = {r[0]: r[1] for r in conn.execute("SELECT key, value FROM counters ORDER BY key")}
        answers = [dict(r) for r in conn.execute(
            "SELECT session_id, item_id, ref_type, ref_id, kind, correct, seconds, answered_ms, day, box_after "
            "FROM answers ORDER BY answered_ms")]
        settings = get_settings(conn)
    return {"format": "english-tutor-progress", "version": 1, "exported_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "items": items, "days": days, "counters": counters, "settings": settings, "answers": answers}
