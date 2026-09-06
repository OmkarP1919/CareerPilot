"""Application logging configuration.

Sets up a minimal, production-safe logging foundation for CareerPilot:

- A format that includes the request ID when available.
- A filter that strips sensitive data from specific log fields.
- A ``setup_logging()`` function called once at application startup.

The root logger level is controlled by the ``LOG_LEVEL`` environment
variable (default ``INFO``).  Uvicorn's own loggers are left untouched;
only the application ``app.*`` namespace is configured.
"""

import logging
import re
import sys

from app.core.request_context import get_request_id

# Simple key=value log line format.
_FORMAT = "%(asctime)s %(levelname)s %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Characters that must never appear in a log line (injection guard).
_CONTROL_RE = re.compile(r"[\x00-\x08\x0e-\x1f\x7f]")


class _RequestContextFilter(logging.Filter):
    """Inject ``request_id`` into every log record and sanitize ``path``."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        # Ensure path, if present, is a clean string.
        path = getattr(record, "path", None)
        if isinstance(path, str):
            record.path = _CONTROL_RE.sub("", path)
        return True


def setup_logging(log_level: str = "INFO") -> None:
    """Configure the application root logger.

    This is intended to be called exactly once during application startup
    (``app.core.config.get_settings().LOG_LEVEL`` → ``setup_logging()``).

    Uvicorn's loggers are children of the Python root logger and are
    therefore not affected by the level set here; their levels are
    controlled by Uvicorn itself.

    Request logging does NOT include the Authorization header, cookies,
    request/response bodies, or any user file contents; those values are
    never passed to the logger, so the information is excluded by
    construction rather than redacted.
    """
    level_name = (log_level or "INFO").strip().upper()
    numeric_level = getattr(logging, level_name, logging.INFO)
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO

    formatter = logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(numeric_level)
    root.addHandler(handler)

    # Apply the request-id context filter so every application logger can
    # reference ``%(request_id)s`` and emit the current request ID.
    handler.addFilter(_RequestContextFilter())

    # Quiet noisy third-party loggers that produce no value in production.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
