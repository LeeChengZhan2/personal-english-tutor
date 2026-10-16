"""The FastAPI app: the API under /api, and the built web app (web/dist) for every other path."""

from __future__ import annotations

import base64
import hashlib
import logging
import mimetypes
import re
import threading
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse

from coach import db

from . import __version__
from .context import AppContext, Paths
from .errors import ApiException, install_handlers
from .routes import accounts, content, meta, update
from .security import LocalOnlyMiddleware
from .update import UpdateManager

log = logging.getLogger("tutor")

# Windows can map .js to text/plain from the registry; browsers refuse module scripts with that type.
for _type, _ext in (("text/javascript", ".js"), ("text/css", ".css"), ("image/svg+xml", ".svg"), ("font/woff2", ".woff2"),
                    ("application/manifest+json", ".webmanifest"), ("application/json", ".map")):
    mimetypes.add_type(_type, _ext)

NOT_BUILT = """<!doctype html><meta charset="utf-8"><title>Personal English Tutor</title>
<body style="font:16px system-ui;max-width:40rem;margin:4rem auto;padding:0 1rem;line-height:1.5">
<h1>The app isn't built yet</h1><p>Run <code>pnpm -C web install</code> and <code>pnpm -C web build</code>,
then reload. (While developing, run <code>pnpm -C web dev</code> and open http://localhost:5173.)</p>"""


def _csp(index_html: str) -> str:
    """Only this app's own files; the one inline script (the no-flash theme) is allowed by its hash."""
    hashes = [
        "'sha256-" + base64.b64encode(hashlib.sha256(script.encode("utf-8")).digest()).decode() + "'"
        for script in re.findall(r"<script>(.*?)</script>", index_html, re.S)
    ]
    return "; ".join([
        "default-src 'self'", "script-src 'self' " + " ".join(hashes), "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data:", "font-src 'self' data:", "connect-src 'self'", "object-src 'none'",
        "base-uri 'none'", "form-action 'self'", "frame-ancestors 'none'",
    ])


def _mount_web(app: FastAPI, dist: Path) -> None:
    index = dist / "index.html"
    root = dist.resolve()

    @app.get("/{full_path:path}", include_in_schema=False)
    def web(full_path: str):
        if full_path == "api" or full_path.startswith("api/"):
            raise ApiException(404, "not_found", "There is no such API endpoint.")
        if not index.exists():
            return HTMLResponse(NOT_BUILT, status_code=503)
        if full_path:
            candidate = (dist / full_path).resolve()
            if candidate.is_file() and root in candidate.parents:
                cache = "public, max-age=31536000, immutable" if full_path.startswith("assets/") else "no-cache"
                return FileResponse(candidate, headers={"Cache-Control": cache})
        html = index.read_text(encoding="utf-8")
        return HTMLResponse(html, headers={"Cache-Control": "no-cache", "Content-Security-Policy": _csp(html)})


def create_app(paths: Paths | None = None, *, config: dict | None = None, clock: Callable[[], int] | None = None,
               dev: bool = False) -> FastAPI:
    paths = paths or Paths.default()
    ctx = AppContext(paths, config, clock)
    updates = UpdateManager(ctx)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        with ctx.conn() as conn:
            try:
                path = db.daily_backup(conn, paths.backups)
                if path:
                    log.info("progress backed up to %s", path)
            except OSError as e:
                log.warning("daily backup failed: %s", e)
        # read the lessons now, so the first page doesn't wait for it
        threading.Thread(target=ctx.lessons.snapshot, daemon=True).start()
        yield
        updates.shutdown()  # a running update stops at its next step; its progress so far is kept

    app = FastAPI(
        title="Personal English Tutor", version=__version__, lifespan=lifespan,
        openapi_url="/api/openapi.json", docs_url="/api/docs", redoc_url=None,
        separate_input_output_schemas=False,
        generate_unique_id_function=lambda route: route.name,  # readable names in the generated client
    )
    app.state.ctx = ctx
    app.state.updates = updates
    install_handlers(app)
    app.include_router(meta.router)
    app.include_router(content.router)
    app.include_router(accounts.router)
    app.include_router(update.router)
    _mount_web(app, paths.web_dist)
    app.add_middleware(LocalOnlyMiddleware, port=int(ctx.config.get("server_port") or 8765), dev=dev)
    return app
