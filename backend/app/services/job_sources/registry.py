"""Central provider registry for job sources.

Provides a simple factory that returns all enabled providers based on
configuration. The orchestrator iterates over the list returned by
``get_providers()`` without knowing which concrete classes are involved.
"""
from __future__ import annotations

import logging
from typing import Sequence

from app.services.job_sources.base import BaseJobSource
from app.core.config import get_settings

logger = logging.getLogger(__name__)


def get_providers() -> list[BaseJobSource]:
    """Return an ordered list of enabled provider instances.

    A provider is enabled when its required credentials are present in the
    environment. Providers that are not configured are silently skipped so
    that the orchestrator can still run with fewer sources.
    """
    settings = get_settings()
    providers: list[BaseJobSource] = []

    # Adzuna — requires APP_ID + APP_KEY
    if settings.ADZUNA_APP_ID and settings.ADZUNA_APP_KEY:
        from app.services.job_sources.adzuna import AdzunaSource
        providers.append(AdzunaSource())
    else:
        logger.debug("Adzuna provider disabled (credentials not configured)")

    # Jobicy — no API key required (public API)
    from app.services.job_sources.jobicy import JobicySource
    providers.append(JobicySource())

    # Jooble — requires API key
    if settings.JOOBLE_API_KEY:
        from app.services.job_sources.jooble import JoobleSource
        providers.append(JoobleSource())
    else:
        logger.debug("Jooble provider disabled (API key not configured)")

    return providers


def get_all_provider_names() -> list[str]:
    """Return names of all known providers (enabled or not)."""
    return ["Adzuna", "Jobicy", "Jooble"]
