"""Small lesson data shared by the tests."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from coach import store, vocab  # noqa: E402

CATALOG = {
    "categories": {"verbs": {"title": "Verbs", "zh": "动词"}, "mechanics": {"title": "Spelling & punctuation", "zh": "拼写与标点"}},
    "patterns": {
        "do-support": {"category": "verbs", "title": "do / does in questions", "rule": "Questions need do or does before the subject.",
                       "rule_zh": "问句要加 do/does。", "examples": [{"wrong": "Why it fails?", "right": "Why does it fail?"}]},
        "spelling": {"category": "mechanics", "title": "Spelling", "rule": "Check the spelling of words you type often.",
                     "rule_zh": "注意拼写。", "examples": []},
    },
}

DO = ("do-support", "Why my table has", "Why does my table have")
PLEAS = ("spelling", "Pleas", "Please")

# A grammar lesson as coach.grammar.clean returns it (and as data/grammar/<pattern>.json keeps it)
LESSON = {
    "title": "Questions with do and does", "summary": "Questions in the present need do or does before the subject.",
    "summary_zh": "一般现在时的问句要在主语前加 do/does。", "your_habit": 'You often leave out does: "Why my table has".',
    "rules": [{"rule": "Put do or does before the subject.", "example": "Why does the job stop?"}],
    "examples": [{"sentence": "Does the build pass on main?", "note": "does + subject + base verb"}],
    "watch_out": [{"wrong": "Why it fails?", "right": "Why does it fail?", "why": "A question needs does."}],
    "quiz": [{"sentence": "Why ___ the test fail?", "answer": "does", "options": ["do", "is"], "why": "The test is one thing."}],
    "tip": "A question? Find the helper verb first.", "tip_zh": "问句先找助动词。",
}


def finding(pattern, wrong, right, sentence, corrected, message_id, ts, severity="error"):
    return {"card": store.card_id(pattern, wrong, right), "message_id": message_id, "ts": ts, "pattern": pattern,
            "severity": severity, "sentence": sentence, "wrong": wrong, "right": right, "corrected": corrected,
            "explain": f"explain {wrong}", "explain_zh": "解释", "distractors": [f"{wrong} x"]}


def make_batch(batch_id="b20261001-030016-3e1b0ad1-3e8d", day="2026-10-01", source="claude-code"):
    ts1, ts2 = f"{day}T03:00:16Z", f"{day}T03:05:00Z"
    return {
        "id": batch_id, "v": 1, "created": f"{day}T11:00:00+08:00", "source": source, "project": "demo",
        "messages": [
            {"id": f"{batch_id[-4:]}m1", "ts": ts1, "project": "demo", "text": "Why my table has one row? Pleas check it",
             "fixed": "Why does my table have one row? Please check it", "polished": "Why does my table have only one row? Please check.",
             "words": 9, "issues": 2},
            {"id": f"{batch_id[-4:]}m2", "ts": ts2, "project": "demo", "text": "ok thanks", "fixed": "ok thanks",
             "polished": "OK, thanks.", "words": 2, "issues": 0},
        ],
        "findings": [
            finding(*DO, "Why my table has one row?", "Why does my table have one row?", f"{batch_id[-4:]}m1", ts1),
            # stored broken, as older batches were: the model already fixed the sentence, and a substring match doubled the "e"
            finding(*PLEAS, "Please check it", "Pleasee check it", f"{batch_id[-4:]}m1", ts1, severity="typo"),
        ],
        "patterns": {},
        "vocab": [{"id": vocab.vocab_id("spelling", "please"), "kind": "spelling", "word": "please", "pos": "adverb",
                   "meaning": "a polite word for asking", "meaning_zh": "请", "example": "Please check it.",
                   "you_wrote": "Pleas", "message_id": f"{batch_id[-4:]}m1", "ts": ts1, "distractors": ["pleese"]}],
        "new_words": [{"id": vocab.vocab_id("new", "investigate"), "kind": "new", "word": "investigate", "pos": "verb",
                       "level": "B2", "meaning": "to look at something carefully to find the cause", "meaning_zh": "调查",
                       "you_wrote": "check it", "rewrite": "Why does my table have only one row? Please investigate.",
                       "example": "Could you investigate the slow login?", "message_id": f"{batch_id[-4:]}m1", "ts": ts1,
                       "distractors": ["integrate", "illustrate"]}],
        "new_words_at": f"{day}T11:05:00+08:00",
    }


@pytest.fixture
def data_root(tmp_path):
    """tmp_path laid out like the project: data/batches/<one batch>.json and data/patterns.json."""
    batches = tmp_path / "data" / "batches"
    batches.mkdir(parents=True)
    batch = make_batch()
    (batches / f"{batch['id']}.json").write_text(json.dumps(batch), encoding="utf-8")
    (tmp_path / "data" / "patterns.json").write_text(json.dumps(CATALOG), encoding="utf-8")
    (tmp_path / "data" / "inbox").mkdir()
    return tmp_path
