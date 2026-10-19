"""Command line: python -m coach <command>

  status            what is captured and analyzed
  backfill          read every Claude Code conversation still on this PC (no analysis)
  analyze [-n N] [-j J]   analyze waiting messages (N batches at most, J at a time)
  vocab [-j J]      add vocabulary to batches that have none
  new-words [-j J]  add new words (vocabulary you haven't used yet) to batches that have none
  run               a full update: read new conversations, analyze them, add vocabulary and new words
                    (what the app's "Update my lessons" button does)
"""

from __future__ import annotations

import argparse
import logging
import sys

from . import analyze, capture, new_words, run, store, vocab
from .accounts import load_accounts
from .config import LOGS, TRANSCRIPTS
from .llm import LLMError


def setup_logging(verbose: bool) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [logging.FileHandler(LOGS / "coach.log", encoding="utf-8")]
    if verbose:
        handlers.append(logging.StreamHandler(sys.stdout))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=handlers)


def cmd_status() -> None:
    messages = store.read_messages()
    pending = store.pending_messages()
    batches = store.batch_paths()
    no_vocab = [p.stem for p in batches if '"vocab"' not in p.read_text(encoding="utf-8")]
    no_new_words = new_words.missing()
    print(f"captured messages : {len(messages)}")
    print(f"waiting analysis  : {len(pending)}")
    print(f"lesson batches    : {len(batches)} ({len(no_vocab)} without vocabulary, {len(no_new_words)} without new words)")


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(prog="coach", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["status", "backfill", "analyze", "vocab", "new-words", "run"])
    parser.add_argument("-n", type=int, default=None, help="analyze: at most N batches")
    parser.add_argument("-j", type=int, default=2, help="analyze: batches at a time")
    parser.add_argument("-q", action="store_true", help="log to the file only")
    args = parser.parse_args(argv)
    setup_logging(verbose=not args.q)

    if args.command == "status":
        cmd_status()
    elif args.command == "backfill":
        print(f"captured {capture.backfill(TRANSCRIPTS)} new messages")
    elif args.command == "analyze":
        ids = analyze.analyze_pending(limit=args.n, parallel=args.j, accounts=load_accounts())
        print(f"{len(ids)} new batches")
    elif args.command == "vocab":
        print(f"vocabulary added to {vocab.fill_missing(parallel=args.j, accounts=load_accounts())} batches")
    elif args.command == "new-words":
        print(f"new words added to {new_words.fill_missing(parallel=args.j, accounts=load_accounts())} batches")
    elif args.command == "run":
        accounts = load_accounts()
        if not accounts:
            print("No Claude account is set up yet. Add one in the app: Settings > Accounts.")
            return 1
        try:
            result = run.run(accounts, parallel=args.j,
                             on_progress=lambda stage, done, total: print(f"  {stage} {done}/{total}"))
        except TimeoutError:
            print("Another update is already running.")
            return 1
        except LLMError as e:
            print(f"Stopped: {e}")
            return 1
        print(f"{result['captured']} new messages read, {result['analyzed']} analyzed into "
              f"{len(result['batches'])} lesson batches; {result['waiting']} still waiting")
    return 0


if __name__ == "__main__":
    sys.exit(main())
