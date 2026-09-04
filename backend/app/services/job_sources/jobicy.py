import json
import logging
import re
import httpx
from app.services.job_sources.base import (
    BaseJobSource,
    NormalizedJob,
    ProviderCapabilities,
    SearchCriteria,
    SourceUnavailableError,
    describe_status,
)
from app.core.config import get_settings

logger = logging.getLogger(__name__)

JOBICY_BASE_URL = "https://jobicy.com/api/v2/remote-jobs"
MAX_PER_QUERY = 15


def strip_html(text: str) -> str:
    """Remove HTML tags from a string."""
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"\s+", " ", clean)
    return clean.strip()


class JobicySource(BaseJobSource):
    name = "Jobicy"

    @property
    def capabilities(self) -> ProviderCapabilities:
        # The current adapter only sends `count` and `tag` (keyword). It does
        # NOT pass location, remote, job type, experience, posted-date, salary
        # or pagination criteria upstream, so all filter capabilities are
        # reported as unsupported. (Jobicy returns remote-style listings, but
        # the adapter never requests a `remote` criterion explicitly.)
        return ProviderCapabilities()

    def fetch(self, criteria: SearchCriteria) -> list[NormalizedJob]:
        timeout = get_settings().JOBICY_TIMEOUT_SECONDS
        jobs: list[NormalizedJob] = []
        source_errors: list[str] = []

        for query in criteria.queries[:2]:
            try:
                fetched = self._search(query, timeout)
                jobs.extend(fetched)
            except (httpx.TimeoutException, httpx.TransportError):
                source_errors.append("timed out")
                logger.warning("Jobicy request failed for query='%s': %s", query, "transport error")
            except httpx.HTTPStatusError as e:
                source_errors.append(describe_status(e.response.status_code))
                logger.warning("Jobicy HTTP error %s for query='%s'", e.response.status_code, query)
            except SourceUnavailableError:
                source_errors.append("invalid response")
                logger.warning("Jobicy returned an invalid response for query='%s'", query)
            except Exception:
                source_errors.append("unexpected error")
                logger.exception("Jobicy search failed for query='%s'", query)

        if not jobs and source_errors:
            raise SourceUnavailableError(
                f"Jobicy was temporarily unavailable ({'; '.join(dict.fromkeys(source_errors))})."
            )

        return jobs

    def _search(self, tag: str, timeout: float) -> list[NormalizedJob]:
        params = {
            "count": MAX_PER_QUERY,
            "tag": tag[:50],
        }

        response = httpx.get(JOBICY_BASE_URL, params=params, timeout=timeout)
        response.raise_for_status()
        try:
            data = response.json()
        except json.JSONDecodeError:
            logger.warning("Jobicy returned malformed JSON for query='%s'", tag)
            raise SourceUnavailableError("Jobicy returned an invalid response.")

        if not data.get("success"):
            return []

        raw_jobs = data.get("jobs", [])
        jobs = []

        for item in raw_jobs:
            job_types = item.get("jobType", [])
            employment_type = job_types[0] if job_types else None
            if employment_type:
                employment_type = employment_type.replace("-", " ").title()

            level = item.get("jobLevel", None)
            if level:
                level = level.strip()

            posted = item.get("pubDate")
            posted_at = posted if posted else None

            description = strip_html(item.get("jobDescription", ""))

            jobs.append(NormalizedJob(
                external_id=str(item.get("id", "")),
                title=item.get("jobTitle", "").strip(),
                company=item.get("companyName", "").strip(),
                location=item.get("jobGeo", None),
                description=description,
                employment_type=employment_type,
                experience_level=level,
                application_url=item.get("url", ""),
                source=self.name,
                posted_at=posted_at,
                raw_data=item,
            ))

        return jobs
