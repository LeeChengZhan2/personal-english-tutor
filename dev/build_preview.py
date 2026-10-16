"""Build dev/preview.html: the app in the claude.ai page skeleton, with a stand-in `window.claude`.

The stand-in serves the local lessons (data/batches, data/patterns.json) through the same db API the
real viewer has, keeps progress in localStorage, and answers `sample` calls with canned replies.

  python dev/build_preview.py            # with the stand-in database and Claude
  python dev/build_preview.py --no-claude  # no window.claude: the app's example mode
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKELETON = (
    '<!doctype html><html><head><meta charset=utf8><meta name=viewport content="width=device-width,'
    'initial-scale=1,viewport-fit=cover"><style>:root{color-scheme:light;box-sizing:border-box;'
    "padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}"
    "body{margin:0;padding:0;font:14px system-ui,sans-serif}img{max-width:100%}"
    "[hidden]{display:none!important}</style></head><body>"
)

FAKE = r"""
<script>
(() => {
  const SEED = __SEED__;
  const docs = new Map();
  for (const b of SEED.batches) docs.set("lessons/" + b.id, b);
  docs.set("catalog/patterns", SEED.catalog);
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem("bp-dev-db") || "{}"); } catch (e) {}
  for (const [p, d] of Object.entries(saved)) docs.set(p, d);
  const persist = () => { const out = {}; for (const [p, d] of docs) if (!p.startsWith("catalog/") && !(p.startsWith("lessons/") && SEED.batches.some((b) => "lessons/" + b.id === p))) out[p] = d; try { localStorage.setItem("bp-dev-db", JSON.stringify(out)); } catch (e) {} };
  const listeners = new Set();
  const meta = { fromCache: false, hasPendingWrites: false };
  const snapDoc = (path) => ({ id: path.split("/").pop(), exists: docs.has(path), data: () => docs.has(path) ? JSON.parse(JSON.stringify(docs.get(path))) : undefined, metadata: meta });
  const snapColl = (coll) => { const items = [...docs.keys()].filter((p) => p.startsWith(coll + "/") && p.split("/").length === coll.split("/").length + 1).sort().map(snapDoc); return { docs: items, size: items.length, empty: !items.length, docChanges: () => [], metadata: meta }; };
  const notify = (path) => { const coll = path.split("/").slice(0, -1).join("/"); for (const l of listeners) if (l.coll === coll) setTimeout(() => l.cb(snapColl(coll)), 30); };
  const merge = (a, b) => { const out = Object.assign({}, a); for (const [k, v] of Object.entries(b)) out[k] = v && typeof v === "object" && !Array.isArray(v) && a && a[k] && typeof a[k] === "object" ? merge(a[k], v) : v; return out; };
  const docRef = (path) => ({
    id: path.split("/").pop(), path,
    get: async () => snapDoc(path),
    set: async (d) => { docs.set(path, JSON.parse(JSON.stringify(d))); persist(); notify(path); },
    update: async (d) => { if (!docs.has(path)) throw { code: "invalid_argument", message: "missing" }; docs.set(path, merge(docs.get(path), d)); persist(); notify(path); },
    delete: async () => { docs.delete(path); persist(); notify(path); },
  });
  const db = {
    doc: docRef,
    collection: (coll) => ({ path: coll, doc: (id) => docRef(coll + "/" + id), get: async () => snapColl(coll), onSnapshot: (cb) => { const l = { coll, cb }; listeners.add(l); setTimeout(() => cb(snapColl(coll)), 120); return () => listeners.delete(l); } }),
  };
  const user = { isOwner: async () => true, canEdit: async () => true, can: async () => true, id: async () => "u_dev", me: async () => ({ id: "u_dev", name: "", isOwner: true, canEdit: true }) };
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  async function sampleJson(input) {
    const text = typeof input === "string" ? input : input.map((m) => m.content).join("\n");
    await wait(500);
    if (text.includes("Learner's answer")) return { ok: true, note: "Good fix: that is exactly the change it needed." };
    if (text.includes("Judge the rewrite")) return { score: 4, good: "Clear and polite, and the request is easy to follow.", fixes: [{ wrong: "check why blocked", right: "check why it was blocked", why: "The sentence needs a subject and a passive verb." }], better: "The 11:00-12:00 booking should be allowed. Could you check why it was blocked?" };
    if (text.includes("Write 6 new practice sentences")) return [
      { sentence: "The report should send to the client by Friday.", wrong: "should send", right: "should be sent", explain: "The report doesn't send; it is sent.", explain_zh: "报告是被发送。", distractors: ["should been sent", "should sending"] },
      { sentence: "All the old logs has been delete last night.", wrong: "has been delete", right: "were deleted", explain: "Past event, plural logs: were deleted.", explain_zh: "过去发生，复数：were deleted。", distractors: ["was delete", "has deleted"] },
    ];
    if (text.includes("Check the text below")) return {
      fixed: "Hi team, the deployment is done. Please check whether the dashboard is working.",
      polished: "Hi team, the deployment is done. Could you check that the dashboard is working?",
      findings: [
        { sentence: "Hi team, the deployment done.", wrong: "deployment done", right: "deployment is done", pattern: "missing-be", severity: "error", explain: "Done is an adjective here, so it needs is.", explain_zh: "形容词前要加 is。", distractors: ["deployment was do", "deployment doing"] },
        { sentence: "Please check is the dashboard working.", wrong: "check is the dashboard working", right: "check whether the dashboard is working", pattern: "question-order", severity: "error", explain: "Inside a sentence, use whether and normal word order.", explain_zh: "句中问题用 whether + 陈述语序。", distractors: ["check the dashboard is it working", "check if is the dashboard working"] },
      ],
    };
    return {};
  }
  async function sample(input) { await wait(300); return { text: "ok", truncated: false, modelTierApplied: "quick" }; }
  sample.json = sampleJson;
  sample.limits = async () => ({ maxPromptBytes: 262144 });
  const caps = { db, user, sample };
  window.claude = { use: async (name) => { await wait(60); return caps[name] || null; } };
})();
</script>
"""


def main() -> None:
    no_claude = "--no-claude" in sys.argv
    batches = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "data" / "batches").glob("*.json"))]
    catalog = json.loads((ROOT / "data" / "patterns.json").read_text(encoding="utf-8"))
    app = (ROOT / "app" / "index.html").read_text(encoding="utf-8")
    seed = json.dumps({"batches": batches, "catalog": catalog}, ensure_ascii=False).replace("</", "<\\/")
    fake = "" if no_claude else FAKE.replace("__SEED__", seed)
    out = ROOT / "dev" / ("preview-example.html" if no_claude else "preview.html")
    out.write_text(SKELETON + fake + app + "\n</body></html>", encoding="utf-8")
    print(f"{out} ({len(batches)} batches)")


if __name__ == "__main__":
    main()
