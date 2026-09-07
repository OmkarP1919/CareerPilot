from urllib.parse import urlsplit

from pydantic_settings import BaseSettings
from functools import lru_cache
import logging

logger = logging.getLogger("app.config")

# Origins that are safe to send credentials to during local development.
# Production deployments MUST set CORS_ORIGINS explicitly; see
# cors_origins_for() below for the fail-safe production policy.
DEV_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
]

# Hosts accepted during local development when TRUSTED_HOSTS is empty.
# Starlette's TrustedHostMiddleware compares against the Host header hostname
# (port stripped); IPv6 literals are included here but note Starlette splits
# the header on ":" so matching of IPv6 literal Host headers is limited.
DEV_TRUSTED_HOSTS = ["localhost", "127.0.0.1", "::1"]

# Default global request-body cap: 16 MiB. This is deliberately above the
# 10 MiB file-upload limit plus multipart/form-data overhead, so it only
# rejects genuinely oversized bodies while the per-upload limit stays intact.
DEFAULT_MAX_REQUEST_BODY_BYTES = 16 * 1024 * 1024


def _split_and_clean(raw: str) -> list[str]:
    """Split a comma-separated origin list and normalize each entry.

    Each entry is stripped of surrounding whitespace and any trailing slash so
    ``https://app.example.com/`` and ``https://app.example.com`` are treated as
    the same origin. Empty entries are dropped.
    """
    if not raw:
        return []
    return [
        part.strip().rstrip("/")
        for part in raw.split(",")
        if part.strip()
    ]


def _validate_origin(origin: str) -> None:
    """Reject CORS origins that are empty, use '*', or are not scheme://host.

    Origins carrying a path, query string, or fragment cannot be matched by the
    browser Origin header and are treated as configuration errors.
    """
    if not origin:
        raise ValueError("CORS_ORIGINS must not contain empty origins")
    if origin == "*":
        raise ValueError("CORS_ORIGINS must not contain the wildcard '*'")
    parsed = urlsplit(origin)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(
            f"Invalid CORS origin: {origin!r}. Expected scheme://host[:port]"
        )
    if parsed.path or parsed.query or parsed.fragment:
        raise ValueError(
            f"Invalid CORS origin: {origin!r}. Origins must not include a path, query, or fragment."
        )


def cors_origins_for(environment: str, cors_origins: str) -> list[str]:
    """Resolve the list of allowed CORS origins for a deployment.

    - Explicitly configured origins (comma-separated) are always used verbatim
      after normalization and validation.
    - Empty configuration falls back to the localhost development origins for
      development/test environments.
    - An empty configuration in a production-like environment raises so the
      application fails fast instead of silently shipping a permissive or
      wrong CORS policy.
    """
    explicit = _split_and_clean(cors_origins)
    if explicit:
        unique: list[str] = []
        for origin in explicit:
            _validate_origin(origin)
            if origin not in unique:
                unique.append(origin)
        return unique

    env = (environment or "development").strip().lower()
    if env in {"production", "prod", "staging"}:
        raise ValueError(
            "CORS_ORIGINS must be explicitly configured when ENVIRONMENT is "
            f"{environment!r}. Refusing to start with an unsafe CORS default."
        )
    return list(DEV_CORS_ORIGINS)


def _validate_trusted_host(host: str) -> None:
    """Reject clearly malformed TRUSTED_HOSTS entries.

    Host names are hostname patterns (optionally ``*.domain`` for wildcard
    subdomains). Ports are deliberately not part of the contract: Starlette's
    TrustedHostMiddleware strips the port from the Host header before
    matching, so ``host:port`` entries would silently never match.
    """
    if not host:
        raise ValueError("TRUSTED_HOSTS must not contain empty entries")
    if host == "*":
        raise ValueError(
            "TRUSTED_HOSTS must not be the wildcard '*'; list concrete hosts."
        )
    if "://" in host or "/" in host:
        raise ValueError(
            f"Invalid TRUSTED_HOSTS entry: {host!r}. Expected a hostname (no scheme or path)."
        )
    if any(ch.isspace() for ch in host):
        raise ValueError(
            f"Invalid TRUSTED_HOSTS entry: {host!r}. Hostnames must not contain whitespace."
        )


def trusted_hosts_for(environment: str, trusted_hosts: str) -> list[str]:
    """Resolve the allowed Host header values for a deployment.

    - Explicitly configured values (comma-separated, ``*.domain`` wildcards
      allowed) are always used after validation and de-duplication.
    - Empty configuration falls back to localhost development hosts for
      development/test environments.
    - Empty configuration in a production-like environment raises so the
      application fails fast instead of silently trusting any Host header.
    """
    explicit = _split_and_clean(trusted_hosts)
    if explicit:
        unique: list[str] = []
        for host in explicit:
            _validate_trusted_host(host)
            if host not in unique:
                unique.append(host)
        return unique

    env = (environment or "development").strip().lower()
    if env in {"production", "prod", "staging"}:
        raise ValueError(
            "TRUSTED_HOSTS must be explicitly configured when ENVIRONMENT is "
            f"{environment!r}. Refusing to trust an arbitrary Host header."
        )
    return list(DEV_TRUSTED_HOSTS)


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    CORS_ORIGINS: str = ""
    LOG_LEVEL: str = "INFO"
    STORAGE_ROOT: str = ""  # empty -> backend/uploads (project-local default)
    TRUSTED_HOSTS: str = ""  # empty -> localhost defaults (dev/test), error (prod)
    MAX_REQUEST_BODY_BYTES: int = DEFAULT_MAX_REQUEST_BODY_BYTES  # bytes (16 MiB)
    ENABLE_HSTS: bool = False  # only enable on HTTPS deployments

    # ── Rate limiting (Phase 5E.9) ──────────────────────────────────────────
    RATE_LIMIT_ENABLED: bool = True           # master switch (off in tests when needed)
    RATE_LIMIT_BACKEND: str = "memory"        # currently only "memory" is shipped
    RATE_LIMIT_WINDOW_SECONDS: int = 60       # fixed window length (seconds)
    RATE_LIMIT_AUTHENTICATED_MAX: int = 300   # per-user (Firebase UID), 5 req/s avg
    RATE_LIMIT_ANONYMOUS_MAX: int = 120       # per client IP, 2 req/s avg
    RATE_LIMIT_EXPENSIVE_MAX: int = 30        # per-user for AI/discovery/upload
    RATE_LIMIT_MAX_KEYS: int = 20_000         # memory backend cap
    RATE_LIMIT_TRUST_PROXY: bool = False      # unused until proxy-header parsing added

    DATABASE_URL: str = "postgresql://user:password@localhost:5432/careerpilot"

    # ── Backup & recovery (Phase 5E.11) ─────────────────────────────────────
    # Directory that stores pg_dump archives and their SHA-256 sidecars.
    # Empty -> the project-local default backend/backups. Production deployments
    # must point BACKUP_DIR at a dedicated volume that is itself backed up
    # off-host (see backend/docs/backup_recovery.md).
    BACKUP_DIR: str = ""
    # Number of newest valid backups to retain. Older archives are pruned by
    # `python -m app.ops.backup cleanup`. Must be >= 1.
    BACKUP_RETENTION_COUNT: int = 30

    FIREBASE_PROJECT_ID: str = ""
    ADZUNA_APP_ID: str = ""
    ADZUNA_APP_KEY: str = ""
    ADZUNA_COUNTRY: str = "us"
    ADZUNA_TIMEOUT_SECONDS: float = 20.0
    JOBICY_TIMEOUT_SECONDS: float = 20.0
    JOOBLE_API_KEY: str = ""
    JOOBLE_TIMEOUT_SECONDS: float = 20.0

    # AI resume tailoring (Phase 3A). Optional - the application must fail
    # gracefully when these are not configured.
    AI_PROVIDER: str = ""            # e.g. "openai"
    AI_API_KEY: str = ""             # never hardcoded, read from env
    AI_MODEL: str = ""               # e.g. "gpt-4o-mini"
    AI_BASE_URL: str = ""            # optional custom OpenAI-compatible endpoint (e.g. OpenRouter)
    AI_TIMEOUT_SECONDS: float = 60.0

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def allowed_cors_origins(self) -> list[str]:
        """Resolved CORS allowlist for this deployment. Raises on unsafe config."""
        return cors_origins_for(self.ENVIRONMENT, self.CORS_ORIGINS)

    @property
    def allowed_trusted_hosts(self) -> list[str]:
        """Resolved TrustedHost allowlist. Raises on unsafe/empty prod config."""
        return trusted_hosts_for(self.ENVIRONMENT, self.TRUSTED_HOSTS)

    @property
    def hsts_enabled(self) -> bool:
        """Whether to emit Strict-Transport-Security.

        HSTS is off by default and in non-production environments. In
        production/staging it must be explicitly opted in (ENABLE_HSTS=true)
        rather than silently assumed - this keeps it off on plain HTTP while
        allowing an explicit HTTPS deployment to set it on.
        """
        if self.ENABLE_HSTS:
            return True
        env = (self.ENVIRONMENT or "development").strip().lower()
        return False

    @property
    def rate_limit_config(self) -> dict:
        """Sanitized rate-limit configuration. Raises on invalid values.

        Returns a plain dict so callers (middleware, dependencies) don't need to
        import Settings. Production deployments using the memory backend receive
        a logged warning (not a hard failure) so a beta single-instance prod
        deploy is not blocked while remaining honest about multi-instance limits.
        """
        backend = (self.RATE_LIMIT_BACKEND or "memory").strip().lower()
        allowed_backends = {"memory"}
        if backend not in allowed_backends:
            raise ValueError(
                f"RATE_LIMIT_BACKEND={backend!r} is not supported; "
                f"choose from {sorted(allowed_backends)}"
            )

        window = max(1, self.RATE_LIMIT_WINDOW_SECONDS)
        auth_max = max(1, self.RATE_LIMIT_AUTHENTICATED_MAX)
        anon_max = max(1, self.RATE_LIMIT_ANONYMOUS_MAX)
        exp_max = max(1, self.RATE_LIMIT_EXPENSIVE_MAX)
        max_keys = max(1000, self.RATE_LIMIT_MAX_KEYS)

        env = (self.ENVIRONMENT or "development").strip().lower()
        if env in {"production", "prod", "staging"} and self.RATE_LIMIT_ENABLED:
            logger.warning(
                "RATE_LIMIT_BACKEND='memory' is single-instance only; "
                "a shared backend (Redis, etc.) is needed for true distributed "
                "rate limiting in multi-instance production deployments."
            )

        return {
            "enabled": bool(self.RATE_LIMIT_ENABLED),
            "backend": backend,
            "window_seconds": window,
            "authenticated_max": auth_max,
            "anonymous_max": anon_max,
            "expensive_max": exp_max,
            "max_keys": max_keys,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()