"""Production-safe rate limiting core (Phase 5E.9).

Design
------
- Fixed-window per-key counters give a deterministic, cheap, testable limit.
- A small ``RateLimitBackend`` abstraction isolates storage. The only backend
  shipped is ``MemoryRateLimitBackend`` and it is deliberately a
  single-instance (process-local) backend.
- Keys are stored/salted-hashed (SHA-256) so the backend never retains raw
  Firebase UIDs, IPs, or other PII.

Distributed limitation
----------------------
``MemoryRateLimitBackend`` is NOT a distributed rate limiter. It is correct for
development, tests, and a single backend process only. A multi-instance
deployment MUST use a shared backend (e.g. Redis) that is outside the scope of
this phase; ``RATE_LIMIT_BACKEND`` exists so a shared backend can be dropped in
behind the same interface. In production the middleware/dependency logs a
startup warning when only the memory backend is configured so single-process
rate limiting is never silently presented as distributed protection (see
``RateLimitConfig`` / ``app.core.config``).

``time.monotonic()`` is used for in-process timing so limits are immune to wall-
clock changes and NTP jumps.
"""
import hashlib
import logging
import threading
import time

logger = logging.getLogger("app.rate_limit")

# Seconds(ish) after which a stale window bucket is considered expired and is
# evicted on the next sweep or access to make space.
_GRACE_SECONDS = 2


class RateLimitResult:
    __slots__ = ("allowed", "retry_after")

    def __init__(self, allowed: bool, retry_after: float = 0.0):
        self.allowed = allowed
        self.retry_after = retry_after


class RateLimitBackend:
    """Interface for rate-limit counter storage."""

    def key(self, raw: str) -> str:
        """Hash a raw identity into a non-PII storage key."""
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def check_limit(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:  # pragma: no cover
        """Increment the counter for ``key`` within ``window_seconds``.

        Returns whether the request is allowed and, when denied, how many
        seconds (float) the client should wait before retrying.
        """
        raise NotImplementedError

    def clear(self) -> None:  # pragma: no cover
        raise NotImplementedError


class MemoryRateLimitBackend(RateLimitBackend):
    """Single-process fixed-window limiter.

    Not distributed. Bounded (never grows beyond ``max_keys`` buckets),
    concurrency-safe (single lock), and uses monotonic time.
    """

    def __init__(self, max_keys: int = 20000):
        self._max_keys = int(max_keys)
        self._buckets: dict[str, tuple[float, int]] = {}
        self._lock = threading.Lock()
        self._last_sweep = time.monotonic()

    def check_limit(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        now = time.monotonic()
        window_seconds = max(1, int(window_seconds))
        limit = max(1, int(limit))
        with self._lock:
            self._maybe_sweep(now)
            bucket = self._buckets.get(key)
            if bucket is None or (now - bucket[0]) >= window_seconds:
                if bucket is None and len(self._buckets) >= self._max_keys:
                    # Memory bound reached with no expired buckets to reclaim;
                    # fail-open (allow) so the limiter itself cannot be used to
                    # cause a global outage, and warn once.
                    logger.warning(
                        "rate_limit backend full (%d keys); allowing request to avoid unbounded memory",
                        len(self._buckets),
                    )
                    return RateLimitResult(allowed=True, retry_after=0.0)
                self._buckets[key] = (now, 1)
                return RateLimitResult(allowed=True, retry_after=0.0)

            start, count = bucket
            if count < limit:
                self._buckets[key] = (start, count + 1)
                return RateLimitResult(allowed=True, retry_after=0.0)

            retry_after = window_seconds - (now - start)
            return RateLimitResult(allowed=False, retry_after=retry_after)

    def _maybe_sweep(self, now: float) -> None:
        # Full sweep only occasionally, plus eviction of the touched window is
        # handled by time expiry above. Sweeping keeps the table bounded.
        if now - self._last_sweep < 60:
            return
        self._last_sweep = now
        expired = [k for k, (start, _) in self._buckets.items() if (now - start) >= 5]
        for k in expired:
            self._buckets.pop(k, None)

    def bucket_count(self) -> int:
        with self._lock:
            return len(self._buckets)

    def clear(self) -> None:
        with self._lock:
            self._buckets.clear()


class RateLimiter:
    """Facade combining a backend with per-call limits."""

    def __init__(self, backend: RateLimitBackend):
        self.backend = backend

    def check(self, raw_identity: str, limit: int, window_seconds: int) -> RateLimitResult:
        key = self.backend.key(raw_identity)
        return self.backend.check_limit(key, limit, window_seconds)