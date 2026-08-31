import json
import logging
import httpx
from datetime import datetime, timezone
from app.services.job_sources.base import (
    BaseJobSource,
    NormalizedJob,
    SourceUnavailableError,
    describe_status,
)
from app.core.config import get_settings

logger = logging.getLogger(__name__)

ADZUNA_BASE_URL = "https://api.adzuna.com/v1/api/jobs"
RESULTS_PER_PAGE = 10


ADZUNA_SUPPORTED_COUNTRIES = {
    "gb", "us", "at", "au", "be", "br", "ca", "ch", "de", "es",
    "fr", "it", "mx", "nl", "nz", "pl", "ru", "sg", "za",
}


class AdzunaSource(BaseJobSource):
    name = "Adzuna"

    def fetch(
        self,
        queries: list[str],
        locations: list[str] | None = None,
        country: str | None = None,
    ) -> list[NormalizedJob]:
        settings = get_settings()
        app_id = settings.ADZUNA_APP_ID
        app_key = settings.ADZUNA_APP_KEY
        timeout = settings.ADZUNA_TIMEOUT_SECONDS
        target_country = (country or settings.ADZUNA_COUNTRY or "us").lower()
        if target_country not in ADZUNA_SUPPORTED_COUNTRIES:
            target_country = settings.ADZUNA_COUNTRY or "us"

        if not app_id or not app_key:
            logger.warning("Adzuna API credentials not configured, skipping")
            return []

        jobs: list[NormalizedJob] = []
        source_errors: list[str] = []
        primary_location = locations[0] if locations else None

        for query in queries[:2]:
            try:
                fetched = self._search(app_id, app_key, target_country, query, primary_location, timeout)
                jobs.extend(fetched)
            except httpx.HTTPStatusError as e:
                source_errors.append(describe_status(e.response.status_code))
                logger.warning(
                    "Adzuna HTTP error %s for country='%s', query='%s'",
                    e.response.status_code, target_country, query,
                )
                if target_country != "us":
                    target_country = "us"
                    try:
                        fetched = self._search(app_id, app_key, "us", query, None, timeout)
                        jobs.extend(fetched)
                    except Exception:
                        logger.warning("Adzuna US fallback failed for query='%s'", query)
                else:
                    logger.warning("Adzuna search failed for query='%s' in country='%s'", query, target_country)
            except (httpx.TimeoutException, httpx.TransportError) as e:
                source_errors.append("timed out")
                logger.warning(
                    "Adzuna request failed for query='%s' in country='%s': %s",
                    query, target_country, type(e).__name__,
                )
            except Exception as e:
                source_errors.append("unexpected error")
                logger.exception("Adzuna search failed for query='%s' in country='%s'", query, target_country)

        if not jobs and source_errors:
            raise SourceUnavailableError(
                f"Adzuna was temporarily unavailable ({'; '.join(dict.fromkeys(source_errors))})."
            )

        return jobs

    def _search(
        self, app_id: str, app_key: str, country: str, what: str, where: str | None, timeout: float
    ) -> list[NormalizedJob]:
        url = f"{ADZUNA_BASE_URL}/{country}/search/1"
        params = {
            "app_id": app_id,
            "app_key": app_key,
            "results_per_page": RESULTS_PER_PAGE,
            "what": what,
            "content-type": "application/json",
        }
        if where:
            params["where"] = where

        response = httpx.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        try:
            data = response.json()
        except json.JSONDecodeError:
            logger.warning("Adzuna returned malformed JSON for query='%s'", what)
            raise SourceUnavailableError("Adzuna returned an invalid response.")

        results = data.get("results", [])
        jobs = []
        for item in results:
            company_data = item.get("company", {})
            location_data = item.get("location", {})

            posted = item.get("created")
            posted_at = None
            if posted:
                try:
                    posted_at = datetime.fromisoformat(posted.replace("Z", "+00:00")).isoformat()
                except (ValueError, AttributeError):
                    pass

            contract = item.get("contract_type", "")
            employment_type = None
            if contract == "permanent":
                employment_type = "Full-time"
            elif contract == "contract":
                employment_type = "Contract"
            elif contract == "part_time":
                employment_type = "Part-time"

            display_location = location_data.get("display_name", "") if isinstance(location_data, dict) else ""

            jobs.append(NormalizedJob(
                external_id=str(item.get("id", "")),
                title=item.get("title", "").strip(),
                company=company_data.get("display_name", "").strip() if isinstance(company_data, dict) else "",
                location=display_location or None,
                description=item.get("description", ""),
                employment_type=employment_type,
                application_url=item.get("redirect_url", ""),
                source=self.name,
                posted_at=posted_at,
                raw_data=item,
            ))

        return jobs
