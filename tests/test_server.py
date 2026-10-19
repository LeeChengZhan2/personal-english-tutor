"""The local app's API: shapes, errors and the localhost-only rules. Skipped without the server's dependencies
(plain `python -m pytest` runs only the pipeline tests; `uv run pytest` runs everything)."""

import json

import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient  # needs fastapi and httpx2 (or httpx)

from conftest import LESSON  # noqa: E402

from coach import srs  # noqa: E402
from server.app import create_app  # noqa: E402
from server.context import Paths  # noqa: E402

BASE = "http://127.0.0.1:8765"
CONFIG = {"server_port": 8765, "claude_accounts": [{"name": "default", "config_dir": ""}]}


@pytest.fixture
def client(data_root):
    dist = data_root / "web" / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><script>var x = 1</script><div id=root></div>", encoding="utf-8")
    (dist / "assets" / "app-123.js").write_text("console.log(1)", encoding="utf-8")
    app = create_app(Paths.under(data_root), config=CONFIG, clock=lambda: srs.parse_ms("2026-10-03T12:00:00+08:00"))
    with TestClient(app, base_url=BASE) as c:
        yield c


def test_bootstrap_and_home(client):
    b = client.get("/api/bootstrap").json()
    assert b["counts"]["cards_total"] == 2 and b["settings"] == {"zh": False, "round_size": 8, "new_per_day": 12}
    assert b["lessons_version"] and b["pipeline"]["batches"] == 1
    assert b["ai"] == {"available": False, "accounts": [],
                       "reason": "Add your Claude account in Settings to make lessons and use the AI checks."}
    h = client.get("/api/home").json()
    assert h["practice"]["mode"] == "new" and h["focus"]["pattern"] == "do-support" and h["latest_chat"]["messages"] == 2
    assert h["word_of_the_day"]["word"] == "investigate"


def test_content_pages(client):
    cats = client.get("/api/patterns").json()["categories"]
    assert [c["key"] for c in cats] == ["verbs", "mechanics"]
    detail = client.get("/api/patterns/spelling").json()
    assert detail["cards"][0]["corrected"] == "Please check it"  # repaired on load
    assert client.get("/api/patterns/nope").json()["code"] == "not_found"
    new = client.get("/api/words").json()  # new words are the first list
    assert new["group"] == "new" and new["groups"] == [{"group": "new", "count": 1}, {"group": "fix", "count": 1}]
    assert new["words"][0]["level"] == "B2" and new["words"][0]["rewrite"].endswith("Please investigate.")
    fixes = client.get("/api/words", params={"group": "fix"}).json()
    assert fixes["total_in_group"] == 1 and fixes["words"][0]["wrote"] == ["Pleas"] and fixes["words"][0]["rewrite"] == ""
    msgs = client.get("/api/messages", params={"filter": "all"}).json()
    assert msgs["counts"] == {"mistakes": 1, "all": 2}
    one = client.get(f"/api/messages/{msgs['messages'][0]['id']}").json()
    assert one["id"] == msgs["messages"][0]["id"]
    assert client.get("/api/messages", params={"cursor": "%%%"}).status_code == 400
    p = client.get("/api/progress").json()
    assert len(p["practice"]) == 28 and p["kpis"]["cards_total"] == 2


def test_grammar_lessons(client, data_root):
    folder = data_root / "data" / "grammar"
    folder.mkdir()
    doc = {"pattern": "do-support", "written_at": "2026-10-02T10:00:00+08:00", "based_on": 1, "lesson": LESSON}
    (folder / "do-support.json").write_text(json.dumps(doc), encoding="utf-8")
    listing = client.get("/api/grammar").json()
    assert listing["coming"] == 0 and [r["pattern"] for r in listing["lessons"]] == ["do-support"]
    assert listing["lessons"][0]["title"] == LESSON["title"] and listing["lessons"][0]["mistakes"] == 1
    lesson = client.get("/api/grammar/do-support").json()
    assert lesson["quiz"] == LESSON["quiz"] and lesson["category_title"] == "Verbs"
    assert lesson["from_you"][0]["wrong"] == "Why my table has"
    assert client.get("/api/grammar/spelling").json()["code"] == "not_found"
    assert client.get("/api/grammar/..%5Cpatterns").status_code == 404  # never a file outside data/grammar
    assert client.get("/api/patterns/do-support").json()["lesson"] is True
    assert client.get("/api/patterns/spelling").json()["lesson"] is False


def test_settings_validate_and_save(client):
    assert client.put("/api/settings", json={"round_size": 12}).json()["round_size"] == 12
    bad = client.put("/api/settings", json={"round_size": 7})
    assert bad.status_code == 422 and bad.json()["code"] == "invalid_request"
    assert client.put("/api/settings", json={"surprise": 1}).status_code == 422
    assert client.get("/api/settings").json()["round_size"] == 12


def test_only_localhost_and_the_apps_own_pages(client):
    assert client.get("/api/health", headers={"Host": "evil.example"}).status_code == 400
    assert client.put("/api/settings", json={"zh": True}, headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.put("/api/settings", json={"zh": True}, headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert client.put("/api/settings", json={"zh": True}, headers={"Origin": BASE}).status_code == 200
    r = client.put("/api/settings", content="zh=true", headers={"Content-Type": "text/plain"})
    assert r.status_code == 415
    r = client.put("/api/settings", content=json.dumps({"x": "a" * 300_000}), headers={"Content-Type": "application/json"})
    assert r.status_code == 413
    assert client.get("/api/health").headers["x-content-type-options"] == "nosniff"


def test_serves_the_web_app_with_a_fallback(client):
    page = client.get("/mistakes/do-support")
    assert page.status_code == 200 and "id=root" in page.text
    assert "sha256-" in page.headers["content-security-policy"]
    asset = client.get("/assets/app-123.js")
    assert asset.headers["content-type"].startswith("text/javascript") and "immutable" in asset.headers["cache-control"]
    missing = client.get("/api/nothing-here")
    assert missing.status_code == 404 and missing.json()["code"] == "not_found"
    assert client.get("/../../etc/passwd").status_code in (200, 404)  # never a file outside dist


def test_openapi_has_readable_operation_ids(client):
    schema = client.get("/api/openapi.json").json()
    ids = {op["operationId"] for path in schema["paths"].values() for op in path.values()}
    assert {"bootstrap", "home", "patterns", "pattern", "grammar_list", "grammar_lesson", "words", "messages", "progress"} <= ids
