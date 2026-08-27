import logging
import re
import httpx
from app.services.job_sources.base import BaseJobSource, NormalizedJob

logger = logging.getLogger(__name__)

JOBICY_BASE_URL = "https://jobicy.com/api/v2/remote-jobs"
REQUEST_TIMEOUT = 5
MAX_PER_QUERY = 15


def strip_html(text: str) -> str:
    """Remove HTML tags from a string."""
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"\s+", " ", clean)
    return clean.strip()


class JobicySource(BaseJobSource):
    name = "Jobicy"

    def fetch(self, queries: list[str], locations: list[str] | None = None) -> list[NormalizedJob]:
        jobs: list[NormalizedJob] = []

        for query in queries[:2]:
            try:
                fetched = self._search(query)
                jobs.extend(fetched)
            except Exception:
                logger.exception(f"Jobicy search failed for query='{query}'")

        return jobs

    def _search(self, tag: str) -> list[NormalizedJob]:
        params = {
            "count": MAX_PER_QUERY,
            "tag": tag[:50],
        }

        response = httpx.get(JOBICY_BASE_URL, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()

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
