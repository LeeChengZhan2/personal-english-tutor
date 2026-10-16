"""Text helpers shared by the pipeline and the app: answer comparison, whole-word phrases, redaction."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from coach import analyze, store  # noqa: E402


def test_text_vectors_match_the_app():
    # the same vectors are checked by the web app's tests (web/src/lib/answer.test.ts)
    vectors = json.loads((ROOT / "tests" / "fixtures" / "text_vectors.json").read_text(encoding="utf-8"))
    for v in vectors:
        assert store.squash(v["input"]) == v["squash"], v
        assert store.norm(v["input"]) == v["norm"], v
        assert store.answer_key(v["input"]) == v["answer_key"], v


def test_find_phrase_matches_whole_words_only():
    assert store.find_phrase("Please tell me", "Pleas") == -1
    assert store.find_phrase("It is what the prompt mentioned.", "what the prompt mention") == -1
    assert store.find_phrase("Pleas tell me", "Pleas") == 0
    assert store.find_phrase("using in the in-box", "in") == 6
    assert store.find_phrase("the user_role_control have a row", "control have a") == 14  # "_" is not a word char
    assert store.find_phrase("I dont know", "dont") == 2
    assert store.find_phrase("I don't know", "don") == -1  # the apostrophe belongs to the word
    assert store.find_phrase("end.", ".") == 3  # punctuation needs no boundary
    assert store.find_phrase("anything", "") == -1


def test_replace_phrase_and_put_back():
    assert store.replace_phrase("Pleas tell me", "Pleas", "Please") == "Please tell me"
    assert store.replace_phrase("Please tell me", "Pleas", "Please") is None
    assert store.put_back("Please tell me", "Pleas", "Please") == "Pleas tell me"
    assert store.put_back("Pleas tell me", "Pleas", "Please") is None  # already the learner's words
    assert store.put_back("Something else", "Pleas", "Please") is None


def test_repair_never_doubles_an_ending():
    # real cases: the model returned an already-fixed sentence, and a plain substring match made "Pleasee"
    assert analyze.repair("Please tell me the difference", "Pleas", "Please") == ("Pleas tell me the difference", "Pleas", "Please")
    s, w, r = analyze.repair("Is it hardcoded to get all people count sensors?", "all people count sensor", "all people count sensors")
    assert store.replace_phrase(s, w, r) == "Is it hardcoded to get all people count sensors?"
    s, w, r = analyze.repair("Explain what the prompt mentioned.", "what the prompt mention", "what the prompt mentioned")
    assert store.replace_phrase(s, w, r) == "Explain what the prompt mentioned."


def test_repair_still_finds_words_with_different_case_or_spacing():
    assert analyze.repair("Why  my table has one row?", "why my table has", "Why does my table have")[1] == "Why  my table has"
    assert analyze.repair("Check the user_role_control have a row", "control have a", "control has a")[1] == "control have a"


def test_redact_masks_share_keys_in_links():
    text = "update https://claude.ai/artifact/AbCdEfGhIjKlMnOpQrStUv?sk=T-3abcdefghijklmnopqrs with this"
    out = store.redact(text)
    assert "T-3abc" not in out and "?sk=[secret]" in out and out.endswith(" with this")
    assert store.redact("see https://example.com/?page=2") == "see https://example.com/?page=2"
