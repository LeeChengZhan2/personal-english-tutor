"""Update my lessons: read new conversations, find the mistakes, add lessons. One update at a time."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from ..context import AppContext, get_ctx
from ..errors import ApiException
from ..models import ApiError, UpdateIn, UpdatePreview, UpdateStatus
from ..update import UpdateManager, preview

router = APIRouter(prefix="/api/update", tags=["update"],
                   responses={400: {"model": ApiError}, 409: {"model": ApiError}, 422: {"model": ApiError},
                              500: {"model": ApiError}})


def get_updates(request: Request) -> UpdateManager:
    return request.app.state.updates


def _selected(ctx: AppContext, ids: list[str] | None):
    items = ctx.accounts()
    if not items:
        raise ApiException(400, "not_configured", "Add your Claude account in Settings first.")
    if ids is None:
        return items
    chosen = [a for a in items if a.id in set(ids)]
    if not chosen:
        raise ApiException(422, "no_accounts_chosen", "Choose at least one account.")
    return chosen


@router.get("", response_model=UpdateStatus)
def update_status(updates: UpdateManager = Depends(get_updates)) -> dict:
    return updates.status()


@router.get("/preview", response_model=UpdatePreview)
def update_preview(account_ids: list[str] | None = Query(None), ctx: AppContext = Depends(get_ctx),
                   updates: UpdateManager = Depends(get_updates)) -> dict:
    return {**preview(_selected(ctx, account_ids)), "last_finished_at": updates.status()["last_finished_at"]}


@router.post("", response_model=UpdateStatus, status_code=202)
def start_update(body: UpdateIn, ctx: AppContext = Depends(get_ctx), updates: UpdateManager = Depends(get_updates)) -> dict:
    return updates.start(_selected(ctx, body.account_ids))


@router.post("/stop", response_model=UpdateStatus)
def stop_update(updates: UpdateManager = Depends(get_updates)) -> dict:
    return updates.stop()
