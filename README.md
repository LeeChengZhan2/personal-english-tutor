# Personal English Tutor

Practise English with lessons made from your own Claude Code conversations. The tutor reads the
messages you typed to Claude Code, finds your English mistakes, and turns each one into a short
practice card with a simple explanation and a Simplified Chinese hint. It runs on your PC at
http://127.0.0.1:8765.

A fresh clone has no data. Your lessons, progress and keys are made on your PC and stay in the
`data/` folder, which git ignores.

## What you need

- [uv](https://docs.astral.sh/uv/). It installs Python 3.13 for you.
- Node.js with [pnpm](https://pnpm.io/), to build the web app once.
- Claude Code conversations on this PC. The lessons are made from them.
- One way to call Claude for each account:
  - **Claude Code sign-in.** This uses your Claude plan at no extra cost, and needs Claude Code installed.
  - **An API key** from console.anthropic.com. This is paid per use and works without Claude Code.

It is made and tested on Windows.

## Get started

```bash
git clone <this repo> personal-english-tutor
cd personal-english-tutor
uv sync
pnpm -C web install
pnpm -C web build
uv run tutor            # or double-click start.cmd on Windows
```

The app opens in your browser. Then:

1. Go to **Settings > Accounts > Add account**. Give the account a name, then choose two things:
   - **How to call Claude:** a Claude Code sign-in or an API key.
   - **Where its conversations are:** Claude Code's normal folder (`~/.claude`), or another folder
     if this account has its own (`CLAUDE_CONFIG_DIR`).
2. Press **Update my lessons**, in the sidebar or on Home. Choose the accounts to read, then confirm.
   - The first update reads every past conversation, so it can take a while.
   - Later updates read only what's new since the last one.
3. Practise your words with **Word round**, on Home or the Words page. Look through your mistakes and
   messages too. Rounds for your mistakes are coming next (see Status).

If you press **Update my lessons** before you add an account, the app asks you to add one first.

## More than one Claude account

You can add as many accounts as you like. **Update my lessons** reads the conversations of the
accounts you tick. If one account hits its usage limit, the next one is used.

Claude Code keeps one sign-in per folder. To use two subscriptions, give the second account its own
folder (for example `C:\Users\you\.claude-work`) and sign in to it once:

```bash
uv run tutor login Work      # opens Claude Code with that folder; run /login there
```

## Your data stays private

Everything personal is in `data/`, and git ignores the whole folder:

| Path | What |
|---|---|
| `data/accounts.json` | your accounts and API keys (a key is never shown again after you save it) |
| `data/inbox/` | the messages read so far, how far each conversation was read, Claude's raw answers |
| `data/batches/` | your lessons: messages, mistakes and words, with secrets removed |
| `data/grammar/` | grammar lessons for the grammar you get wrong most |
| `data/patterns.json` | new mistake patterns Claude added for you |
| `data/tutor.db` | your practice progress and settings, backed up every day to `data/backups/` |
| `data/config.json` | optional settings (see below) |
| `data/logs/` | the log of updates run from the command line (`python -m coach`) |

- Only the text you typed is read. Code, files, tool output and pasted text are skipped.
- Emails, passwords, tokens and keys are removed before anything is sent to Claude.
- The server only answers requests from this PC.

**Keep more history:** by default, Claude Code deletes conversations older than 30 days. To give
your first update more to learn from, set `"cleanupPeriodDays": 365` in `~/.claude/settings.json`.
Lessons you already made stay in `data/`, even after their conversations are deleted.

## How it works

```
~/.claude/projects/*/*.jsonl ─read──▶ data/inbox/messages.jsonl  only what you typed, new lines only
                             ─check─▶ data/batches/*.json        mistakes → cards, by Claude (Sonnet)
                             ─words─▶ the same batches           typos & fixes, a second pass
                             ─new───▶ the same batches           new words you haven't used, a third pass
your mistakes                ─teach─▶ data/grammar/*.json        a lesson for each frequent grammar mistake
the app (FastAPI + React)    reads data/batches and data/grammar; keeps progress in data/tutor.db
```

1. **Read** (`coach/capture.py`, `coach/transcripts.py`): keeps the messages you typed and records
   how far each conversation file was read, so the next update starts where this one stopped.
2. **Find mistakes** (`coach/analyze.py`, `prompts/analyze.md`): sends waiting messages to Claude,
   30 at a time. Each mistake comes back with the sentence, the wrong words, the fix, a short
   explanation in English and Chinese, wrong options for multiple choice, and a corrected and a
   natural version of every message.
3. **Typos & fixes** (`coach/vocab.py`, `prompts/vocab.md`): adds the words you mistype, use in the
   wrong form, or could say more clearly. These are words you already know.
4. **New words** (`coach/new_words.py`, `prompts/new_words.md`): where you wrote something in a plain or
   long way, Claude suggests the word a fluent professional would use (level B2 and above), with your
   sentence rewritten around it. A word you have typed in any message is never suggested.
5. **Grammar lessons** (`coach/grammar.py`, `prompts/grammar.md`): for the 12 grammar points you get wrong
   most (recent mistakes count more), Claude writes a short lesson: what you usually get wrong, the rules,
   new example sentences and a quick check. A lesson is rewritten when its mistakes grow a lot.
6. **Practise** (`coach/lessons.py`, `coach/srs.py`): the same mistake made twice is one card. Cards come
   back after 10 minutes, then 1, 3, 7, 16, 35 and 90 days.
   - **Word rounds** (`coach/practice.py`): words due come first, then new words, with a few typos & fixes.
     A new word gets harder as you learn it: choose its meaning, then choose it for a gap in your own
     sentence, then type it (not with Tap-only practice). A word you miss is asked once more at the end
     of the round; that extra try isn't scored.

The analysis prompt is written for a software engineer with a Mandarin and Singlish background who
is improving their workplace English. Edit `prompts/analyze.md` to suit another learner.

## Status

- Working:
  - the accounts
  - **Update my lessons**
  - the Home, Mistakes, Words, Messages, Progress, Settings and Help pages
  - word rounds
- Coming next:
  - rounds for your mistakes (cards)
  - Check writing
  - the AI answer checks

This app replaces Blue Pencil, an earlier version that ran as a claude.ai artifact. That version is
kept in `app/` and `dev/` for reference only. Its users can bring their progress over with
`uv run tutor import-artifact <export folder>`.

## Commands

```bash
uv run tutor                         # start the app (same as: uv run tutor serve)
uv run tutor serve --no-browser      # also: --port 8765, --app-window (Edge app window), --dev (API only)
uv run tutor status                  # lessons, practice and accounts at a glance
uv run tutor login <account>         # sign in Claude Code for an account with its own folder
uv run tutor export-progress         # back up your progress to data/backups/
uv run tutor import-progress <file>  # restore it (merges; --replace to overwrite)
uv run python -m coach run           # Update my lessons from the command line, with every account
uv run python -m coach status        # messages read, waiting and lessons made
```

## Settings (`data/config.json`)

The file is optional. Any key in it overrides the default in `coach/config.py`:

| Key | Default | What |
|---|---|---|
| `analyze_model` | `"sonnet"` | the model that finds mistakes (`sonnet`, `opus` or `haiku`) |
| `batch_size` | `30` | messages per call |
| `skip_projects` | `[]` | Claude Code project folders never read (names under `~/.claude/projects`) |
| `server_host`, `server_port` | `"127.0.0.1"`, `8765` | where the app runs |

## Development

- **Python** (`coach/`, `server/`):
  - FastAPI and SQLite, managed by uv.
  - Run `uv run pytest` after changing them.
- **Web app** (`web/`):
  - React 19, TypeScript, Vite, Tailwind CSS v4, shadcn/ui, and TanStack Router and Query.
  - Run `uv run tutor serve --dev` and `pnpm -C web dev`, then open http://localhost:5173.
  - Check it with `pnpm -C web typecheck`, `pnpm -C web lint`, `pnpm -C web test:run` and `pnpm -C web build`.
- **API types:** after changing `server/models.py`, run `uv run tutor openapi -o web/openapi.json` and
  then `pnpm -C web api:gen`.

See `CLAUDE.md` for the conventions.
