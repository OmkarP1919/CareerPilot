import json
import logging
import re
from datetime import datetime, timezone
import httpx
from app.services.job_sources.base import (
    BaseJobSource,
    NormalizedJob,
    ProviderCapabilities,
    SourceUnavailableError,
    describe_status,
)
from app.core.config import get_settings

logger = logging.getLogger(__name__)

JOOBLE_BASE_URL = "https://jooble.org/api"
RESULTS_PER_PAGE = 10


def _parse_salary(raw_salary: str | None) -> tuple[int | None, int | None, str | None]:
    """Parse Jooble salary string like '17,600 UAH' into (min, max, currency)."""
    if not raw_salary:
        return None, None, None
    cleaned = raw_salary.strip()
    # Extract trailing currency code (3 uppercase letters)
    currency_match = re.search(r"\s+([A-Z]{3})\s*$", cleaned)
    currency = currency_match.group(1) if currency_match else None
    # Remove currency suffix
    amount_part = cleaned[:currency_match.start()] if currency_match else cleaned
    # Remove commas and whitespace
    amount_part = re.sub(r"[,\s]", "", amount_part)
    # Handle ranges: "17600 - 25000" or single "17600"
    range_match = re.match(r"(\d+)\s*-\s*(\d+)", amount_part)
    if range_match:
        return int(range_match.group(1)), int(range_match.group(2)), currency
    single_match = re.match(r"(\d+)", amount_part)
    if single_match:
        val = int(single_match.group(1))
        return val, val, currency
    return None, None, None


class JoobleSource(BaseJobSource):
    name = "Jooble"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_location=True,
            supports_radius=True,
            supports_salary=True,
            supports_pagination=True,
            supports_job_type=True,
            supports_posted_date=True,
        )

    @property
    def is_enabled(self) -> bool:
        settings = get_settings()
        return bool(settings.JOOBLE_API_KEY)

    def fetch(
        self,
        queries: list[str],
        locations: list[str] | None = None,
        **kwargs,
    ) -> list[NormalizedJob]:
        settings = get_settings()
        api_key = settings.JOOBLE_API_KEY
        timeout = settings.JOOBLE_TIMEOUT_SECONDS

        if not api_key:
            logger.warning("Jooble API key not configured, skipping")
            return []

        jobs: list[NormalizedJob] = []
        source_errors: list[str] = []
        primary_location = locations[0] if locations else ""

        for query in queries[:2]:
            try:
                fetched = self._search(api_key, query, primary_location, timeout)
                jobs.extend(fetched)
            except httpx.HTTPStatusError as e:
                status_desc = describe_status(e.response.status_code)
                source_errors.append(status_desc)
                logger.warning(
                    "Jooble HTTP error %s for query='%s': %s",
                    e.response.status_code, query, status_desc,
                )
            except (httpx.TimeoutException, httpx.TransportError):
                source_errors.append("timed out")
                logger.warning(
                    "Jooble request timed out for query='%s'",
                    query,
                )
            except SourceUnavailableError:
                source_errors.append("invalid response")
                logger.warning("Jooble returned an invalid response for query='%s'", query)
            except Exception:
                source_errors.append("unexpected error")
                logger.exception("Jooble search failed for query='%s'", query)

        if not jobs and source_errors:
            raise SourceUnavailableError(
                f"Jooble was temporarily unavailable ({'; '.join(dict.fromkeys(source_errors))})."
            )

        return jobs

    def _search(
        self, api_key: str, keywords: str, location: str, timeout: float
    ) -> list[NormalizedJob]:
        url = f"{JOOBLE_BASE_URL}/{api_key}"
        payload = {
            "keywords": keywords,
            "location": location or "",
        }

        response = httpx.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=timeout,
        )
        response.raise_for_status()

        try:
            data = response.json()
        except json.JSONDecodeError:
            logger.warning("Jooble returned malformed JSON for keywords='%s'", keywords)
            raise SourceUnavailableError("Jooble returned an invalid response.")

        raw_jobs = data.get("jobs", [])
        if not isinstance(raw_jobs, list):
            return []

        jobs = []
        for item in raw_jobs:
            if not isinstance(item, dict):
                continue

            salary_min, salary_max, salary_currency = _parse_salary(item.get("salary"))

            employment_type = item.get("type")
            if employment_type:
                employment_type = employment_type.strip()

            posted_at = item.get("updated")
            if posted_at:
                try:
                    posted_at = datetime.fromisoformat(
                        posted_at.replace("Z", "+00:00")
                    ).isoformat()
                except (ValueError, AttributeError):
                    posted_at = None

            snippet = item.get("snippet", "")
            description = snippet if snippet else None

            jobs.append(NormalizedJob(
                external_id=str(item.get("id", "")),
                title=(item.get("title") or "").strip(),
                company=(item.get("company") or "").strip(),
                location=(item.get("location") or None),
                description=description,
                employment_type=employment_type,
                application_url=item.get("link", ""),
                source=self.name,
                posted_at=posted_at,
                source_url=item.get("link", ""),
                salary_min=salary_min,
                salary_max=salary_max,
                salary_currency=salary_currency,
                raw_data=item,
            ))

        return jobs
