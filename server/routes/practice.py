"""Practice rounds: start a word round, answer its questions, and finish it."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from coach import practice

from ..context import AppContext, get_ctx
from ..errors import ApiException
from ..models import AnswerIn, AnswerOut, ApiError, RoundIn, RoundScore, WordRound

router = APIRouter(prefix="/api", tags=["practice"],
                   responses={404: {"model": ApiError}, 422: {"model": ApiError}, 500: {"model": ApiError}})


@router.post("/rounds", response_model=WordRound)
def start_round(body: RoundIn, ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.conn() as conn:
        view = ctx.view(conn)
        return practice.start_word_round(conn, view, body.group, body.tap_only, body.client_id)


@router.post("/rounds/{round_id}/answers", response_model=AnswerOut)
def answer(round_id: str, body: AnswerIn, ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.conn() as conn:
        try:
            return practice.answer(conn, round_id, body.item_id, body.answer, body.seconds, ctx.clock())
        except LookupError as e:
            raise ApiException(404, "not_found", str(e)) from e


@router.post("/rounds/{round_id}/finish", response_model=RoundScore)
def finish_round(round_id: str, ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.conn() as conn:
        view = ctx.view(conn)
        try:
            score = practice.finish(conn, round_id, view.now_ms)
        except LookupError as e:
            raise ApiException(404, "not_found", str(e)) from e
    return {**score, "words_due": len(view.due_words())}
