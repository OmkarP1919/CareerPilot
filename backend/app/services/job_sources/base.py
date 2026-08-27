from abc import ABC, abstractmethod


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
