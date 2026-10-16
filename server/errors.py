"""Every error the API returns has the same body: {"code", "message", "details"?} (models.ApiError)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("tutor")


class ApiException(Exception):
    def __init__(self, status: int, code: str, message: str, details: list[dict[str, Any]] | None = None):
        super().__init__(message)
        self.status, self.code, self.message, self.details = status, code, message, details


def body(code: str, message: str, details: list[dict[str, Any]] | None = None) -> dict:
    out: dict[str, Any] = {"code": code, "message": message}
    if details:
        out["details"] = details
    return out


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiException)
    async def api_error(_: Request, e: ApiException) -> JSONResponse:
        return JSONResponse(body(e.code, e.message, e.details), status_code=e.status)

    @app.exception_handler(RequestValidationError)
    async def invalid(_: Request, e: RequestValidationError) -> JSONResponse:
        details = [{"loc": [str(p) for p in err.get("loc", ())], "msg": err.get("msg", "")} for err in e.errors()]
        return JSONResponse(body("invalid_request", "Some of what was sent isn't valid.", details), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, e: StarletteHTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed"}.get(e.status_code, "http_error")
        return JSONResponse(body(code, str(e.detail)), status_code=e.status_code)

    @app.exception_handler(Exception)
    async def crashed(_: Request, e: Exception) -> JSONResponse:
        log.exception("unhandled error")
        return JSONResponse(body("internal", "Something went wrong on the server."), status_code=500)
