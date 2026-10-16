"""Hermetic tests for the pure parts: transcript cleaning, redaction, card ids, batching, finding repair."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from coach import analyze, store, vocab  # noqa: E402
from coach.transcripts import clean_text, message_from, user_text  # noqa: E402


def record(text, **extra):
    base = {"type": "user", "uuid": "u1", "sessionId": "s1", "timestamp": "2026-10-13T06:38:00.000Z", "cwd": "C:/x",
            "origin": {"kind": "human"}, "message": {"role": "user", "content": [{"type": "text", "text": text}]}}
    base.update(extra)
    return base


def test_keeps_typed_text_and_strips_ide_context():
    text = "<ide_opened_file>The user opened a.py</ide_opened_file>Make sure all unused code been remove"
    assert user_text(record(text)) == "Make sure all unused code been remove"


def test_drops_pasted_content_but_keeps_the_users_words():
    text = 'These also no need to show\n<pasted_content id="5394">Only real results are reported</pasted_content id="5394">'
    assert clean_text(text) == "These also no need to show"


def test_skips_records_that_are_not_typed_by_the_user():
    assert user_text(record("<command-name>/compact</command-name>")) == ""
    assert user_text(record("hello", isMeta=True)) == ""
    assert user_text(record("hello", origin={"kind": "task-notification"})) == ""
    tool = record("x")
    tool["message"]["content"] = [{"type": "tool_result", "tool_use_id": "t", "content": "out"}]
    assert user_text(tool) == ""


def test_message_from_names_the_project_folder():
    m = message_from(record("ok give me commit message"), Path("C:/h/.claude/projects/c--Users-Me-Code-aibe-lake/s1.jsonl"))
    assert m["project"] == "c--Users-Me-Code-aibe-lake" and m["text"] == "ok give me commit message"


def test_redact_hides_emails_and_tokens():
    out = store.redact("login buildingmanager@kajima.com.sg password: hunter2 key sk-abcdefghijklmnopqrstuvwx")
    assert "kajima" not in out and "hunter2" not in out and "sk-abc" not in out


def test_card_id_merges_repeats_but_keeps_capital_letter_fixes_apart():
    assert store.card_id("apostrophes", "Dont", "Don't") == store.card_id("apostrophes", "dont", "don't")
    assert store.card_id("capitals", "i", "I") != store.card_id("capitals", "I", "i")


def test_make_batches_keeps_sessions_together_and_in_order():
    msgs = [{"id": str(i), "session": "a" if i < 3 else "b", "ts": f"2026-10-0{i + 1}", "text": "x"} for i in range(5)]
    batches = analyze.make_batches(msgs, size=2)
    assert [[m["id"] for m in b] for b in batches] == [["0", "1"], ["2", "3"], ["4"]]


def test_repair_puts_back_a_mistake_the_model_already_fixed():
    assert analyze.repair("Explain these two things first.", "frist", "first") == ("Explain these two things frist.", "frist", "first")


def test_repair_turns_a_deletion_into_a_replacement():
    assert analyze.repair("I think just do the fix first gua", "gua", "") == ("I think just do the fix first gua", "first gua", "first")


def test_build_batch_validates_findings():
    messages = [{"id": "m1", "ts": "2026-10-13T06:38:00Z", "session": "s1", "project": "c--Users-Me-Code-aibe-operator",
                 "text": "Make sure all unused code been remove"}]
    answer = {
        "messages": [{"id": "m1", "keep": True, "fixed": "Make sure all unused code has been removed",
                      "polished": "Please make sure all unused code has been removed.", "redact": []}],
        "findings": [
            {"message_id": "m1", "pattern": "passive-voice", "severity": "error", "sentence": "Make sure all unused code been remove.",
             "wrong": "been remove", "right": "has been removed", "explain": "e", "explain_zh": "z",
             "distractors": ["been removed", "has been remove", "been remove"]},
            {"message_id": "m1", "pattern": "word-choice", "severity": "error", "sentence": "x", "wrong": "x", "right": "y",
             "explain": "", "explain_zh": "", "distractors": []},
        ],
        "new_patterns": [{"key": "politeness-placeholder", "category": "tone", "title": "Placeholder", "rule": "Placeholder pattern.", "rule_zh": ""}],
    }
    batch = analyze.build_batch(messages, answer, {"patterns": {"passive-voice": {}, "word-choice": {}}})
    assert len(batch["findings"]) == 1
    f = batch["findings"][0]
    assert f["corrected"] == "Make sure all unused code has been removed."
    assert "been remove" not in f["distractors"]
    assert batch["patterns"] == {}
    assert batch["messages"][0]["issues"] == 1 and batch["project"] == "aibe-operator"
    json.dumps(batch)


def test_vocab_clean_keeps_real_items_only():
    batch = {"messages": [{"id": "m1", "ts": "2026-10-13", "text": "Can you explan why the respond is slow"}]}
    answer = {"vocab": [
        {"word": "explain", "kind": "spelling", "pos": "verb", "meaning": "make clear", "meaning_zh": "解释",
         "example": "Can you explain why?", "you_wrote": "explan", "message_id": "m1", "distractors": ["explian", "explan"]},
        {"word": "response", "kind": "know", "pos": "noun", "meaning": "a reply", "meaning_zh": "回复",
         "example": "The response is slow.", "you_wrote": "the reply thing", "message_id": "m1", "distractors": []},
        {"word": "explain", "kind": "spelling", "pos": "verb", "meaning": "dup", "meaning_zh": "", "example": "",
         "you_wrote": "explan", "message_id": "m1", "distractors": []},
        {"word": "fast", "kind": "spelling", "pos": "adjective", "meaning": "quick", "meaning_zh": "", "example": "",
         "you_wrote": "", "message_id": "m1", "distractors": []},
        {"word": "x", "kind": "clearer", "pos": "", "meaning": "", "meaning_zh": "", "example": "", "you_wrote": "",
         "message_id": "nope", "distractors": []},
    ]}
    items = vocab.clean(batch, answer)
    assert [i["word"] for i in items] == ["explain", "response"]
    assert items[0]["distractors"] == ["explian"]
    assert items[1]["you_wrote"] == ""  # not something the user really wrote
    assert items[0]["id"] == vocab.vocab_id("spelling", "Explain")
