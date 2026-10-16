"""Ask Claude for JSON with the user's accounts: through an account's Claude Code sign-in (`claude -p`), or its
Anthropic API key (the official SDK, structured outputs). Accounts are tried in order; one that hits its usage
limit or can't sign in hands over to the next.
"""

from __future__ import annotations

import copy
import json
import logging
import threading

from . import accounts as accounts_mod, claude_cli
from .accounts import Account
from .config import load_config

log = logging.getLogger("coach")

# Short names (as in config.json) -> the API's model ids. The Claude Code CLI takes the short names as they are.
API_MODELS = {"opus": "claude-opus-5-5", "sonnet": "claude-sonnet-5-5", "haiku": "claude-haiku-5-5"}
# Models whose refusals the API can re-run on another model by itself (server-side fallback).
SERVER_FALLBACK = {"claude-opus-5-5", "claude-sonnet-5-5"}
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMError(RuntimeError):
    """`kind`: not_configured, usage_limit, auth, overloaded, refused, too_long, invalid_output, cancelled,
    timeout, not_installed, failed."""

    def __init__(self, message: str, kind: str = "failed", account: str | None = None, resets: str | None = None):
        super().__init__(message)
        self.kind = kind
        self.account = account
        self.resets = resets


def model_alias(tier: str, config: dict | None = None) -> str:
    """'sonnet' / 'haiku' / ... for a tier: 'analysis' (finding mistakes) or 'quick' (checking one answer)."""
    config = config or load_config()
    if tier == "quick":
        return (config.get("ai_models") or {}).get("quick") or "haiku"
    return config.get("analyze_model") or "sonnet"


def strict_schema(schema: dict) -> dict:
    """The schema with additionalProperties: false on every object, as structured outputs require."""
    out = copy.deepcopy(schema)

    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                node.setdefault("additionalProperties", False)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(out)
    return out


def ask_json(prompt: str, schema: dict, *, tier: str = "analysis", accounts: list[Account] | None = None,
             cancel: threading.Event | None = None, timeout: float = 900) -> tuple[dict, Account]:
    """The model's JSON answer and the account that gave it. Raises LLMError."""
    accounts = accounts if accounts is not None else accounts_mod.load_accounts()
    if not accounts:
        raise LLMError("No Claude account is set up. Add one in Settings.", kind="not_configured")
    alias = model_alias(tier)
    last: LLMError | None = None
    for account in accounts_mod.ordered(accounts):
        if cancel is not None and cancel.is_set():
            raise LLMError("stopped", kind="cancelled")
        try:
            if account.method == "api-key":
                answer = _ask_api(account, prompt, schema, alias, tier, cancel, timeout)
            else:
                answer = _ask_cli(account, prompt, schema, alias, cancel, timeout)
        except LLMError as e:
            e.account = account.name
            log.warning("%s: %s (%s)", account.name, e.kind, str(e)[:300])
            if e.kind in ("usage_limit", "auth"):
                if e.kind == "usage_limit":
                    accounts_mod.mark_limited(account, e.resets)
                last = e
                continue  # the next account may still have room
            raise
        accounts_mod.clear_limited(account)
        return answer, account
    assert last is not None
    raise last


def _ask_cli(account: Account, prompt: str, schema: dict, alias: str, cancel, timeout: float) -> dict:
    try:
        result = claude_cli.run(prompt, model=alias, schema=schema, tools="", timeout=timeout,
                                config_dir=str(account.home) if account.folder else None, cancel=cancel)
    except claude_cli.ClaudeError as e:
        raise LLMError(str(e), kind=e.kind, resets=e.resets) from e
    answer = result.get("structured_output")
    if not isinstance(answer, dict):
        try:
            answer = json.loads(result.get("result", ""))
        except ValueError as e:
            raise LLMError("Claude's answer wasn't JSON.", kind="invalid_output") from e
    if not isinstance(answer, dict):
        raise LLMError("Claude's answer wasn't a JSON object.", kind="invalid_output")
    return answer


def _ask_api(account: Account, prompt: str, schema: dict, alias: str, tier: str, cancel, timeout: float) -> dict:
    import anthropic  # only needed for API-key accounts

    model = API_MODELS.get(alias, alias)
    client = anthropic.Anthropic(api_key=account.api_key, timeout=timeout, max_retries=2)
    output_config: dict = {"format": {"type": "json_schema", "schema": strict_schema(schema)}}
    if tier == "quick":
        output_config["effort"] = "low"
    params: dict = {
        "model": model,
        "max_tokens": 32000 if tier == "analysis" else 2000,
        "messages": [{"role": "user", "content": prompt}],
        "output_config": output_config,
    }
    if model in SERVER_FALLBACK:  # a declined request is re-run on Anthropic's recommended model
        params["betas"] = [FALLBACK_BETA]
        params["fallbacks"] = "default"
    try:
        with client.beta.messages.stream(**params) as stream:
            for _ in stream:
                if cancel is not None and cancel.is_set():
                    raise LLMError("stopped", kind="cancelled")
            message = stream.get_final_message()
    except anthropic.AuthenticationError as e:
        raise LLMError("The API key was not accepted.", kind="auth") from e
    except anthropic.PermissionDeniedError as e:
        raise LLMError("This API key isn't allowed to use that model.", kind="auth") from e
    except anthropic.RateLimitError as e:
        raise LLMError("The API key hit its rate limit.", kind="usage_limit") from e
    except anthropic.BadRequestError as e:
        if "credit balance" in str(e).lower():
            raise LLMError("The API key's account is out of credit.", kind="usage_limit") from e
        raise LLMError(f"The API rejected the request: {e}", kind="failed") from e
    except anthropic.APITimeoutError as e:
        raise LLMError("The API took too long to answer.", kind="timeout") from e
    except anthropic.APIConnectionError as e:
        raise LLMError("Couldn't reach the Anthropic API. Check the internet connection.", kind="failed") from e
    except anthropic.APIStatusError as e:
        kind = "overloaded" if e.status_code >= 500 else "failed"
        raise LLMError(f"The API answered with an error ({e.status_code}).", kind=kind) from e
    if message.stop_reason == "refusal":
        raise LLMError("Claude declined to analyze this text.", kind="refused")
    if message.stop_reason == "max_tokens":
        raise LLMError("The answer was too long and got cut off.", kind="too_long")
    text = next((b.text for b in message.content if b.type == "text"), "")
    try:
        answer = json.loads(text)
    except ValueError as e:
        raise LLMError("Claude's answer wasn't JSON.", kind="invalid_output") from e
    if not isinstance(answer, dict):
        raise LLMError("Claude's answer wasn't a JSON object.", kind="invalid_output")
    return answer


def check_account(account: Account) -> tuple[bool, str]:
    """Whether the account can be used for analysis, in a sentence. Free: makes no model call."""
    files = len(accounts_mod.conversation_files(account))
    found = f"{files} conversation file{'s' if files != 1 else ''} found in {account.projects}."
    if account.method == "api-key":
        if not account.api_key:
            return False, "No API key saved for this account."
        import anthropic

        model = API_MODELS.get(model_alias("analysis"), model_alias("analysis"))
        try:
            anthropic.Anthropic(api_key=account.api_key, timeout=20, max_retries=1).models.retrieve(model)
        except anthropic.AuthenticationError:
            return False, "The API key was not accepted."
        except anthropic.PermissionDeniedError:
            return False, f"The API key can't use {model}."
        except anthropic.APIConnectionError:
            return False, "Couldn't reach the Anthropic API. Check the internet connection."
        except anthropic.APIStatusError as e:
            return False, f"The API answered with an error ({e.status_code})."
        return True, f"The API key works. {found}"
    from .config import find_claude

    if not find_claude():
        return False, "Claude Code isn't installed on this PC, so this account can't analyze. Use an API key instead."
    if not accounts_mod.signed_in(account):
        how = "run `claude` and type /login" if account.uses_default_folder else f"run `uv run tutor login {account.name}`"
        return False, f"Claude Code isn't signed in for this folder: {how}."
    email = accounts_mod.account_email(account)
    return True, f"Signed in{f' as {email}' if email else ''}. {found}"
