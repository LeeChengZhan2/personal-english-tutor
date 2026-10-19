"""Lessons -> cards/words/messages, spaced repetition, the progress database and the page data."""

import json
from datetime import datetime
from pathlib import Path

import pytest
from conftest import CATALOG, DO, PLEAS, make_batch

from coach import db, insights, lessons, srs, store, vocab

ROOT = Path(__file__).resolve().parent.parent
NOW = int(datetime(2026, 10, 3, 12, 0).timestamp() * 1000)


def snap_of(*batches):
    return lessons.derive(list(batches), CATALOG)


def view_of(snap, states=None, days=None, settings=None, new_today=0):
    return insights.View(snap=snap, states=states or {}, days=days or {}, rounds=0,
                         settings=settings or dict(db.DEFAULT_SETTINGS), now_ms=NOW, cards_new_today=new_today)


# ---------- lessons ----------

def test_same_mistake_in_two_batches_is_one_card_with_two_examples():
    snap = snap_of(make_batch(), make_batch("b20261002-030016-3e1b0ad1-9999", day="2026-10-02"))
    do = snap.card_by_id[store.card_id(*DO)]
    assert len(do.examples) == 2 and do.times == 2
    assert do.last.startswith("2026-10-02") and do.first.startswith("2026-10-01")
    assert len(snap.messages) == 4 and snap.messages[0].ts > snap.messages[-1].ts  # newest first


def test_broken_corrections_are_repaired_when_loading():
    snap = snap_of(make_batch())
    ex = snap.card_by_id[store.card_id(*PLEAS)].examples[0]
    assert ex.sentence == "Pleas check it" and ex.corrected == "Please check it"
    assert ex.before + ex.wrong + ex.after == ex.sentence and ex.located


def test_words_and_spelling_counts():
    snap = snap_of(make_batch(), make_batch("b20261002-030016-3e1b0ad1-9999", day="2026-10-02"))
    w = snap.word_by_id[vocab.vocab_id("spelling", "please")]
    assert w.wrote == ["Pleas"] and w.times == 2


def test_new_words_are_their_own_list():
    snap = snap_of(make_batch(), make_batch("b20261002-030016-3e1b0ad1-9999", day="2026-10-02"))
    w = snap.word_by_id[vocab.vocab_id("new", "investigate")]
    assert w.kind == "new" and w.level == "B2" and w.wrote == ["check it"] and w.times == 2
    view = view_of(snap)
    new, fix = insights.word_list(view, "new"), insights.word_list(view, "fix")
    assert [x["word"] for x in new["words"]] == ["investigate"] and [x["word"] for x in fix["words"]] == ["please"]
    assert new["groups"] == [{"group": "new", "count": 1}, {"group": "fix", "count": 1}]
    assert insights.word_of_the_day(view)["word"] == "investigate"  # a new word before the others


def test_unknown_pattern_gets_a_fallback_title():
    b = make_batch()
    b["findings"][0]["pattern"] = "made-up-pattern"
    snap = snap_of(b)
    assert snap.pattern_title("made-up-pattern") == "made up pattern"


def test_lesson_store_reloads_changed_files_and_survives_a_broken_one(data_root):
    store_ = lessons.LessonStore(data_root / "data" / "batches", data_root / "data" / "patterns.json")
    first = store_.snapshot()
    assert store_.snapshot() is first  # cached
    second = make_batch("b20261002-030016-3e1b0ad1-9999", day="2026-10-02")
    (data_root / "data" / "batches" / f"{second['id']}.json").write_text(json.dumps(second), encoding="utf-8")
    (data_root / "data" / "batches" / "half-written.json.tmp").write_text("{", encoding="utf-8")
    assert len(store_.snapshot().messages) == 4
    (data_root / "data" / "batches" / f"{second['id']}.json").write_text("{ broken", encoding="utf-8")
    snap = store_.snapshot()
    assert len(snap.messages) == 4 and snap.errors  # previous parse kept, error reported


@pytest.mark.realdata
def test_real_lessons_load_cleanly():
    """Whoever's lessons are in data/batches: every example locates and every id recomputes."""
    paths = sorted((ROOT / "data" / "batches").glob("*.json"))
    if not paths:
        pytest.skip("no lessons in data/batches yet")
    batches = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
    snap = lessons.derive(batches, store.read_patterns())
    assert all(e.located for c in snap.cards for e in c.examples)
    assert all(f["card"] == store.card_id(f["pattern"], f["wrong"], f["right"]) for b in batches for f in b["findings"])
    assert all(v["id"] == vocab.vocab_id(v["kind"], v["word"])
               for b in batches for v in b.get("vocab", []) + b.get("new_words", []))


# ---------- spaced repetition ----------

def test_grade_follows_the_box_schedule():
    st = srs.grade(None, True, NOW)
    assert (st.box, st.due_ms - NOW, st.seen, st.right) == (1, 10 * srs.MIN, 1, 1)
    st = srs.grade(st, True, NOW + 1)
    assert (st.box, st.due_ms - NOW - 1) == (2, srs.DAY)
    for _ in range(10):
        st = srs.grade(st, True, NOW + 2)
    assert st.box == 7 and srs.status(st) == "mastered"
    st = srs.grade(st, False, NOW + 3)
    assert (st.box, st.wrong, st.lapses, st.first_ms) == (1, 1, 1, NOW)
    assert srs.is_due(st, NOW + 3 + 10 * srs.MIN) and not srs.is_due(None, NOW)


# ---------- database ----------

def test_migrate_creates_the_schema_once_and_refuses_a_newer_one(tmp_path):
    conn = db.connect(tmp_path / "p.db")
    assert db.migrate(conn) == db.SCHEMA_VERSION
    assert db.migrate(conn) == db.SCHEMA_VERSION
    conn.execute(f"PRAGMA user_version = {db.SCHEMA_VERSION + 1}")
    with pytest.raises(RuntimeError):
        db.migrate(conn)


def test_merge_keeps_the_most_recently_answered_state(tmp_path):
    conn = db.connect(tmp_path / "p.db")
    db.migrate(conn)
    old = srs.grade(None, True, NOW)
    new = srs.grade(old, True, NOW + 1000)
    with db.write_tx(conn):
        assert db.merge_states(conn, {"a": ("card", new)}) == (1, 0, 0)
        assert db.merge_states(conn, {"a": ("card", old)}) == (0, 0, 1)
        assert db.merge_day(conn, "2026-10-01", "artifact", 8, 7, 100)
        assert not db.merge_day(conn, "2026-10-01", "artifact", 5, 5, 50)
        db.add_day(conn, "2026-10-01", True, 4.4)
        db.max_counter(conn, "rounds.artifact", 2)
        db.bump_counter(conn, "rounds.local")
    assert db.load_states(conn)["a"].box == 2
    assert db.day_totals(conn)["2026-10-01"] == {"answered": 9, "correct": 8, "seconds": 104}
    assert db.rounds(conn) == 3


def test_settings_defaults_and_updates(tmp_path):
    conn = db.connect(tmp_path / "p.db")
    db.migrate(conn)
    assert db.get_settings(conn) == {"zh": False, "round_size": 8, "new_per_day": 12}
    with db.write_tx(conn):
        assert db.put_settings(conn, {"zh": True, "unknown": 1})["zh"] is True


def test_writes_are_atomic(tmp_path):
    conn = db.connect(tmp_path / "p.db")
    db.migrate(conn)
    with pytest.raises(ZeroDivisionError), db.write_tx(conn):
        db.add_day(conn, "2026-10-01", True, 1)
        1 / 0
    assert db.day_totals(conn) == {}


# ---------- page data ----------

def test_counts_and_the_new_card_allowance_counts_cards_only():
    snap = snap_of(make_batch())
    view = view_of(snap, settings={"zh": False, "round_size": 8, "new_per_day": 1}, new_today=0)
    c = insights.counts(view)
    assert (c["cards_total"], c["cards_due"], c["new_cards_ready"], c["new_left_today"]) == (2, 0, 1, 1)
    due = srs.State(box=1, due_ms=NOW - 1, seen=1, right=1, wrong=0, lapses=0, first_ms=NOW - 5, last_ms=NOW - 5)
    view = view_of(snap, states={store.card_id(*DO): due}, new_today=1,
                   settings={"zh": False, "round_size": 8, "new_per_day": 1})
    c = insights.counts(view)
    assert (c["cards_due"], c["new_cards_ready"]) == (1, 0)
    assert insights.home(view)["practice"]["mode"] == "review"


def test_streak_counts_back_from_today_or_yesterday():
    day = lambda n: srs.day_key(NOW - n * srs.DAY)  # noqa: E731
    days = {day(1): {"answered": 3}, day(2): {"answered": 1}, day(4): {"answered": 9}}
    assert insights.streak(days, NOW) == 2
    days[day(0)] = {"answered": 1}
    assert insights.streak(days, NOW) == 3


def test_message_pages_follow_the_cursor_without_overlap():
    snap = snap_of(*(make_batch(f"b2026100{i}-030016-3e1b0ad1-000{i}", day=f"2026-10-0{i}") for i in range(1, 7)))
    view = view_of(snap)
    first = insights.message_page(view, "all", None, limit=5)
    second = insights.message_page(view, "all", first["next_cursor"], limit=5)
    ids = [m["id"] for m in first["messages"] + second["messages"]]
    assert len(ids) == len(set(ids)) == 10 and first["counts"] == {"mistakes": 6, "all": 12}
    with pytest.raises(ValueError):
        insights.message_page(view, "all", "not-a-cursor!!", limit=5)


def test_pattern_detail_pages_and_unknown_patterns():
    view = view_of(snap_of(make_batch()))
    detail = insights.pattern_detail(view, "do-support", page=1, page_size=5)
    assert detail["total"] == 1 and detail["cards"][0]["status"] == "new" and detail["more_examples"]
    assert insights.pattern_detail(view, "no-such-pattern") is None


def test_pipeline_status_reads_the_inbox(tmp_path):
    (tmp_path / "messages.jsonl").write_text('{"id":"a"}\n{"id":"b"}\n{"id":"b"}\nnot json\n', encoding="utf-8")
    (tmp_path / "analyzed.txt").write_text("a\n", encoding="utf-8")
    s = insights.pipeline_status(tmp_path, snap_of(make_batch()))
    assert (s["captured"], s["waiting"], s["batches"], s["analyzing"]) == (2, 1, 1, False)
