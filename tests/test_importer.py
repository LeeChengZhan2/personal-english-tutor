"""Importing the old claude.ai artifact's export, and progress backups."""

import json

import pytest
from conftest import CATALOG, DO, make_batch

from coach import db, importer, lessons, store


def write_dump(root, batch):
    """An artifact export like ArtifactData writes it: lessons/, catalog/, progress/ with one file per document."""
    (root / "lessons").mkdir(parents=True)
    (root / "catalog").mkdir()
    (root / "progress").mkdir()
    (root / "lessons" / f"{batch['id']}.json").write_text(json.dumps(batch), encoding="utf-8")
    app_lesson = {
        "id": "app-mv7wls7s", "v": 1, "created": "2026-10-14T09:24:49.816Z", "source": "app", "project": "Blue Pencil",
        "messages": [{"id": "wmv7wls7s", "ts": "2026-10-14T09:24:49.816Z", "project": "Write",
                      "text": "Email me at someone@example.com. The LLM might not remember what the prompt mention.",
                      "fixed": "", "polished": "", "words": 99, "issues": 0}],
        "findings": [{"card": store.card_id("past-tense", "what the prompt mention", "what the prompt mentioned"),
                      "message_id": "wmv7wls7s", "ts": "2026-10-14T09:24:49.816Z", "pattern": "past-tense", "severity": "error",
                      "sentence": "The LLM might not remember what the prompt mentioned.", "wrong": "what the prompt mention",
                      "right": "what the prompt mentioned",
                      "corrected": "The LLM might not remember what the prompt mentioneded.", "explain": "e", "explain_zh": "z",
                      "distractors": []}],
        "patterns": {},
    }
    (root / "lessons" / "app-mv7wls7s.json").write_text(json.dumps(app_lesson), encoding="utf-8")
    (root / "catalog" / "patterns.json").write_text(json.dumps(CATALOG), encoding="utf-8")
    card = store.card_id(*DO)
    word = batch["vocab"][0]["id"]
    srs_doc = {"cards": {card: {"b": 2, "d": 1760000000000, "f": 1759990000000, "n": 2, "r": 2, "w": 0, "t": 1759999000000},
                         word: {"b": 1, "d": 1760000000000, "f": 1759990000000, "n": 1, "r": 1, "w": 0, "t": 1759999000000},
                         "ffffffffff": {"b": 9, "d": 1, "f": 1, "n": 1, "r": 0, "w": 1, "t": 1, "l": 1}}}
    (root / "progress" / "srs-0.json").write_text(json.dumps(srs_doc), encoding="utf-8")
    (root / "progress" / "stats.json").write_text(json.dumps({"days": {"2026-10-15": {"a": 8, "c": 7, "s": 2208}}, "rounds": 1}),
                                                  encoding="utf-8")
    return card, word


@pytest.fixture
def setup(data_root, tmp_path_factory):
    dump = tmp_path_factory.mktemp("dump")
    batch = json.loads(next((data_root / "data" / "batches").glob("*.json")).read_text(encoding="utf-8"))
    card, word = write_dump(dump, batch)
    conn = db.connect(data_root / "data" / "tutor.db")
    db.migrate(conn)
    store_ = lessons.LessonStore(data_root / "data" / "batches", data_root / "data" / "patterns.json")
    return dump, data_root / "data" / "batches", conn, store_, card, word


def test_import_brings_in_progress_stats_and_the_app_lesson(setup):
    dump, batches, conn, store_, card, word = setup
    s = importer.import_artifact(dump, batches_dir=batches, conn=conn, lessons=store_)
    assert s["lessons"]["same"] == 1 and s["lessons"]["added"] == ["app-mv7wls7s"]
    assert s["progress"] == {"states": 3, "card": 1, "word": 1, "unknown": 1, "invalid": 0, "added": 3, "updated": 0, "kept": 0}
    states = db.load_states(conn)
    assert states[card].box == 2 and states[word].box == 1 and states["ffffffffff"].box == 7  # clamped
    assert db.day_totals(conn)["2026-10-15"]["answered"] == 8 and db.rounds(conn) == 1

    app = json.loads((batches / "app-mv7wls7s.json").read_text(encoding="utf-8"))
    f = app["findings"][0]
    assert f["corrected"] == "The LLM might not remember what the prompt mentioned."
    assert f["sentence"] == "The LLM might not remember what the prompt mention."
    assert "someone@example.com" not in app["messages"][0]["text"] and app["vocab"] == []
    assert app["messages"][0]["words"] == len(app["messages"][0]["text"].split()) and app["messages"][0]["issues"] == 1
    assert "repaired correction" in " ".join(s["lessons"]["notes"])


def test_importing_twice_changes_nothing(setup):
    dump, batches, conn, store_, *_ = setup
    importer.import_artifact(dump, batches_dir=batches, conn=conn, lessons=store_)
    before = db.export_all(conn)
    again = importer.import_artifact(dump, batches_dir=batches, conn=conn, lessons=store_)
    assert again["already_imported"] and again["progress"]["added"] == 0 and again["lessons"]["added"] == []
    after = db.export_all(conn)
    assert before["items"] == after["items"] and before["days"] == after["days"]


def test_dry_run_writes_nothing(setup):
    dump, batches, conn, store_, *_ = setup
    s = importer.import_artifact(dump, batches_dir=batches, conn=conn, lessons=store_, dry_run=True)
    assert s["progress"]["added"] == 3 and not (batches / "app-mv7wls7s.json").exists()
    assert db.load_states(conn) == {} and db.day_totals(conn) == {}


def test_progress_backup_round_trip(setup, tmp_path):
    dump, batches, conn, store_, *_ = setup
    importer.import_artifact(dump, batches_dir=batches, conn=conn, lessons=store_)
    exported = db.export_all(conn)
    fresh = db.connect(tmp_path / "fresh.db")
    db.migrate(fresh)
    summary = importer.import_progress(fresh, json.loads(json.dumps(exported)))
    assert summary["added"] == len(exported["items"])
    again = db.export_all(fresh)
    assert again["items"] == exported["items"] and again["days"] == exported["days"] and again["counters"] == exported["counters"]
    with pytest.raises(ValueError):
        importer.import_progress(fresh, {"format": "something else"})
