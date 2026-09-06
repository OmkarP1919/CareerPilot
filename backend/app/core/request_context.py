"""Request-scoped context via :class:`contextvars.ContextVar`.

The request ID is the single piece of per-request state that needs to
be accessible from application loggers, middleware and other utilities
without threading a ``Request`` object through every call.

Usage inside request handlers or middleware::

    from app.core.request_context import set_request_id, get_request_id

    set_request_id("abc-123")
    rid = get_request_id()  # "abc-123" or ""

The ``ContextVar`` is inherently safe under concurrent requests and is
automatically reset for each new thread/task boundary.  The middleware
sets it at request start and clears it at request end, so there is no
cross-request leakage.
"""

from contextvars import ContextVar

_request_id: ContextVar[str] = ContextVar("request_id", default="")


def set_request_id(request_id: str) -> None:
    """Store the current request ID in the context."""
    _request_id.set(request_id)


def get_request_id() -> str:
    """Return the current request ID, or an empty string if unset."""
    return _request_id.get()
