"""Word rounds: which words come in, how each is asked, and how answers are recorded."""

import random
from datetime import datetime

import pytest
from conftest import CATALOG, make_batch

from coach import db, insights, lessons, practice, srs, vocab

NOW = int(datetime(2026, 10, 3, 12, 0).timestamp() * 1000)


def item(kind, word, *, meaning="", pos="noun", example="", rewrite="", wrote="", distractors=None, ts="2026-10-01T03:00:16Z"):
    v = {"id": vocab.vocab_id(kind, word), "kind": kind, "word": word, "pos": pos, "meaning": meaning or f"the {word} idea",
         "meaning_zh": "意思", "example": example or f"We talked about {word} today.", "you_wrote": wrote,
         "message_id": "3e8dm1", "ts": ts, "distractors": [f"{word}x", f"x{word}"] if distractors is None else distractors}
    if kind == "new":
        v.update(level="B2", rewrite=rewrite or f"Please look at the {word} again.")
    return v


def view_of(words, states=None, round_size=8):
    batch = make_batch()
    batch["vocab"] = [w for w in words if w["kind"] != "new"]
    batch["new_words"] = [w for w in words if w["kind"] == "new"]
    snap = lessons.derive([batch], CATALOG)
    return insights.View(snap=snap, states=states or {}, days={}, rounds=0,
                         settings={**db.DEFAULT_SETTINGS, "round_size": round_size}, now_ms=NOW)


def state(box, due_ms=NOW + srs.DAY):
    return srs.State(box=box, due_ms=due_ms, seen=box, right=box, wrong=0, lapses=0, first_ms=NOW - srs.DAY, last_ms=NOW - srs.DAY)


def word(view, kind, text):
    return view.snap.word_by_id[vocab.vocab_id(kind, text)]


# ---------- one word ----------

def test_a_gap_is_cut_only_where_the_word_stands_whole():
    g = practice.gap("Trim the logs, then check the trimmed lines.", "trim", "example")
    assert g == {"before": "", "match": "Trim", "after": " the logs, then check the trimmed lines.", "source": "example"}
    assert practice.gap("We trimmed it.", "trim", "example") is None
    assert practice.gap("Let's narrow  down the cause.", "narrow down", "rewrite")["match"] == "narrow  down"
    assert practice.gap("The end-to-end test", "end", "example") is None
    assert practice.gap("", "trim", "example") is None


def test_choices_for_a_word():
    view = view_of([item("spelling", "satisfied", wrote="statisfied", distractors=["satisfyed", "Statisfied"]),
                    item("new", "intermittent", wrote="sometimes can, sometimes cannot", distractors=["arbitrary", "redundant"]),
                    item("know", "response", wrote="respond", distractors=["responding"])])
    assert practice.word_options(word(view, "spelling", "satisfied")) == ["satisfied", "statisfied", "satisfyed"]
    assert practice.word_options(word(view, "new", "intermittent")) == ["intermittent", "arbitrary", "redundant"]
    assert practice.word_options(word(view, "know", "response")) == ["response", "responding", "respond"]


def test_wrong_meanings_match_the_part_of_speech_and_never_pass_for_the_right_one():
    words = [item("new", "constraint", meaning="a rule or limit that controls what is allowed"),
             item("know", "restriction", meaning="rules or limits that stop you from doing something"),
             item("new", "clarify", pos="verb", meaning="to make something easier to understand"),
             item("new", "deprecate", pos="verb", meaning="to mark a feature as old and not to be used"),
             item("new", "consolidate", pos="verb", meaning="to put several things together into one"),
             item("new", "narrow down", pos="verb", meaning="to find the cause by removing choices"),
             item("new", "rationale", meaning="the reasons behind a decision")]
    view = view_of(words)
    constraint = practice.meaning_options(word(view, "new", "constraint"), view.snap.words, random.Random(1))
    assert constraint[0] == "a rule or limit that controls what is allowed"
    assert "rules or limits that stop you from doing something" not in constraint
    clarify = practice.meaning_options(word(view, "new", "clarify"), view.snap.words, random.Random(1))
    assert len(clarify) == 4 and all(m.startswith("to ") for m in clarify)


def test_a_new_word_gets_harder_as_it_is_learned():
    view = view_of([item("new", "intermittent", example="We see intermittent failures.",
                         rewrite="The login error is intermittent.")])
    w = word(view, "new", "intermittent")
    asked = {box: practice.exercise(w, state(box) if box else None) for box in range(6)}
    assert asked[0] == ("meaning", None)
    assert [(k, g["source"]) for k, g in (asked[1], asked[2], asked[3], asked[4])] == [
        ("choose", "rewrite"), ("choose", "example"), ("type", "rewrite"), ("type", "example")]
    assert practice.exercise(w, state(3), tap_only=True)[0] == "choose"
    no_sentence = view_of([item("new", "rationale", example="No match here.", rewrite="Nor here.")])
    assert practice.exercise(word(no_sentence, "new", "rationale"), state(1)) == ("choose", None)
    assert practice.exercise(word(no_sentence, "new", "rationale"), state(3)) == ("type", None)


def test_typos_and_fixes_are_asked_as_in_the_original_app():
    view = view_of([item("spelling", "satisfied", wrote="statisfied", example="I'm not satisfied yet."),
                    item("know", "response", example="Give me an example response."),
                    item("clearer", "overlap", example="The two bookings overlap.")])
    spelling, know, clearer = word(view, "spelling", "satisfied"), word(view, "know", "response"), word(view, "clearer", "overlap")
    assert [practice.exercise(spelling, state(b) if b else None)[0] for b in (0, 1, 2)] == ["choose", "choose", "type"]
    assert practice.exercise(spelling, state(2), tap_only=True)[0] == "choose"
    assert [practice.exercise(know, state(b) if b else None)[0] for b in (0, 1, 2)] == ["meaning", "meaning", "choose"]
    assert [practice.exercise(clearer, state(b) if b else None)[0] for b in (0, 1, 2, 3)] == ["choose", "choose", "meaning", "choose"]


# ---------- a round ----------

def many(kind, n, **kw):
    return [item(kind, f"{kind}{i:02d}", ts=f"2026-10-01T03:{i:02d}:00Z", **kw) for i in range(n)]


def test_the_plain_round_brings_in_new_words_first_with_a_few_fixes():
    view = view_of(many("new", 10) + many("spelling", 6) + many("know", 6))
    kinds = [w.kind for w in practice.pick_words(view, None, 8)]
    assert kinds.count("new") == 6 and len(kinds) == 8
    assert [w.word for w in practice.pick_words(view, None, 8)][:3] == ["new09", "new08", "new07"]  # latest first
    assert all(w.kind != "new" for w in practice.pick_words(view, "fix", 8))
    assert all(w.kind == "new" for w in practice.pick_words(view, "new", 8))
    out_of_new = view_of(many("new", 2) + many("spelling", 10))
    assert [w.kind for w in practice.pick_words(out_of_new, None, 8)].count("spelling") == 6


def test_due_words_come_first_and_leave_room_for_words_never_practised():
    words = many("new", 10) + many("know", 10)
    ids = [vocab.vocab_id(w["kind"], w["word"]) for w in words]
    states = {i: state(2, due_ms=NOW - 1000 * n) for n, i in enumerate(ids[10:])}  # every know word is due
    picked = practice.pick_words(view_of(words, states), None, 8)
    assert [w.kind for w in picked] == ["know"] * 4 + ["new"] * 4
    assert picked[0].word == "know09"  # the longest overdue first
    learned = {i: state(3) for i in ids}  # nothing due, nothing new: the weakest come back
    learned[ids[5]] = state(1)
    assert practice.pick_words(view_of(words, learned), None, 8)[0].word == "new05"


def test_a_round_has_one_question_per_word_with_the_right_answer_among_the_choices():
    view = view_of(many("new", 3) + many("spelling", 3) + many("clearer", 3), round_size=5)
    items = practice.build_word_round(view, seed="r1")
    assert len(items) == 5 and len({it["item_id"] for it in items}) == 5
    for it in items:
        assert it["answer"] in it["options"] or it["exercise"] == "type"
        assert it["word"]["status"] == "new"
    assert practice.build_word_round(view, seed="r1") == items  # the seed fixes the order and the choices


# ---------- answers ----------

@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "p.db")
    db.migrate(c)
    yield c
    c.close()


def test_answers_are_recorded_once_and_the_round_counted_once(conn):
    view = view_of([item("new", "intermittent"), item("spelling", "satisfied", wrote="statisfied")])
    first = practice.start_word_round(conn, view, client_id="tab-1")
    assert practice.start_word_round(conn, view, client_id="tab-1")["id"] == first["id"]
    new = next(it for it in first["items"] if it["word"]["kind"] == "new")
    out = practice.answer(conn, first["id"], new["item_id"], new["answer"].upper() + " ", 5.2, NOW)
    assert out["correct"] and out["status"] == "learning" and out["answer"] == new["answer"]
    again = practice.answer(conn, first["id"], new["item_id"], "something else", 3, NOW + 1000)
    assert again["correct"]  # the first answer stands
    typo = next(it for it in first["items"] if it["word"]["kind"] == "spelling")
    assert not practice.answer(conn, first["id"], typo["item_id"], "", 900, NOW)["correct"]  # gave up
    st = db.load_state(conn, typo["item_id"])
    assert (st.box, st.due_ms) == (1, NOW + srs.INTERVALS[1])
    assert db.day_totals(conn)[srs.day_key(NOW)] == {"answered": 2, "correct": 1, "seconds": 125}
    with pytest.raises(LookupError):
        practice.answer(conn, first["id"], "nope", "x", 1, NOW)
    assert practice.finish(conn, first["id"], NOW) == {"answered": 2, "correct": 1}
    practice.finish(conn, first["id"], NOW)
    assert db.rounds(conn) == 1
    with pytest.raises(LookupError):
        practice.finish(conn, "missing", NOW)


def test_an_empty_round_is_not_saved(conn):
    out = practice.start_word_round(conn, view_of([]), group="new")
    assert out["items"] == [] and db.get_session(conn, out["id"]) is None
