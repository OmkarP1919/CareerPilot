"""ASGI middleware enforcing a global request-body size limit.

Protects against oversized request bodies (both requests with an explicit
``Content-Length`` and chunked requests without one) WITHOUT buffering the
entire body in memory:

- If ``Content-Length`` is present and exceeds the limit, the request is
  rejected immediately (413) without invoking the downstream application.
- If ``Content-Length`` is absent (chunked transfer encoding), body bytes are
  counted while streaming. Once the cumulative count exceeds the limit, no
  further body bytes are forwarded downstream and a 413 is returned.

Only safety metadata about the request is ever logged; request bodies, query
parameters, and headers are never written to logs.

This is a global, configurable cap. It is intentionally larger than the
per-file 10 MiB upload limit (which remains enforced by the application for
resumes/application documents) so multipart/form-data overhead stays below
the cap while genuinely oversized bodies are still stopped early.
"""

import json
import logging

from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger("app.security")

_CHUNK = "chunked"

_BODY_TOO_LARGE = {
    "detail": "Request body too large",
}


class RequestBodyLimitMiddleware:
    """Reject request bodies larger than ``max_bytes`` (streaming, 413)."""

    def __init__(self, app: ASGIApp, max_bytes: int):
        self.app = app
        self.max_bytes = int(max_bytes)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope["headers"])
        content_length = _parse_content_length(headers.get(b"content-length"))

        # Immediate short-circuit: a declared Content-Length over the cap never
        # reaches the application, so no body is consumed or written to storage.
        if content_length is not None and content_length > self.max_bytes:
            await _send_413(send)
            return

        limit_exceeded = False
        ended = False
        count = 0

        async def receive_wrapper() -> dict:
            nonlocal limit_exceeded, ended, count
            if ended:
                return {"type": "http.request", "body": b"", "more_body": False}
            message = await receive()
            if message.get("type") == "http.request":
                body = message.get("body", b"")
                total = count + len(body)
                if total > self.max_bytes:
                    # Stop forwarding body bytes downstream: the application is
                    # never handed the crossed chunk, so it cannot persist a
                    # partial large body. Terminate the stream cleanly.
                    limit_exceeded = True
                    ended = True
                    return {"type": "http.request", "body": b"", "more_body": False}
                count = total
                if not message.get("more_body", False):
                    ended = True
            return message

        async def send_wrapper(message: dict) -> None:
            if limit_exceeded and message.get("type") == "http.response.start":
                # Suppress the downstream response and return a small JSON 413
                # instead. No body/path/query content is included.
                await _send_413(send)
                return
            await send(message)

        await self.app(scope, receive_wrapper, send_wrapper)


def _parse_content_length(raw: bytes | None) -> int | None:
    """Return the declared Content-Length, or ``None`` if absent/invalid.

    A malformed (non-numeric or negative) value is treated as absent so the
    request is handled via streaming byte-counting rather than a bogus jump.
    """
    if raw is None:
        return None
    text = raw.decode("latin-1").strip()
    if not text.isdigit():
        return None
    try:
        value = int(text)
    except ValueError:
        return None
    if value < 0:
        return None
    return value


async def _send_413(send: Send) -> None:
    """Write a minimal JSON 413 response."""

    body = json.dumps(_BODY_TOO_LARGE).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body, "more_body": False})
