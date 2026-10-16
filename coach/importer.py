"""Bring data into the local app: an export of the old claude.ai artifact's database, or a progress backup.

An artifact export is a folder with lessons/, catalog/ and progress/, one <doc id>.json per document (what
Claude Code's ArtifactData tool writes with out_dir). Importing it is idempotent: lesson files already on disk
win, card states merge by "most recently answered wins", and the artifact's daily stats are kept apart from
local practice, so importing twice (or practising in both places) never double-counts.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path

from . import db, store
from .lessons import LessonStore, repair_example
from .srs import MAX_BOX, State

BATCH_ID = re.compile(r"^b\d{8}-\d{6}-[0-9a-f]{8}-[0-9a-f]{4}$")
APP_ID = re.compile(r"^app-[0-9a-z]+$")


def read_dump(dump_dir: Path) -> dict[str, dict[str, dict]]:
    """{collection: {doc_id: document}} for lessons, catalog and progress. A document wrapped as
    {"data": {...}} (a possible future export format) is unwrapped."""
    out: dict[str, dict[str, dict]] = {}
    for collection in ("lessons", "catalog", "progress"):
        docs: dict[str, dict] = {}
        folder = Path(dump_dir) / collection
        for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
            doc = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(doc, dict) and set(doc) <= {"data", "version", "id"} and isinstance(doc.get("data"), dict):
                doc = doc["data"]
            if isinstance(doc, dict):
                docs[path.stem] = doc
        out[collection] = docs
    return out


def fingerprint(dump_dir: Path) -> str:
    h = hashlib.sha1()
    for path in sorted(Path(dump_dir).rglob("*.json")):
        h.update(path.relative_to(dump_dir).as_posix().encode())
        h.update(path.read_bytes())
    return h.hexdigest()[:16]


def fix_app_lesson(doc: dict) -> tuple[dict, dict[str, str], list[str]]:
    """A lesson saved by the old app's Write tab, made like the ones the new app saves: secrets removed,
    corrections rebuilt at word boundaries, card ids from store.card_id, no vocabulary pass.
    Returns (lesson, {old card id: new card id}, notes)."""
    notes: list[str] = []
    remap: dict[str, str] = {}
    messages = []
    for m in doc.get("messages") or []:
        text = store.redact(m.get("text", ""))
        messages.append({**m, "text": text, "fixed": store.redact(m.get("fixed", "")),
                         "polished": store.redact(m.get("polished", "")), "words": len(text.split()), "issues": 0})
    by_id = {m["id"]: m for m in messages}
    findings = []
    for f in doc.get("findings") or []:
        sentence = store.redact(f.get("sentence", ""))
        wrong, right = store.redact(f.get("wrong", "")), store.redact(f.get("right", ""))
        fixed_sentence, corrected, _, _, located = repair_example(sentence, wrong, right, f.get("corrected", ""))
        if not located or store.squash(wrong) == store.squash(right):
            notes.append(f"dropped finding {wrong!r} -> {right!r} (not in its sentence)")
            continue
        if corrected != f.get("corrected"):
            notes.append(f"repaired correction {f.get('corrected', '')!r} -> {corrected!r}")
        card = store.card_id(f.get("pattern", ""), wrong, right)
        if f.get("card") and f["card"] != card:
            remap[f["card"]] = card
        findings.append({**f, "card": card, "sentence": fixed_sentence, "wrong": wrong, "right": right, "corrected": corrected})
        m = by_id.get(f.get("message_id"))
        if m is not None and f.get("severity") != "style":
            m["issues"] += 1
    lesson = {**doc, "messages": messages, "findings": findings, "patterns": doc.get("patterns") or {}, "vocab": []}
    return lesson, remap, notes


def _state(raw: dict) -> State | None:
    try:
        last = int(raw.get("t") or 0)
        first = int(raw.get("f") or last)
        return State(box=min(max(int(raw.get("b") or 0), 0), MAX_BOX), due_ms=int(raw.get("d") or 0),
                     seen=int(raw.get("n") or 0), right=int(raw.get("r") or 0), wrong=int(raw.get("w") or 0),
                     lapses=int(raw.get("l") or raw.get("w") or 0), first_ms=first, last_ms=last)
    except (TypeError, ValueError):
        return None


def import_artifact(dump_dir: Path, *, batches_dir: Path, conn: sqlite3.Connection, lessons: LessonStore,
                    dry_run: bool = False) -> dict:
    """Import an artifact export. Returns a summary (see format_summary)."""
    dump_dir = Path(dump_dir)
    dump = read_dump(dump_dir)
    summary: dict = {"lessons": {"same": 0, "differs": [], "restored": [], "added": [], "skipped": [], "notes": []},
                     "catalog": "missing", "progress": {}, "stats": {}, "dry_run": dry_run,
                     "fingerprint": fingerprint(dump_dir)}
    previous = db.import_seen(conn, summary["fingerprint"])
    summary["already_imported"] = bool(previous)

    # 1. lessons: files on disk always win; missing pipeline batches are restored; app lessons are fixed first
    remap: dict[str, str] = {}
    for doc_id, doc in dump["lessons"].items():
        target = Path(batches_dir) / f"{doc_id}.json"
        if APP_ID.match(doc_id):
            if target.exists():
                summary["lessons"]["same"] += 1
                continue
            lesson, ids, notes = fix_app_lesson(doc)
            remap.update(ids)
            summary["lessons"]["added"].append(doc_id)
            summary["lessons"]["notes"] += [f"{doc_id}: {n}" for n in notes]
            if not dry_run:
                store.write_json(target, lesson)
        elif BATCH_ID.match(doc_id):
            if target.exists():
                local = json.loads(target.read_text(encoding="utf-8"))
                if local == doc:
                    summary["lessons"]["same"] += 1
                else:
                    summary["lessons"]["differs"].append(doc_id)
            else:
                summary["lessons"]["restored"].append(doc_id)
                if not dry_run:
                    store.write_json(target, doc)
        else:
            summary["lessons"]["skipped"].append(doc_id)

    # 2. the catalog is only compared: data/patterns.json is the one the pipeline maintains
    catalog = dump["catalog"].get("patterns")
    if catalog is not None:
        local_catalog = store.merge_catalog(store.read_user_patterns(Path(batches_dir).parent / "patterns.json"))
        summary["catalog"] = "same" if local_catalog == store.merge_catalog(catalog) else "differs (kept yours)"

    # 3. progress: card states (sharded srs-<hex> docs) and daily stats
    lessons.invalidate()
    snap = lessons.snapshot()
    states: dict[str, tuple[str, State]] = {}
    kinds = {"card": 0, "word": 0, "unknown": 0}
    bad = 0
    stats_doc = None
    for doc_id, doc in dump["progress"].items():
        if doc_id == "stats":
            stats_doc = doc
            continue
        if not doc_id.startswith("srs-"):
            continue
        for item_id, raw in (doc.get("cards") or {}).items():
            st = _state(raw) if isinstance(raw, dict) else None
            if st is None:
                bad += 1
                continue
            item_id = remap.get(item_id, item_id)
            if dry_run and item_id not in snap.card_by_id and any(item_id == v for v in remap.values()):
                kind = "card"  # an app lesson not written in a dry run
            else:
                kind = "card" if item_id in snap.card_by_id else "word" if item_id in snap.word_by_id else "unknown"
            kinds[kind] += 1
            states[item_id] = (kind, st)

    days = []
    rounds = 0
    if stats_doc:
        for day, rec in (stats_doc.get("days") or {}).items():
            if re.match(r"^\d{4}-\d{2}-\d{2}$", day) and isinstance(rec, dict):
                days.append((day, int(rec.get("a") or 0), int(rec.get("c") or 0), int(rec.get("s") or 0)))
        rounds = int(stats_doc.get("rounds") or 0)

    if dry_run:
        current = db.load_states(conn)
        added = sum(1 for i in states if i not in current)
        updated = sum(1 for i, (_, st) in states.items() if i in current and st.last_ms > current[i].last_ms)
        summary["progress"] = {"states": len(states), **kinds, "invalid": bad, "added": added, "updated": updated,
                               "kept": len(states) - added - updated}
        summary["stats"] = {"days": [{"day": d, "answered": a, "correct": c} for d, a, c, _ in days], "rounds": rounds}
        return summary

    with db.write_tx(conn):
        added, updated, kept = db.merge_states(conn, states)
        written = sum(1 for d, a, c, s in days if db.merge_day(conn, d, "artifact", a, c, s))
        db.max_counter(conn, "rounds.artifact", rounds)
        summary["progress"] = {"states": len(states), **kinds, "invalid": bad, "added": added, "updated": updated,
                               "kept": kept}
        summary["stats"] = {"days": [{"day": d, "answered": a, "correct": c} for d, a, c, _ in days],
                            "days_written": written, "rounds": rounds}
        db.record_import(conn, summary["fingerprint"], "artifact", {k: summary[k] for k in ("progress", "stats")})
    return summary


def format_summary(s: dict) -> str:
    les = s["lessons"]
    lines = [
        ("Dry run: nothing was written.\n" if s.get("dry_run") else "")
        + ("This export was imported before; nothing new below means nothing changed.\n" if s.get("already_imported") else ""),
        f"Lessons   {les['same']} same · {len(les['differs'])} differ (kept local) · {len(les['restored'])} restored"
        f" · {len(les['added'])} app lesson(s) added" + (f" ({', '.join(les['added'])})" if les["added"] else ""),
    ]
    lines += [f"          {n}" for n in les["notes"]]
    if les["skipped"]:
        lines.append(f"          skipped (unknown id): {', '.join(les['skipped'])}")
    lines.append(f"Catalog   {s['catalog']}")
    p = s["progress"]
    if p:
        lines.append(f"Progress  {p['states']} states: {p['card']} cards · {p['word']} words · {p['unknown']} unknown"
                     f" -> {p['added']} added · {p['updated']} updated · {p['kept']} kept (local newer)"
                     + (f" · {p['invalid']} invalid skipped" if p.get("invalid") else ""))
    st = s["stats"]
    if st:
        days = ", ".join(f"{d['day']}: {d['answered']} answered, {d['correct']} right" for d in st["days"]) or "none"
        lines.append(f"Stats     {len(st['days'])} day(s) ({days}) · rounds {st['rounds']}")
    return "\n".join(line for line in lines if line)


# ---------- progress backups ----------

def import_progress(conn: sqlite3.Connection, data: dict, *, replace: bool = False, with_settings: bool = False,
                    dry_run: bool = False) -> dict:
    """Restore a progress backup (the JSON from db.export_all). Merges unless `replace`."""
    if data.get("format") not in ("english-tutor-progress", "blue-pencil-progress") or data.get("version") != 1:
        raise ValueError("not a Personal English Tutor progress backup")
    states: dict[str, tuple[str, State]] = {}
    for it in data.get("items") or []:
        try:
            states[str(it["id"])] = (it.get("type") if it.get("type") in ("card", "word", "unknown") else "unknown", State(
                box=min(max(int(it["box"]), 0), MAX_BOX), due_ms=int(it["due_ms"]), seen=int(it.get("seen", 0)),
                right=int(it.get("right", 0)), wrong=int(it.get("wrong", 0)), lapses=int(it.get("lapses", 0)),
                first_ms=int(it["first_ms"]), last_ms=int(it["last_ms"])))
        except (KeyError, TypeError, ValueError) as e:
            raise ValueError(f"bad item in backup: {it!r}") from e
    days = [(d["day"], d.get("source", "local"), int(d["answered"]), int(d["correct"]), int(d.get("seconds", 0)))
            for d in data.get("days") or [] if d.get("source", "local") in ("local", "artifact")]
    summary = {"items": len(states), "days": len(days), "answers": len(data.get("answers") or []), "replace": replace,
               "dry_run": dry_run}
    if dry_run:
        current = db.load_states(conn)
        summary["added"] = sum(1 for i in states if i not in current)
        summary["updated"] = sum(1 for i, (_, st) in states.items() if i in current and st.last_ms > current[i].last_ms)
        return summary
    with db.write_tx(conn):
        if replace:
            for table in ("item_state", "day_stats", "counters", "answers"):
                conn.execute(f"DELETE FROM {table}")
        added, updated, kept = db.merge_states(conn, states)
        for day, source, a, c, s in days:
            db.merge_day(conn, day, source, a, c, s)
        for key, value in (data.get("counters") or {}).items():
            if str(key).startswith("rounds."):
                db.max_counter(conn, str(key), int(value))
        for a in data.get("answers") or []:
            conn.execute(
                "INSERT OR IGNORE INTO answers (session_id, item_id, ref_type, ref_id, kind, correct, seconds, answered_ms, day,"
                " box_after) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (a["session_id"], a["item_id"], a["ref_type"], a.get("ref_id"), a["kind"], int(a["correct"]),
                 float(a["seconds"]), int(a["answered_ms"]), a["day"], a.get("box_after")))
        if with_settings and isinstance(data.get("settings"), dict):
            db.put_settings(conn, data["settings"])
    summary.update(added=added, updated=updated, kept=kept)
    return summary
