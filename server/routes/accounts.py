"""The user's Claude accounts: where their conversations are, and how to call Claude with them."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Response

from coach import accounts, llm
from coach.config import CLAUDE_HOME

from ..context import AppContext, get_ctx
from ..errors import ApiException
from ..models import AccountIn, AccountOut, AccountsOut, AccountUpdate, ApiError, CheckOut
from .meta import account_ready, claude_path

router = APIRouter(prefix="/api/accounts", tags=["accounts"],
                   responses={400: {"model": ApiError}, 404: {"model": ApiError}, 422: {"model": ApiError},
                              500: {"model": ApiError}})


def account_out(account: accounts.Account) -> dict:
    limited = accounts.limited_info(account)
    return {
        "id": account.id, "name": account.name, "method": account.method, "folder": account.folder,
        "folder_path": str(account.home), "default_folder": account.uses_default_folder,
        "api_key_hint": accounts.masked_key(account.api_key),
        "email": accounts.account_email(account) if account.method == "claude-code" else None,
        "signed_in": accounts.signed_in(account), "ready": account_ready(account),
        "conversation_files": len(accounts.conversation_files(account)),
        "limited_until": (limited[1] or "soon") if limited else None,
    }


def _validate(name: str, method: str, folder: str, api_key: str, others: list[accounts.Account]) -> None:
    if any(a.name.lower() == name.strip().lower() for a in others):
        raise ApiException(422, "duplicate_name", "You already have an account with that name.")
    if method == "api-key" and not api_key.strip():
        raise ApiException(422, "api_key_required", "Paste the API key for this account.")
    if folder.strip():
        home = Path(folder.strip()).expanduser()
        if not home.is_dir():
            raise ApiException(422, "folder_missing", f"There's no folder at {home}.")


def _find(items: list[accounts.Account], account_id: str) -> int:
    for i, a in enumerate(items):
        if a.id == account_id:
            return i
    raise ApiException(404, "not_found", "That account doesn't exist any more.")


@router.get("", response_model=AccountsOut)
def list_accounts(ctx: AppContext = Depends(get_ctx)) -> dict:
    return {"accounts": [account_out(a) for a in ctx.accounts()], "default_folder": str(CLAUDE_HOME),
            "claude_installed": bool(claude_path())}


@router.post("", response_model=AccountOut, status_code=201)
def add_account(body: AccountIn, ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.accounts_lock:
        items = ctx.accounts()
        _validate(body.name, body.method, body.folder, body.api_key, items)
        account = accounts.Account(id=accounts.new_id(), name=body.name.strip(), method=body.method,
                                   folder=body.folder.strip(), api_key=body.api_key.strip() if body.method == "api-key" else "")
        ctx.save_accounts([*items, account])
    return account_out(account)


@router.put("/{account_id}", response_model=AccountOut)
def edit_account(account_id: str, body: AccountUpdate, ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.accounts_lock:
        items = ctx.accounts()
        i = _find(items, account_id)
        current = items[i]
        name = body.name.strip() if body.name is not None else current.name
        method = body.method or current.method
        folder = body.folder.strip() if body.folder is not None else current.folder
        api_key = body.api_key.strip() if body.api_key else current.api_key
        if method != "api-key":
            api_key = ""
        _validate(name, method, folder, api_key, [a for a in items if a.id != account_id])
        items[i] = accounts.Account(id=current.id, name=name, method=method, folder=folder, api_key=api_key)
        ctx.save_accounts(items)
    return account_out(items[i])


@router.delete("/{account_id}", status_code=204)
def remove_account(account_id: str, ctx: AppContext = Depends(get_ctx)) -> Response:
    with ctx.accounts_lock:
        items = ctx.accounts()
        del items[_find(items, account_id)]
        ctx.save_accounts(items)
    return Response(status_code=204)


@router.post("/{account_id}/check", response_model=CheckOut)
def check_account(account_id: str, ctx: AppContext = Depends(get_ctx)) -> dict:
    items = ctx.accounts()
    ok, message = llm.check_account(items[_find(items, account_id)])
    return {"ok": ok, "message": message}
