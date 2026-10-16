"""The read-only pages: home, mistakes (patterns), words, messages and progress."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query

from coach import insights

from ..context import AppContext, get_ctx
from ..errors import ApiException
from ..models import ApiError, Home, MessagePage, MessageRow, PatternDetail, PatternList, Progress, WordKind, WordList

router = APIRouter(prefix="/api", tags=["content"],
                   responses={400: {"model": ApiError}, 404: {"model": ApiError}, 422: {"model": ApiError},
                              500: {"model": ApiError}})


@router.get("/home", response_model=Home)
def home(ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.conn() as conn:
        return insights.home(ctx.view(conn))


@router.get("/patterns", response_model=PatternList)
def patterns(ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.conn() as conn:
        return insights.pattern_list(ctx.view(conn))


@router.get("/patterns/{key}", response_model=PatternDetail)
def pattern(key: str, page: int = Query(1, ge=1), page_size: int = Query(20, ge=5, le=100),
            ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.conn() as conn:
        detail = insights.pattern_detail(ctx.view(conn), key, page, page_size)
    if detail is None:
        raise ApiException(404, "not_found", "This mistake pattern isn't in your lessons.")
    return detail


@router.get("/words", response_model=WordList)
def words(kind: WordKind = "spelling", page: int = Query(1, ge=1), page_size: int = Query(24, ge=6, le=100),
          ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.conn() as conn:
        return insights.word_list(ctx.view(conn), kind, page, page_size)


@router.get("/messages", response_model=MessagePage)
def messages(filter: Literal["mistakes", "all"] = "mistakes", cursor: str | None = None,
             limit: int = Query(30, ge=5, le=100), ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.conn() as conn:
        view = ctx.view(conn)
    try:
        return insights.message_page(view, filter, cursor, limit)
    except ValueError as e:
        raise ApiException(400, "bad_cursor", "That page link is out of date. Reload the list.") from e


@router.get("/messages/{message_id}", response_model=MessageRow)
def message(message_id: str, ctx: AppContext = Depends(get_ctx)) -> dict:
    snap = ctx.lessons.snapshot()
    m = snap.message_by_id.get(message_id)
    if m is None:
        raise ApiException(404, "not_found", "That message isn't in your lessons.")
    with ctx.conn() as conn:
        return insights.message_row(ctx.view(conn), m)


@router.get("/progress", response_model=Progress)
def progress(ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.conn() as conn:
        return insights.progress(ctx.view(conn))
