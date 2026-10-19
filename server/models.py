"""The API contract: every request and response body. The web app's TypeScript types are generated from the
OpenAPI schema these produce (`uv run tutor openapi -o web/openapi.json`, then `pnpm -C web api:gen`).

Timestamps are ISO-8601 strings with an offset; days are local YYYY-MM-DD strings.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["error", "unnatural", "style", "typo"]
WordKind = Literal["spelling", "know", "clearer", "new"]
WordGroup = Literal["new", "fix"]   # new = words not used yet; fix = spelling, know and clearer
ItemStatus = Literal["new", "learning", "mastered"]
RoundSize = Literal[5, 8, 12, 16]
NewPerDay = Literal[6, 12, 20, 30]


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ApiError(BaseModel):
    code: str
    message: str
    details: list[dict[str, Any]] | None = None


# ---------- settings, bootstrap, status ----------

class PracticeSettings(BaseModel):
    zh: bool = False
    round_size: RoundSize = 8
    new_per_day: NewPerDay = 12


class SettingsUpdate(Request):
    zh: bool | None = None
    round_size: RoundSize | None = None
    new_per_day: NewPerDay | None = None


class Counts(BaseModel):
    cards_due: int
    words_due: int
    new_left_today: int
    new_cards_ready: int
    cards_total: int
    words_total: int
    cards_mastered: int
    words_mastered: int


class DayTotals(BaseModel):
    answered: int
    correct: int
    seconds: int


AccountMethod = Literal["claude-code", "api-key"]


class AccountInfo(BaseModel):
    id: str
    name: str
    method: AccountMethod
    email: str | None
    ready: bool                     # can be used for analysis now (signed in / key saved)
    limited_until: str | None = None


class AiInfo(BaseModel):
    available: bool
    reason: str | None
    accounts: list[AccountInfo]


# ---------- accounts ----------

class AccountOut(BaseModel):
    id: str
    name: str
    method: AccountMethod
    folder: str                     # as typed; "" = Claude Code's normal folder
    folder_path: str                # the folder it resolves to
    default_folder: bool
    api_key_hint: str | None        # e.g. "sk-ant-…a1b2"; the key itself is never sent
    email: str | None
    signed_in: bool
    ready: bool
    conversation_files: int
    limited_until: str | None = None


class AccountsOut(BaseModel):
    accounts: list[AccountOut]
    default_folder: str
    claude_installed: bool


class AccountIn(Request):
    name: str = Field(min_length=1, max_length=40)
    method: AccountMethod = "claude-code"
    folder: str = Field("", max_length=400)
    api_key: str = Field("", max_length=400)


class AccountUpdate(Request):
    name: str | None = Field(None, min_length=1, max_length=40)
    method: AccountMethod | None = None
    folder: str | None = Field(None, max_length=400)
    api_key: str | None = Field(None, max_length=400)   # empty or missing = keep the saved key


class CheckOut(BaseModel):
    ok: bool
    message: str


# ---------- update my lessons ----------

UpdateState = Literal["idle", "running", "done", "failed", "stopped"]
UpdateStage = Literal["reading", "analyzing", "vocabulary", "new_words", "done"]


class UpdateIn(Request):
    account_ids: list[str] | None = None   # missing = every account


class UpdateResult(BaseModel):
    captured: int
    analyzed: int
    waiting: int
    new_cards: int
    new_words: int
    batches: int


class UpdateErrorInfo(BaseModel):
    code: str
    message: str


class UpdateStatus(BaseModel):
    state: UpdateState
    stage: UpdateStage | None
    done: int
    total: int
    accounts: list[str]
    started_at: str | None
    finished_at: str | None
    result: UpdateResult | None
    error: UpdateErrorInfo | None
    last_finished_at: str | None    # the last update that finished (survives restarts)


class PreviewAccount(BaseModel):
    id: str
    name: str
    files: int
    changed: int                    # conversation files with new activity since the last update


class UpdatePreview(BaseModel):
    accounts: list[PreviewAccount]
    waiting: int                    # messages read but not analyzed yet
    last_finished_at: str | None


class PipelineInfo(BaseModel):
    captured: int
    waiting: int
    batches: int
    app_lessons: int
    analyzing: bool
    last_analysis_at: str | None


class Bootstrap(BaseModel):
    version: str
    lessons_version: str
    app_url: str
    settings: PracticeSettings
    counts: Counts
    streak: int
    today: DayTotals
    ai: AiInfo
    pipeline: PipelineInfo


class LessonsInfo(BaseModel):
    batches: int
    app_lessons: int
    messages: int
    cards: int
    words: int
    loaded_at: str
    errors: list[str]


class Status(BaseModel):
    version: str
    root: str
    db_path: str
    db_version: int
    claude_path: str | None
    lessons: LessonsInfo
    ai: AiInfo
    pipeline: PipelineInfo


class Health(BaseModel):
    app: Literal["personal-english-tutor"] = "personal-english-tutor"
    version: str


# ---------- shared pieces ----------

class Mastery(BaseModel):
    total: int
    mastered: int
    learning: int
    new: int


class Example(BaseModel):
    sentence: str
    wrong: str
    right: str
    corrected: str


class ExamplePair(BaseModel):
    wrong: str
    right: str


class WordBrief(BaseModel):
    id: str
    kind: WordKind
    word: str
    pos: str
    meaning: str
    meaning_zh: str
    example: str
    wrote: list[str]
    times: int
    last: str | None
    level: str | None               # new words: CEFR level (B2, C1, C2)
    rewrite: str                    # new words: the learner's sentence rewritten with the word; "" otherwise
    status: ItemStatus
    strength: int
    due_at: str | None


# ---------- home ----------

class PracticeSummary(BaseModel):
    mode: Literal["review", "new", "extra"]
    cards_due: int
    new_cards: int
    words_due: int
    round_size: int
    est_minutes: int


class Focus(BaseModel):
    pattern: str
    title: str
    rule: str
    rule_zh: str
    window: Literal["week", "all"]
    count: int
    example: Example | None


class PatternCount(BaseModel):
    pattern: str
    title: str
    count: int


class MarkedMessage(BaseModel):
    id: str
    text: str
    fixed: str


class LatestChat(BaseModel):
    day: str
    messages: int
    cards: int
    top_patterns: list[PatternCount]
    sample: MarkedMessage | None


class WeekPoint(BaseModel):
    week_start: str
    per_100_words: float
    messages: int
    words: int
    issues: int


class WritingTrend(BaseModel):
    points: list[WeekPoint]
    latest: float | None
    average_before: float | None
    verdict: Literal["fewer", "more", "same"] | None


class Home(BaseModel):
    empty: bool
    practice: PracticeSummary
    focus: Focus | None
    latest_chat: LatestChat | None
    word_of_the_day: WordBrief | None
    writing: WritingTrend


# ---------- mistakes ----------

class PatternRow(BaseModel):
    key: str
    title: str
    times: int
    last: str | None
    mastery: Mastery


class CategoryGroup(BaseModel):
    key: str
    title: str
    zh: str
    patterns: list[PatternRow]


class PatternList(BaseModel):
    categories: list[CategoryGroup]


class CardRow(BaseModel):
    id: str
    pattern: str
    severity: Severity
    times: int
    last: str | None
    status: ItemStatus
    strength: int
    due_at: str | None
    sentence: str
    corrected: str
    wrong: str
    right: str
    explain: str
    explain_zh: str


class PatternDetail(BaseModel):
    key: str
    title: str
    category: str
    category_title: str
    rule: str
    rule_zh: str
    mastery: Mastery
    more_examples: list[ExamplePair]
    cards: list[CardRow]
    total: int
    page: int
    pages: int


# ---------- words ----------

class WordGroupCount(BaseModel):
    group: WordGroup
    count: int


class WordList(BaseModel):
    group: WordGroup
    groups: list[WordGroupCount]
    due: int
    mastered: int
    total: int
    words: list[WordBrief]
    total_in_group: int
    page: int
    pages: int


# ---------- messages ----------

class MessageRow(BaseModel):
    id: str
    ts: str
    day: str
    project: str
    source: Literal["claude-code", "app"]
    text: str
    fixed: str
    polished: str
    words: int
    issues: int


class MessageCounts(BaseModel):
    mistakes: int
    all: int


class MessagePage(BaseModel):
    messages: list[MessageRow]
    next_cursor: str | None
    counts: MessageCounts


# ---------- progress ----------

class DayPoint(BaseModel):
    day: str
    answered: int
    correct: int


class CategoryMastery(BaseModel):
    key: str
    title: str
    zh: str
    total: int
    mastered: int
    learning: int


class RepeatRow(BaseModel):
    card_id: str
    pattern: str
    pattern_title: str
    wrong: str
    right: str
    times: int
    status: ItemStatus


class Kpis(BaseModel):
    streak: int
    right_pct_7d: int | None
    cards_mastered: int
    cards_total: int
    words_mastered: int
    words_total: int
    answers_total: int
    rounds: int


class Progress(BaseModel):
    kpis: Kpis
    writing: WritingTrend
    practice: list[DayPoint]
    mastery: list[CategoryMastery]
    repeated: list[RepeatRow]
