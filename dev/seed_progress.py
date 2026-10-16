"""Print a JS snippet that puts some cards at later boxes in the preview's stand-in database,
so a round shows every card type: python dev/seed_progress.py > dev/seed.js"""

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    findings = []
    for path in sorted((ROOT / "data" / "batches").glob("*.json")):
        findings += json.loads(path.read_text(encoding="utf-8"))["findings"]
    spotable = [f for f in findings if len(f["wrong"].split()) <= 3 and len(f["sentence"].split()) <= 25]
    now = int(time.time() * 1000)
    states = {}
    for i, f in enumerate(spotable[:12]):
        box = 2 if i < 6 else 3  # box 2 -> tap the mistake, box 3 -> fix it (typing)
        states[f["card"]] = {"b": box, "d": now - 60000, "n": box, "r": box, "w": 0, "f": now - 5 * 86400000, "t": now - 86400000}
    docs = {}
    for card, st in states.items():
        docs.setdefault(f"progress/srs-{card[0]}", {"cards": {}})["cards"][card] = st
    day = time.strftime("%Y-%m-%d", time.localtime(time.time() - 86400))
    docs["progress/stats"] = {"days": {day: {"a": 16, "c": 12, "s": 300}}, "rounds": 2}
    print("localStorage.setItem('bp-dev-db', " + json.dumps(json.dumps(docs)) + "); 1")


if __name__ == "__main__":
    main()
