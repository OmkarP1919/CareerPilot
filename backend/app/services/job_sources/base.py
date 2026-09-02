from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Source status
# ---------------------------------------------------------------------------

class SourceStatus(str, enum.Enum):
    SUCCESS = "success"
    UNAVAILABLE = "unavailable"
    RATE_LIMITED = "rate_limited"
    UNAUTHORIZED = "unauthorized"
    TIMEOUT = "timeout"
    MALFORMED_RESPONSE = "malformed_response"
    DISABLED = "disabled"


# ---------------------------------------------------------------------------
# SourceUnavailableError  (backward-compatible)
# ---------------------------------------------------------------------------

class SourceUnavailableError(Exception):
    """Raised when a job source could not be reached (timeout, HTTP error, etc.).

    Carries a user-safe, non-sensitive message. Detailed reasons are logged
    separately and must never be propagated to end users.
    """

    def __init__(self, message: str, *args: object):
        super().__init__(message, *args)


# ---------------------------------------------------------------------------
# describe_status  (backward-compatible)
# ---------------------------------------------------------------------------

def describe_status(status_code: int) -> str:
    """Maps an HTTP status to a generic, user-safe description."""
    if status_code == 429:
        return "rate limited"
    if status_code in (401, 403):
        return "access denied"
    if status_code >= 500:
        return "temporarily unavailable"
    return f"returned status {status_code}"


# ---------------------------------------------------------------------------
# SearchCriteria
# ---------------------------------------------------------------------------

@dataclass
class SearchCriteria:
    """Internal representation of search parameters for a provider."""

    queries: list[str]
    locations: list[str] | None = None
    country: str | None = None
    radius: str | None = None
    remote: bool | None = None
    employment_type: str | None = None
    experience_level: str | None = None
    posted_after: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    page: int = 1
    page_size: int = 10
    sort: str | None = None


# ---------------------------------------------------------------------------
# ProviderCapabilities
# ---------------------------------------------------------------------------

@dataclass
class ProviderCapabilities:
    """Declares what search filters a provider actually supports."""

    supports_location: bool = False
    supports_radius: bool = False
    supports_salary: bool = False
    supports_remote: bool = False
    supports_job_type: bool = False
    supports_experience_level: bool = False
    supports_posted_date: bool = False
    supports_sort: bool = False
    supports_pagination: bool = False


# ---------------------------------------------------------------------------
# SourceResult
# ---------------------------------------------------------------------------

@dataclass
class SourceResult:
    """Aggregated result from a single provider call."""

    source: str
    status: SourceStatus
    jobs: list[NormalizedJob] = field(default_factory=list)
    error_message: str | None = None
    total_count: int | None = None


# ---------------------------------------------------------------------------
# NormalizedJob  (backward-compatible, extended)
# ---------------------------------------------------------------------------

class NormalizedJob:
    """Common job structure returned by all source adapters."""

    def __init__(
        self,
        external_id: str,
        title: str,
        company: str,
        location: str | None = None,
        description: str | None = None,
        employment_type: str | None = None,
        experience_level: str | None = None,
        application_url: str | None = None,
        source: str = "",
        posted_at: str | None = None,
        raw_data: dict | None = None,
        # --- Phase 5A extensions (optional) ---
        country: str | None = None,
        city: str | None = None,
        remote: bool | None = None,
        salary_min: int | None = None,
        salary_max: int | None = None,
        salary_currency: str | None = None,
        updated_at: str | None = None,
        source_url: str | None = None,
        category: str | None = None,
        skills: list[str] | None = None,
    ):
        self.external_id = external_id
        self.title = title
        self.company = company
        self.location = location
        self.description = description
        self.employment_type = employment_type
        self.experience_level = experience_level
        self.application_url = application_url
        self.source = source
        self.posted_at = posted_at
        self.raw_data = raw_data or {}
        # Phase 5A extensions
        self.country = country
        self.city = city
        self.remote = remote
        self.salary_min = salary_min
        self.salary_max = salary_max
        self.salary_currency = salary_currency
        self.updated_at = updated_at
        self.source_url = source_url
        self.category = category
        self.skills = skills


# ---------------------------------------------------------------------------
# BaseJobSource
# ---------------------------------------------------------------------------

class BaseJobSource(ABC):
    """Abstract base class for job source adapters."""

    name: str = "unknown"

    @abstractmethod
    def fetch(
        self,
        queries: list[str],
        locations: list[str] | None = None,
        **kwargs: Any,
    ) -> list[NormalizedJob]:
        """Fetch jobs from the external source using the given search queries.

        Args:
            queries: List of search terms derived from user profile.
            locations: Optional list of preferred locations.
            **kwargs: Provider-specific extra arguments (e.g. country).

        Returns:
            List of NormalizedJob instances.
        """
        ...

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Return the capabilities of this provider. Override in subclasses."""
        return ProviderCapabilities()

    @property
    def is_enabled(self) -> bool:
        """Whether this provider can currently be queried.

        Subclasses that require credentials should override this so the
        orchestrator can report a clean ``disabled`` status without attempting
        a network call.
        """
        return True

    def to_source_result(
        self,
        jobs: list[NormalizedJob],
        status: SourceStatus = SourceStatus.SUCCESS,
        error_message: str | None = None,
        total_count: int | None = None,
    ) -> SourceResult:
        """Convenience: wrap a job list into a SourceResult."""
        return SourceResult(
            source=self.name,
            status=status,
            jobs=jobs,
            error_message=error_message,
            total_count=total_count,
        )
