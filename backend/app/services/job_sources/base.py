from abc import ABC, abstractmethod


class SourceUnavailableError(Exception):
    """Raised when a job source could not be reached (timeout, HTTP error, etc.).

    Carries a user-safe, non-sensitive message. Detailed reasons are logged
    separately and must never be propagated to end users.
    """

    def __init__(self, message: str, *args: object):
        super().__init__(message, *args)


def describe_status(status_code: int) -> str:
    """Maps an HTTP status to a generic, user-safe description."""
    if status_code == 429:
        return "rate limited"
    if status_code in (401, 403):
        return "access denied"
    if status_code >= 500:
        return "temporarily unavailable"
    return f"returned status {status_code}"


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


class BaseJobSource(ABC):
    """Abstract base class for job source adapters."""

    name: str = "unknown"

    @abstractmethod
    def fetch(self, queries: list[str], locations: list[str] | None = None) -> list[NormalizedJob]:
        """Fetch jobs from the external source using the given search queries.

        Args:
            queries: List of search terms derived from user profile.
            locations: Optional list of preferred locations.

        Returns:
            List of NormalizedJob instances.
        """
        ...
