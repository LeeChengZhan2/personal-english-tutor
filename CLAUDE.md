# CLAUDE.md

Personal English Tutor (formerly Blue Pencil) is a local web app. It turns the English mistakes in a
user's own Claude Code messages into practice cards. Read README.md first: it covers setup, the
read → find mistakes → words pipeline, the accounts and the `data/` layout.

## Who it's for

The default learner is a software engineer in Malaysia or Singapore (Mandarin and Singlish background) improving
workplace English. Explanations stay short and simple, and every rule also has a Simplified Chinese hint.

Their most frequent mistakes:
- spelling slips and plurals
- word form (respond/response, restrict/restriction)
- articles and verb patterns
- passive voice (be + past participle) and missing am/is/are
- do-support in negatives and questions, and question word order
- Singlish particles (eh, ba, lah, meh, ah, gua)

## Layout

- `coach/`: the pipeline (read, analyze, vocab, new_words, grammar) and the practice domain (lessons, srs, insights, db, importer).
  - It must never import `server/` or a web framework. `tests/test_layering.py` checks this.
- `server/`: the FastAPI app and the `tutor` CLI.
  - `server/models.py` (Pydantic) is the API contract.
  - `server/update.py` runs Update my lessons in a background thread.
- `web/`: the React app. It only talks to `/api`, using types generated from the server's OpenAPI schema.
- `prompts/`: the analysis and vocabulary prompts.
- `app/`, `dev/`: the retired claude.ai version.
  - Keep it only as a reference for porting the practice rounds and AI checks.
  - Don't maintain it or publish it.

## Rules

- **Private data:** everything per-user lives in `data/`, which git ignores as a whole.
  - Never put real messages, lessons, emails, keys or artifact links in tracked files.
  - Tests use made-up data (`tests/conftest.py`). Tests that need real data skip when it isn't there.
- **No hooks or background jobs:** lessons are made only when the user presses Update my lessons
  (`POST /api/update`) or runs `uv run python -m coach run`.
  - The job runs `coach/run.py`: read each account's folder, then analyze, then vocab, then new words, then
    the grammar lessons that are due (`data/grammar/<pattern>.json`, for the most frequent grammar mistakes).
  - The Words page has two lists: new words (kind `new`) and typos & fixes (`spelling`, `know`, `clearer`).
    New words never include a word the user has typed in any message.
  - It is incremental: per-file offsets are kept in `data/inbox/state.json`.
- **Accounts** (`coach/accounts.py`, `data/accounts.json`): each account is a conversations folder plus one method.
  - The folder is `~/.claude`, or the account's own `CLAUDE_CONFIG_DIR`.
  - The `claude-code` method runs headless `claude -p` (`coach/claude_cli.py`).
  - The `api-key` method calls the Anthropic SDK with structured output (`coach/llm.py`).
  - `llm.ask_json` tries the accounts in order, and moves on after a usage-limit or auth error.
  - The API never returns a key, only `accounts.masked_key`.
- **Ids:** never change `store.card_id` or `vocab.vocab_id` (normalization, sha1, 10 hex). Progress in
  `data/tutor.db` and imported progress are keyed by them.
- **Catalog:** the base pattern catalog ships in `coach/catalog.json`, with generic examples only.
  - Patterns the model invents go to the user's `data/patterns.json`, merged over the base when loaded.
  - To promote a good one, add it to `coach/catalog.json` with a real rule, a Chinese hint and made-up examples.
  - Merge near-duplicates by adding the old key to `analyze.ALIASES`.
- **Security:** the server binds 127.0.0.1, and `server/security.py` rejects other hosts and cross-site writes.
  Keep it that way unless real authentication is added.
- **Git:** never commit, push or create branches. The user does all git.

## Checks

- **Python** (3.13 via uv): run `uv run pytest` after changing `coach/` or `server/`.
- **Web:** run `pnpm -C web typecheck`, `pnpm -C web lint` (oxlint), `pnpm -C web test:run` and `pnpm -C web build`.
  - shadcn/ui here uses Base UI: use the `render` prop, not `asChild`.
- **API types:** after changing `server/models.py`, run `uv run tutor openapi -o web/openapi.json` and then
  `pnpm -C web api:gen`.
- **Prompt or validation changes:** after changing `prompts/analyze.md`, or the validation in
  `analyze.build_batch` or `repair`, rebuild every batch from the saved raw answers in `data/inbox/raw/`
  (and `raw-vocab/`), with no new model calls:

  ```bash
  uv run python -c "from coach import analyze; print(analyze.rebuild_all())"
  ```

  - For `prompts/new_words.md` or `new_words.clean`, do the same from `raw-new-words/`:
    `uv run python -c "from coach import new_words; print(new_words.rebuild_all())"`.
  - For `grammar.clean`, re-validate the lessons from `raw-grammar/` with `grammar.rebuild_all()`.
    A change to `prompts/grammar.md` only affects lessons written after it.
