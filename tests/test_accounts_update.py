"""Accounts (data/accounts.json), the Claude-calling layer, and the "Update my lessons" job."""

import json
import time

import pytest

from coach import accounts, claude_cli, llm, store

TestClient = pytest.importorskip("fastapi.testclient").TestClient  # the API tests need the server's packages

BASE = "http://127.0.0.1:8765"


# ---------- coach side ----------

def test_accounts_round_trip_and_masking(tmp_path):
    path = tmp_path / "accounts.json"
    assert accounts.load_accounts(path) == []
    a = accounts.Account(id="a1", name="Work", method="api-key", api_key="sk-ant-api03-abcdefghijklmnop1234")
    accounts.save_accounts([a], path)
    assert accounts.load_accounts(path) == [a]
    assert accounts.masked_key(a.api_key) == "sk-ant-…1234"
    assert accounts.masked_key("") is None


def test_limited_accounts_are_tried_last():
    a, b = accounts.Account(id="x1", name="A"), accounts.Account(id="x2", name="B")
    accounts.mark_limited(a, "5pm")
    try:
        assert accounts.ordered([a, b]) == [b, a]
        assert accounts.limited_info(a)[1] == "5pm"
    finally:
        accounts.clear_limited(a)


def test_classify_claude_errors():
    assert claude_cli.classify({"api_error": "usage_limit_reached"}, "") == ("usage_limit", None)
    assert claude_cli.classify({}, "You've hit your limit · resets 5pm (Asia/Singapore)") == ("usage_limit", "5pm (Asia/Singapore)")
    assert claude_cli.classify({}, "Invalid API key · Please run /login")[0] == "auth"
    assert claude_cli.classify({"api_error_status": 529}, "")[0] == "overloaded"
    assert claude_cli.classify({}, "something else")[0] == "failed"


def test_strict_schema_closes_every_object():
    schema = {"type": "object", "properties": {"items": {"type": "array", "items": {"type": "object", "properties": {}}}}}
    out = llm.strict_schema(schema)
    assert out["additionalProperties"] is False
    assert out["properties"]["items"]["items"]["additionalProperties"] is False
    assert "additionalProperties" not in schema  # the original is untouched


def test_ask_json_moves_to_the_next_account_on_a_usage_limit(monkeypatch):
    a, b = accounts.Account(id="y1", name="First"), accounts.Account(id="y2", name="Second")
    calls = []

    def fake_cli(account, prompt, schema, alias, cancel, timeout):
        calls.append(account.name)
        if account.name == "First":
            raise llm.LLMError("limit", kind="usage_limit", resets="5pm")
        return {"ok": True}

    monkeypatch.setattr(llm, "_ask_cli", fake_cli)
    try:
        answer, used = llm.ask_json("p", {"type": "object"}, accounts=[a, b])
        assert answer == {"ok": True} and used.name == "Second" and calls == ["First", "Second"]
        with pytest.raises(llm.LLMError) as e:
            llm.ask_json("p", {"type": "object"}, accounts=[a])
        assert e.value.kind == "usage_limit"
        with pytest.raises(llm.LLMError) as e:
            llm.ask_json("p", {"type": "object"}, accounts=[])
        assert e.value.kind == "not_configured"
    finally:
        accounts.clear_limited(a)


# ---------- the API ----------

@pytest.fixture
def client(data_root, monkeypatch):
    from server.app import create_app
    from server.context import Paths

    inbox = data_root / "data" / "inbox"
    monkeypatch.setattr(store, "STATE_FILE", inbox / "state.json")
    monkeypatch.setattr(store, "MESSAGES", inbox / "messages.jsonl")
    monkeypatch.setattr(store, "ANALYZED", inbox / "analyzed.txt")
    app = create_app(Paths.under(data_root), config={"server_port": 8765})
    with TestClient(app, base_url=BASE) as c:
        yield c


def test_add_edit_and_remove_accounts(client, data_root):
    folder = data_root / "claude-work"
    (folder / "projects" / "p").mkdir(parents=True)
    (folder / "projects" / "p" / "s1.jsonl").write_text("", encoding="utf-8")
    r = client.post("/api/accounts", json={"name": "Work", "method": "api-key", "api_key": "sk-ant-api03-secretsecret9876",
                                           "folder": str(folder)})
    assert r.status_code == 201, r.text
    work = r.json()
    assert work["api_key_hint"] == "sk-ant-…9876" and "secret" not in r.text and work["conversation_files"] == 1
    assert client.post("/api/accounts", json={"name": "work", "method": "claude-code"}).json()["code"] == "duplicate_name"
    assert client.post("/api/accounts", json={"name": "X", "method": "api-key"}).json()["code"] == "api_key_required"
    assert client.post("/api/accounts", json={"name": "Y", "folder": str(data_root / "nope")}).json()["code"] == "folder_missing"
    # editing without a key keeps the saved one; the file has it, the API never shows it
    r = client.put(f"/api/accounts/{work['id']}", json={"name": "Work laptop"})
    assert r.json()["name"] == "Work laptop" and r.json()["api_key_hint"] == "sk-ant-…9876"
    saved = json.loads((data_root / "data" / "accounts.json").read_text(encoding="utf-8"))
    assert saved["accounts"][0]["api_key"] == "sk-ant-api03-secretsecret9876"
    listing = client.get("/api/accounts").json()
    assert [a["name"] for a in listing["accounts"]] == ["Work laptop"] and "secret" not in json.dumps(listing)
    assert client.get("/api/bootstrap").json()["ai"]["available"] is True
    assert client.delete(f"/api/accounts/{work['id']}").status_code == 204
    assert client.get("/api/accounts").json()["accounts"] == []


def test_update_needs_an_account_first(client):
    r = client.post("/api/update", json={})
    assert r.status_code == 400 and r.json()["code"] == "not_configured"
    assert client.get("/api/update").json()["state"] == "idle"


def test_update_runs_in_the_background_and_reports_progress(client, data_root, monkeypatch):
    import server.update as update_module

    folder = data_root / "claude"
    (folder / "projects" / "p").mkdir(parents=True)
    (folder / "projects" / "p" / "s1.jsonl").write_text("{}\n", encoding="utf-8")
    acc = client.post("/api/accounts", json={"name": "Me", "folder": str(folder)}).json()
    preview = client.get("/api/update/preview").json()
    assert preview["accounts"] == [{"id": acc["id"], "name": "Me", "files": 1, "changed": 1}] and preview["waiting"] == 0

    seen = {}

    def fake_run(accts, *, parallel, on_progress, cancel):
        seen["names"] = [a.name for a in accts]
        on_progress("reading", 1, 1)
        on_progress("analyzing", 1, 2)
        time.sleep(0.2)
        on_progress("analyzing", 2, 2)
        return {"captured": 3, "analyzed": 3, "batches": ["b1"], "vocabulary": 1, "waiting": 0, "stopped": False}

    monkeypatch.setattr(update_module.run, "run", fake_run)
    r = client.post("/api/update", json={"account_ids": [acc["id"]]})
    assert r.status_code == 202 and r.json()["state"] == "running" and r.json()["accounts"] == ["Me"]
    assert client.post("/api/update", json={}).status_code == 409  # one at a time
    for _ in range(50):
        status = client.get("/api/update").json()
        if status["state"] != "running":
            break
        time.sleep(0.05)
    assert status["state"] == "done" and status["result"]["captured"] == 3 and status["last_finished_at"]
    assert seen["names"] == ["Me"]


def test_stop_ends_a_running_update(client, data_root, monkeypatch):
    import server.update as update_module

    folder = data_root / "claude"
    (folder / "projects").mkdir(parents=True)
    client.post("/api/accounts", json={"name": "Me", "folder": str(folder)})

    def slow_run(accts, *, parallel, on_progress, cancel):
        for _ in range(100):
            if cancel.is_set():
                raise llm.LLMError("stopped", kind="cancelled")
            time.sleep(0.02)
        return {"captured": 0, "analyzed": 0, "batches": [], "vocabulary": 0, "waiting": 0, "stopped": False}

    monkeypatch.setattr(update_module.run, "run", slow_run)
    client.post("/api/update", json={})
    client.post("/api/update/stop")
    for _ in range(100):
        status = client.get("/api/update").json()
        if status["state"] != "running":
            break
        time.sleep(0.02)
    assert status["state"] == "stopped"
