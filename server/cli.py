"""The `tutor` command (uv run tutor ...): start the app, import the old artifact's data, back up progress."""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

from coach import accounts, db, importer, insights
from coach.config import find_claude, load_config
from coach.lessons import LessonStore

from . import __version__
from .context import AppContext, Paths

EDGE = (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe")


def _utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _running(url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{url}/api/health", timeout=0.7) as r:
            return json.loads(r.read()).get("app") == "personal-english-tutor"
    except (OSError, ValueError):
        return False


def _open(url: str, app_window: bool) -> None:
    if app_window:
        edge = next((e for e in EDGE if Path(e).exists()), None) or shutil.which("msedge")
        if edge:
            subprocess.Popen([edge, f"--app={url}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
    webbrowser.open(url)


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from .app import create_app

    config = load_config()
    host = args.host or config.get("server_host") or "127.0.0.1"
    port = int(args.port or config.get("server_port") or 8765)
    url = f"http://{'127.0.0.1' if host in ('0.0.0.0', '::') else host}:{port}"
    page = "http://localhost:5173" if args.dev else url
    if _running(url):
        print(f"Personal English Tutor is already running at {url}")
        if not args.no_browser:
            _open(page, args.app_window)
        return 0
    paths = Paths.default()
    if not args.dev and not (paths.web_dist / "index.html").exists():
        print("The app isn't built yet. Run:  pnpm -C web install  and  pnpm -C web build")
        return 1
    app = create_app(paths, config={**config, "server_port": port}, dev=args.dev)
    if not args.no_browser:
        threading.Timer(1.0, _open, (page, args.app_window)).start()
    print(f"Personal English Tutor {__version__} is running at {url}" + (" (API only; the app is at http://localhost:5173)" if args.dev else ""))
    print("Keep this window open while you practise. Close it (or press Ctrl+C) to stop.")
    uvicorn.run(app, host=host, port=port, log_level="warning")
    return 0


def _db(paths: Paths):
    paths.db.parent.mkdir(parents=True, exist_ok=True)
    conn = db.connect(paths.db)
    db.migrate(conn, paths.backups)
    return conn


def _now_line(paths: Paths) -> str:
    ctx = AppContext(paths)
    with ctx.conn() as conn:
        view = ctx.view(conn)
    c = insights.counts(view)
    return (f"Now       cards due {c['cards_due']} · words due {c['words_due']} · new cards ready {c['new_cards_ready']}"
            f" · streak {insights.streak(view.days, view.now_ms)}")


def cmd_import_artifact(args: argparse.Namespace) -> int:
    paths = Paths.default()
    dump = Path(args.dump)
    if not (dump / "progress").is_dir() and not (dump / "lessons").is_dir():
        print(f"{dump} doesn't look like an artifact export (no lessons/ or progress/ folder).")
        return 2
    conn = _db(paths)
    try:
        if not args.dry_run and db.load_states(conn):
            backup = db.backup_to(conn, paths.backups / f"tutor-before-import-{time.strftime('%Y%m%d-%H%M%S')}.db")
            print(f"Backed up your progress to {backup}")
        summary = importer.import_artifact(dump, batches_dir=paths.batches, conn=conn,
                                           lessons=LessonStore(paths.batches, paths.patterns), dry_run=args.dry_run)
    finally:
        conn.close()
    print(importer.format_summary(summary))
    if not args.dry_run:
        print(_now_line(paths))
    return 0


def cmd_export_progress(args: argparse.Namespace) -> int:
    paths = Paths.default()
    conn = _db(paths)
    try:
        data = db.export_all(conn)
    finally:
        conn.close()
    text = json.dumps(data, ensure_ascii=False, indent=1) + "\n"
    if args.output == "-":
        sys.stdout.write(text)
        return 0
    out = Path(args.output) if args.output else paths.backups / f"progress-{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"Saved {len(data['items'])} card and word states and {len(data['days'])} days of practice to {out}")
    return 0


def cmd_import_progress(args: argparse.Namespace) -> int:
    paths = Paths.default()
    data = json.loads(Path(args.file).read_text(encoding="utf-8"))
    conn = _db(paths)
    try:
        if not args.dry_run:
            backup = db.backup_to(conn, paths.backups / f"tutor-before-restore-{time.strftime('%Y%m%d-%H%M%S')}.db")
            print(f"Backed up your current progress to {backup}")
        summary = importer.import_progress(conn, data, replace=args.replace, with_settings=args.with_settings,
                                           dry_run=args.dry_run)
    except ValueError as e:
        print(f"Can't import {args.file}: {e}")
        return 2
    finally:
        conn.close()
    print(("Dry run: " if args.dry_run else "") + json.dumps(summary))
    return 0


def cmd_openapi(args: argparse.Namespace) -> int:
    from .app import create_app

    schema = create_app(Paths.default()).openapi()
    text = json.dumps(schema, indent=1, ensure_ascii=False) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"Wrote {args.output}")
    else:
        sys.stdout.write(text)
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    from coach.config import app_url

    paths = Paths.default()
    config = load_config()
    ctx = AppContext(paths, config)
    with ctx.conn() as conn:
        view = ctx.view(conn)
    c = insights.counts(view)
    p = insights.pipeline_status(paths.inbox, view.snap)
    url = app_url(config)
    print(f"app        {url} ({'running' if _running(url) else 'not running: uv run tutor'})")
    print(f"lessons    {p['batches']} batches + {p['app_lessons']} from Check writing · {len(view.snap.cards)} cards"
          f" · {len(view.snap.words)} words")
    print(f"pipeline   {p['captured']} messages captured · {p['waiting']} waiting · last analysis {p['last_analysis_at'] or 'never'}")
    print(f"practice   cards due {c['cards_due']} · words due {c['words_due']} · new cards ready {c['new_cards_ready']}"
          f" · streak {insights.streak(view.days, view.now_ms)}")
    items = ctx.accounts()
    if not items:
        print("accounts   none yet: add one in the app (Settings > Accounts)")
    for account in items:
        if account.method == "api-key":
            how = f"API key {accounts.masked_key(account.api_key) or '(missing)'}"
        else:
            how = f"Claude Code sign-in: {accounts.account_email(account) or 'not signed in'}"
        print(f"account    {account.name}: {how}; conversations in {account.projects}"
              f" ({len(accounts.conversation_files(account))} files)")
    print(f"claude.exe {find_claude() or 'not found'}")
    return 0


def cmd_login(args: argparse.Namespace) -> int:
    items = accounts.load_accounts()
    match = [a for a in items if a.name.lower() == args.account.lower()]
    if not match:
        names = ", ".join(a.name for a in items) or "none yet"
        print(f"No account named {args.account!r} (you have: {names}). Add it in the app: Settings > Accounts.")
        return 2
    account = match[0]
    if account.method == "api-key":
        print("That account uses an API key, so there is nothing to sign in.")
        return 0
    if account.uses_default_folder:
        print("That account uses Claude Code's normal folder. Sign in by running `claude` and typing /login.")
        return 0
    claude = find_claude()
    if not claude:
        print("Claude Code isn't installed on this PC.")
        return 1
    home = account.home
    home.mkdir(parents=True, exist_ok=True)
    subprocess.Popen([claude], env=accounts.child_env(account), cwd=str(home),
                     creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
    print(f"A Claude Code window opened for the {account.name!r} account ({home}).")
    print("In it, type /login, sign in with that account, then close the window.")
    return 0


def main(argv: list[str] | None = None) -> int:
    _utf8_console()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(prog="tutor", description="Personal English Tutor: practise English from your own Claude Code messages.")
    sub = parser.add_subparsers(dest="command")

    serve = sub.add_parser("serve", help="start the app (the default)")
    serve.add_argument("--host", help="address to listen on (default 127.0.0.1)")
    serve.add_argument("--port", type=int, help="port (default 8765)")
    serve.add_argument("--no-browser", action="store_true", help="don't open the app")
    serve.add_argument("--app-window", action="store_true", help="open in its own window (Microsoft Edge app mode)")
    serve.add_argument("--dev", action="store_true", help="API only, for the Vite dev server on port 5173")
    serve.set_defaults(func=cmd_serve)

    imp = sub.add_parser("import-artifact", help="import an export of the old claude.ai app's database")
    imp.add_argument("dump", help="folder with lessons/, catalog/ and progress/")
    imp.add_argument("--dry-run", action="store_true", help="show what would change, write nothing")
    imp.set_defaults(func=cmd_import_artifact)

    exp = sub.add_parser("export-progress", help="save your progress as JSON (a backup)")
    exp.add_argument("-o", "--output", help="file to write ('-' for stdout); default data/backups/progress-<time>.json")
    exp.set_defaults(func=cmd_export_progress)

    imq = sub.add_parser("import-progress", help="restore a progress backup")
    imq.add_argument("file")
    imq.add_argument("--replace", action="store_true", help="replace your progress instead of merging")
    imq.add_argument("--with-settings", action="store_true", help="also restore practice settings")
    imq.add_argument("--dry-run", action="store_true")
    imq.set_defaults(func=cmd_import_progress)

    oapi = sub.add_parser("openapi", help="write the API schema (for the web app's types)")
    oapi.add_argument("-o", "--output")
    oapi.set_defaults(func=cmd_openapi)

    st = sub.add_parser("status", help="lessons, practice and accounts at a glance")
    st.set_defaults(func=cmd_status)

    login = sub.add_parser("login", help="sign in Claude Code for an account that uses its own folder")
    login.add_argument("account")
    login.set_defaults(func=cmd_login)

    args = parser.parse_args(argv)
    if not args.command:
        args = parser.parse_args(["serve", *(argv or sys.argv[1:])])
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
