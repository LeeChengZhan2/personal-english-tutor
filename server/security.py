"""Keeps the local app local.

- Only requests addressed to localhost are answered (blocks DNS rebinding: a web page that points its own
  domain at 127.0.0.1 still sends its own Host header).
- Requests that change something must come from the app's own pages (Origin / Sec-Fetch-Site), so another
  website open in the browser can't post to it.
- Bodies of such requests are JSON and small.
"""

from __future__ import annotations

import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

LOCAL_HOSTS = {"127.0.0.1", "localhost", "[::1]", "::1"}
UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}
MAX_BODY = 256 * 1024


def _host_name(host: str) -> str:
    host = host.strip().lower()
    if host.startswith("["):
        return host[: host.find("]") + 1] if "]" in host else host
    return host.rsplit(":", 1)[0] if host.count(":") == 1 else host


class LocalOnlyMiddleware:
    def __init__(self, app: ASGIApp, *, port: int, dev: bool = False, extra_hosts: tuple[str, ...] = ()):
        self.app = app
        self.hosts = LOCAL_HOSTS | set(extra_hosts)
        ports = {port} | ({5173} if dev else set())
        self.origins = {f"http://{h}:{p}" for h in ("127.0.0.1", "localhost") for p in ports}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        if _host_name(headers.get("host", "")) not in self.hosts:
            await _error(send, 400, "bad_host", "This app only answers on localhost.")
            return
        if scope.get("method", "GET") in UNSAFE:
            origin = headers.get("origin")
            site = headers.get("sec-fetch-site")
            if origin is not None and origin not in self.origins:
                await _error(send, 403, "forbidden_origin", "Requests must come from the Personal English Tutor app.")
                return
            if origin is None and site is not None and site not in ("same-origin", "none"):
                await _error(send, 403, "forbidden_origin", "Requests must come from the Personal English Tutor app.")
                return
            length = headers.get("content-length")
            if length and length.isdigit() and int(length) > MAX_BODY:
                await _error(send, 413, "too_large", "That is too much text to send at once.")
                return
            if length and length != "0":
                ctype = headers.get("content-type", "").split(";")[0].strip().lower()
                if ctype != "application/json":
                    await _error(send, 415, "unsupported_media_type", "Send JSON.")
                    return
        path = scope.get("path", "")

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                extra = [(b"x-content-type-options", b"nosniff"), (b"referrer-policy", b"no-referrer")]
                if path.startswith("/api/"):
                    extra.append((b"cache-control", b"no-store"))
                message["headers"] = list(message.get("headers", [])) + extra
            await send(message)

        await self.app(scope, receive, send_with_headers)


async def _error(send: Send, status: int, code: str, message: str) -> None:
    body = json.dumps({"code": code, "message": message}).encode()
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
    await send({"type": "http.response.body", "body": body})
