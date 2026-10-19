"""Grammar lessons: which points get one, when it is rewritten, and what Claude's answer must contain."""

import json

from conftest import CATALOG, LESSON, make_batch

from coach import grammar, lessons, srs

NOW = srs.parse_ms("2026-10-10T12:00:00+08:00")


def snap_of(*days):
    batches = [make_batch(f"b202610{d:02d}-030016-3e1b0ad1-{d:04d}", day=f"2026-10-{d:02d}") for d in days]
    return lessons.derive(batches, CATALOG)


def test_points_need_three_mistakes_and_recent_ones_count_more():
    snap = snap_of(1, 2, 3)
    assert [key for key, _ in grammar.ranked(snap, NOW)] == ["do-support"]  # spelling isn't grammar
    assert grammar.ranked(snap_of(1, 2), NOW) == []                          # two mistakes aren't a habit yet
    cards = grammar.by_point(snap)["do-support"]
    assert grammar.mistakes(cards) == 3
    assert grammar.need(cards, srs.parse_ms("2026-10-03T12:00:00+08:00")) > grammar.need(cards, NOW)


def test_a_lesson_is_due_when_missing_or_when_the_mistakes_grew_a_lot(tmp_path):
    def save(based_on):
        doc = {"pattern": "do-support", "based_on": based_on, "lesson": LESSON}
        (tmp_path / "do-support.json").write_text(json.dumps(doc), encoding="utf-8")

    assert grammar.due(snap_of(1, 2, 3), NOW, tmp_path) == ["do-support"]
    save(3)
    assert grammar.due(snap_of(1, 2, 3), NOW, tmp_path) == []
    assert grammar.due(snap_of(*range(1, 9)), NOW, tmp_path) == ["do-support"]  # 8 mistakes: 3 * 1.5 and 3 + 5
    assert grammar.read(tmp_path, "do-support")["lesson"] == LESSON
    assert grammar.read(tmp_path, "../do-support") is None


def test_clean_keeps_a_complete_lesson_and_checks_the_quiz():
    assert grammar.clean(LESSON) == LESSON
    answer = {**LESSON, "quiz": [
        {"sentence": "Why ____ the build fail?", "answer": "does", "options": ["do", "does", "is"], "why": "w"},
        {"sentence": "No gap here.", "answer": "x", "options": ["y"], "why": ""},
        {"sentence": "___ and ___", "answer": "x", "options": ["y"], "why": ""},
        {"sentence": "It ___ fine.", "answer": "works", "options": ["works"], "why": ""},
    ], "watch_out": [{"wrong": "Why it fails?", "right": "Why does it fail?", "why": "w"}, {"wrong": "same", "right": "Same", "why": ""}]}
    lesson = grammar.clean(answer)
    assert lesson["quiz"] == [{"sentence": "Why ___ the build fail?", "answer": "does", "options": ["do", "is"], "why": "w"}]
    assert [w["wrong"] for w in lesson["watch_out"]] == ["Why it fails?"]
    assert grammar.clean({**LESSON, "rules": []}) is None and grammar.clean({**LESSON, "title": " "}) is None
