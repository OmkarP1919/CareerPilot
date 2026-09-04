"""Canonical contracts for the multi-source job discovery architecture.

This module defines the provider-neutral contracts shared by all job source
adapters, the orchestrator and the registry:

- :class:`SourceStatus`       - per-source outcome classification.
- :class:`SearchCriteria`     - the canonical internal search request that is
                                passed, as a single object, to every provider.
- :class:`ProviderCapabilities` - what filters a provider *actually* applies.
- :class:`SourceResult`       - aggregated per-source outcome.
- :class:`NormalizedJob`      - canonical normalized job record.
- :class:`BaseJobSource`      - provider interface.
- :class:`SourceUnavailableError` / :func:`describe_status` - error helpers.

Design rules:

* ``SearchCriteria`` is the ONLY thing a provider reads to build its request.
  Providers must not receive loose provider-specific ``**kwargs``.
* ``ProviderCapabilities`` must reflect what the adapter genuinely applies
  today, not what the upstream API documentation claims to support.
* Error messages returned to end users must be generic and sanitized (no API
  keys, raw response bodies, credentials, stack traces or PII).
"""
from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


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
    """Canonical, provider-neutral search request.

    This object is the single contract passed to every provider's ``fetch``.
    It intentionally references the union of filter dimensions that the future
    CareerPilot discovery system cares about. Providers apply ONLY the fields
    they genuinely support (see :class:`ProviderCapabilities`) and ignore the
    rest; unsupported filters are surfaced for application-layer filtering
    rather than silently applied upstream.

    Field semantics:
    * queries          - list of free-text keywords / role terms to search.
    * locations        - list of location / city terms.
    * country          - ISO 3166-1 alpha-2 country code, when known.
    * radius           - search radius, provider-specific unit (e.g. "20km").
    * remote           - restrict to remote roles (True/False).
    * employment_type  - e.g. "Full-time", "Part-time", "Contract".
    * experience_level - e.g. "entry", "mid", "senior" (provider-dependent).
    * internship_only  - True => keep internships only, False => exclude
                         internships, None => no internship constraint.
    * posted_after     - ISO-8601 bound: only jobs posted at/after this time.
     * salary_min       - minimum salary amount.
     * salary_max       - maximum salary amount.
     * salary_period    - optional canonical pay period ("annual"/"monthly"/
                         "weekly"/"daily"/"hourly"). When set, salary filters
                         apply ONLY to jobs declaring the SAME period; jobs
                         with a different or unknown period are not compared
                         (never auto-converted). When None, legacy numeric
                         fallback applies.
     * salary_currency  - optional ISO 4217 currency code. When set, only jobs
                         declaring that exact currency are salary-compared
                         (never converted). When None, no currency gate.
     * page / page_size - pagination (1-based page, page size).
     * sort             - ordering hint (provider-specific).
     * categories       - list of category / sector terms.
     * skills           - list of required skill keywords.
     * skills_match     - skill filter match mode: "any" (job containing at
                         least one requested skill) or "all" (job containing
                         every requested skill). Defaults to "any".
    """

    queries: list[str]
    locations: list[str] | None = None
    country: str | None = None
    radius: str | None = None
    remote: bool | None = None
    employment_type: str | None = None
    experience_level: str | None = None
    internship_only: bool | None = None
    posted_after: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_period: str | None = None
    salary_currency: str | None = None
    page: int = 1
    page_size: int = 10
    sort: str | None = None
    categories: list[str] | None = None
    skills: list[str] | None = None
    skills_match: str = "any"


# ---------------------------------------------------------------------------
# ProviderCapabilities
# ---------------------------------------------------------------------------

@dataclass
class ProviderCapabilities:
    """Declares which filter dimensions a provider's adapter ACTUALLY applies.

    A capability is ``True`` only when the corresponding ``SearchCriteria``
    field is genuinely passed/used by the provider's current request code —
    NOT merely because the upstream API documentation mentions it. This is the
    metadata the future application-layer filter engine uses to decide which
    filters must be applied CareerPilot-side after a provider returns jobs.
    """

    supports_location: bool = False
    supports_radius: bool = False
    supports_salary: bool = False
    supports_remote: bool = False
    supports_job_type: bool = False
    supports_experience_level: bool = False
    supports_posted_date: bool = False
    supports_sort: bool = False
    supports_pagination: bool = False
    supports_categories: bool = False
    supports_skills: bool = False


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
    """Common job structure returned by all source adapters.

    Field semantics (used by future deduplication, freshness and ranking):

    * external_id      - provider's own stable job identifier (may differ
                         across providers for the same underlying listing).
    * title / company  - human-readable title and employer name.
    * location         - free-text location as returned by the source.
    * city / country   - structured city and ISO country code, when derivable
                         from the source WITHOUT aggressive inference; else None.
    * description      - job description text (may be truncated by source).
    * employment_type  - normalized job type, e.g. "Full-time".
    * experience_level - provider-supplied seniority level, else None.
    * application_url  - URL used to apply (career site target).
    * source_url       - canonical listing URL on the provider.
    * source           - provider name (e.g. "Adzuna").
    * remote           - True/False/None when the source states remote status.
    * work_mode        - canonical work-mode classification, when it can be
                         reliably determined from provider data:
                         "remote", "hybrid", "onsite", or "unspecified".
                         This is an additive, backward-compatible field; the
                         legacy boolean ``remote`` is retained and NOT changed.
                         ``unspecified`` means the mode could not be determined
                         with confidence (equivalent to ``remote=None``).
    * salary_min/max   - numeric salary bounds as reported (currency in
                         salary_currency); None when the source gives none.
    * salary_currency  - ISO 4217 currency code for salary_min/max (or None).
    * salary_period    - canonical pay period for salary_min/max: one of
                         "annual", "monthly", "weekly", "daily", "hourly",
                         or "unknown" when the source gives no period. Never
                         auto-converted; comparisons across incompatible
                         periods are refused, not converted.
    * posted_at        - when the source says the job was POSTED (ISO-8601).
                         Never substitute fetched_at here.
    * updated_at       - when the source says the listing was UPDATED (ISO-8601).
                         None when the source provides no distinct update time.
    * category         - provider category / sector label (or None).
    * skills           - provider-supplied skill tags (or None).
    * raw_data         - un-parsed source payload retained for debugging.
    """

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
        # --- Phase 5A/5A.1 extensions (optional, defaults to None) ---
        country: str | None = None,
        city: str | None = None,
        remote: bool | None = None,
        work_mode: str | None = None,
        salary_min: int | None = None,
        salary_max: int | None = None,
        salary_currency: str | None = None,
        salary_period: str | None = None,
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
        # Phase 5A/5A.1 extensions
        self.country = country
        self.city = city
        self.remote = remote
        self.work_mode = work_mode
        self.salary_min = salary_min
        self.salary_max = salary_max
        self.salary_currency = salary_currency
        self.salary_period = salary_period
        self.updated_at = updated_at
        self.source_url = source_url
        self.category = category
        self.skills = skills


# ---------------------------------------------------------------------------
# BaseJobSource
# ---------------------------------------------------------------------------

class BaseJobSource(ABC):
    """Abstract base class for job source adapters.

    A provider is responsible ONLY for:
    1. reading a :class:`SearchCriteria`,
    2. applying the criteria it genuinely supports (per its capabilities),
    3. returning a list of :class:`NormalizedJob`.
    It must NOT be aware of the orchestrator or other providers, and it must
    bound every outbound request with a timeout.
    """

    name: str = "unknown"

    @abstractmethod
    def fetch(self, criteria: SearchCriteria) -> list[NormalizedJob]:
        """Fetch jobs for the given canonical search criteria.

        Args:
            criteria: The canonical search contract. A provider applies only
                the fields it supports (see ``capabilities``) and ignores the
                rest safely.

        Returns:
            List of NormalizedJob instances describing the matched jobs.
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
