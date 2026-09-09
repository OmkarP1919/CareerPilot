from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.profile import router as profile_router
from app.api.resumes import router as resumes_router
from app.api.jobs import router as jobs_router
from app.api.discovery import router as discovery_router
from app.api.match import router as match_router
from app.api.resume_analysis import router as resume_analysis_router
from app.api.resume_tailoring import router as resume_tailoring_router
from app.api.resume_tailoring import tailored_list_router
from app.api.resume_export import router as resume_export_router
from app.api.cover_letter import router as cover_letter_router
from app.api.cover_letter import collection_router as cover_letter_collection_router
from app.api.applications import router as applications_router
from app.api.analytics import router as analytics_router
from app.core.config import get_settings
from app.core.logging_config import setup_logging
from app.core.request_middleware import RequestLoggingMiddleware
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.body_limit import RequestBodyLimitMiddleware
from app.core.rate_limit_middleware import RateLimitMiddleware
from app.core.proxy_headers import ProxyHeadersMiddleware
from app.core.rate_limit_deps import configure_rate_limits

# Initialize application logging early so startup failures are diagnosable.
_settings = get_settings()
setup_logging(_settings.LOG_LEVEL)

# Schema initialization is an explicit release operation (python -m app.database.init),
# NOT an import-time side effect. Application startup assumes the schema exists.
#
# Both allowed_cors_origins and allowed_trusted_hosts raise at import time in
# a production-like environment when their respective variable is empty, so an
# unsafe configuration fails fast at startup instead of silently shipping.

_origins = _settings.allowed_cors_origins
_trusted_hosts = _settings.allowed_trusted_hosts
_hsts = _settings.hsts_enabled
_max_body_bytes = _settings.MAX_REQUEST_BODY_BYTES
_rate_limit = _settings.rate_limit_config

app = FastAPI(
    title="CareerPilot AI",
    description="Intelligent Job Matching & Application Management Platform",
    version="1.0.0",
)

# Middleware order (outermost -> innermost); add_middleware prepends, so these
# are registered in reverse order:
#
#   1. CORS                   - unchanged 5E.1 behavior, outermost
#   2. SecurityHeaders        - security headers on normal AND rejected responses
#   3. ProxyHeaders           - trust X-Forwarded-Proto from configured proxy IPs
#   4. RequestLogging         - request ID + log every non-health request
#   5. TrustedHost            - reject unknown Host headers before routing
#   6. RateLimit              - global anonymous/client-IP 429s BEFORE routing
#   7. RequestBodyLimit       - reject oversized bodies before handlers consume
#   8. application router
#
# RateLimit sits inside TrustedHost (bad Host rejected first, so rejected hosts
# do not consume counters) and outside RequestBodyLimit (so a 429 response gets
# the request-ID + security-header envelope from the outer middlewares).
#
# ProxyHeaders runs before RequestLogging so the logged scheme is correct, and
# before TrustedHost so any downstream middleware sees the original scheme.
app.add_middleware(RequestBodyLimitMiddleware, max_bytes=_max_body_bytes)
app.add_middleware(RateLimitMiddleware,
                   enabled=_rate_limit["enabled"],
                   anonymous_max=_rate_limit["anonymous_max"],
                   window_seconds=_rate_limit["window_seconds"],
                   max_keys=_rate_limit["max_keys"])
app.add_middleware(TrustedHostMiddleware, allowed_hosts=_trusted_hosts)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(ProxyHeadersMiddleware, allowed_ips=_settings.allowed_forwarded_ips)
app.add_middleware(SecurityHeadersMiddleware, hsts_enabled=_hsts)
app.add_middleware(CORSMiddleware,
                   allow_origins=_origins,
                   allow_credentials=True,
                   allow_methods=["*"],
                   allow_headers=["*"])

# Configure the per-user (authenticated / expensive) rate-limit dependencies.
configure_rate_limits(
    enabled=_rate_limit["enabled"],
    window_seconds=_rate_limit["window_seconds"],
    authenticated_max=_rate_limit["authenticated_max"],
    expensive_max=_rate_limit["expensive_max"],
    max_keys=_rate_limit["max_keys"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(resumes_router)
app.include_router(jobs_router)
app.include_router(discovery_router)
app.include_router(match_router)
app.include_router(resume_analysis_router)
app.include_router(resume_tailoring_router)
app.include_router(tailored_list_router)
app.include_router(resume_export_router)
app.include_router(cover_letter_router)
app.include_router(cover_letter_collection_router)
app.include_router(applications_router)
app.include_router(analytics_router)


@app.get("/")
def root():
    return {"message": "CareerPilot AI API"}
