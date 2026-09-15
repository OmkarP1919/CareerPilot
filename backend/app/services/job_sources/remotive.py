"""Remotive job source provider adapter.

Fetches remote listings from the Remotive public API:
GET https://remotive.com/api/remote-jobs

Terms and Attribution Constraints:
- CareerPilot must link back to the Remotive listing/source URL (``source_url``)
  and attribute Remotive as the source.
- Do NOT submit or re-publish Remotive jobs to third-party job boards.
- Do NOT create a signup wall or paywall around Remotive listings.
- Remotive API is free and public; no API key is required.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
import httpx

from app.core.config import get_settings
from app.services.job_sources.base import (
    BaseJobSource,
    NormalizedJob,
    ProviderCapabilities,
    SearchCriteria,
    SourceUnavailableError,
    describe_status,
)

logger = logging.getLogger(__name__)

REMOTIVE_BASE_URL = "https://remotive.com/api/remote-jobs"
DEFAULT_TIMEOUT_SECONDS = 20.0
USER_AGENT = "CareerPilot/1.0 (JobDiscovery; +https://careerpilot.app)"

_CURRENCY_SYMBOLS: dict[str, str] = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "₹": "INR",
}

_JOB_TYPE_MAP: dict[str, str] = {
    "full_time": "Full-time",
    "full-time": "Full-time",
    "full time": "Full-time",
    "part_time": "Part-time",
    "part-time": "Part-time",
    "part time": "Part-time",
    "contract": "Contract",
    "freelance": "Freelance",
    "internship": "Internship",
}


import html

def strip_html(text: str) -> str:
    """Remove HTML tags from a string, unescape entities, and normalize whitespace."""
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"\s+", " ", clean)
    clean = re.sub(r"\s+([.,!?;:])", r"\1", clean)
    return html.unescape(clean).strip()


def _parse_salary_amount(raw_num: str) -> int | None:
    """Parse a single amount string, handling 'k' multiplier and commas."""
    cleaned = raw_num.strip().lower()
    has_k = cleaned.endswith("k")
    if has_k:
        cleaned = cleaned[:-1].strip()
    cleaned = cleaned.replace(",", "")
    try:
        val = float(cleaned)
        if has_k:
            val *= 1000.0
        return int(round(val))
    except (ValueError, TypeError):
        return None


def parse_remotive_salary(
    raw_salary: str | None,
) -> tuple[int | None, int | None, str | None, str | None]:
    """Conservatively parse a Remotive salary string.

    Supports ranges ($100k - $120k, $80,000 - $100,000, 50k-70k EUR) and single
    values ($120k, €60,000). Returns (min, max, currency, period). Never
    invents or guesses values when ambiguous or unparseable.
    """
    if not raw_salary or not isinstance(raw_salary, str):
        return None, None, None, None

    cleaned = raw_salary.strip()
    if not cleaned:
        return None, None, None, None

    # Detect currency
    currency = None
    for sym, code in _CURRENCY_SYMBOLS.items():
        if sym in cleaned:
            currency = code
            break

    if not currency:
        # Check for 3-letter currency code (e.g. USD, EUR, GBP, CAD)
        code_match = re.search(r"\b([A-Z]{3})\b", cleaned)
        if code_match:
            currency = code_match.group(1)

    # Detect pay period
    lowered = cleaned.lower()
    period = None
    if re.search(r"/\s*(?:year|yr)\b|\bper\s+year\b|\bannu", lowered):
        period = "annual"
    elif re.search(r"/\s*(?:month|mo)\b|\bper\s+month\b|\bmonthly\b", lowered):
        period = "monthly"
    elif re.search(r"/\s*(?:hour|hr)\b|\bper\s+hour\b|\bhourly\b", lowered):
        period = "hourly"
    elif re.search(r"/\s*week\b|\bper\s+week\b|\bweekly\b", lowered):
        period = "weekly"
    elif re.search(r"/\s*day\b|\bper\s+day\b|\bdaily\b", lowered):
        period = "daily"

    # Strip symbols, currency codes, and non-numeric characters except range dash, dot, commas, 'k'
    work = cleaned
    for sym in _CURRENCY_SYMBOLS.keys():
        work = work.replace(sym, " ")
    if currency:
        work = re.sub(rf"\b{currency}\b", " ", work, flags=re.IGNORECASE)

    # Remove period words
    work = re.sub(r"/\s*(?:year|month|hour|yr|mo|hr|week|day)\b", " ", work, flags=re.IGNORECASE)
    work = re.sub(r"\b(per|annually|annual|monthly|hourly|weekly|daily)\b", " ", work, flags=re.IGNORECASE)

    # Look for range: e.g. "100k - 120k" or "80,000 - 100,000"
    range_match = re.search(
        r"(\d+(?:[.,]\d+)?\s*k?)\s*(?:-|to)\s*(\d+(?:[.,]\d+)?\s*k?)",
        work,
        flags=re.IGNORECASE,
    )
    if range_match:
        s_min = _parse_salary_amount(range_match.group(1))
        s_max = _parse_salary_amount(range_match.group(2))
        if s_min is not None and s_max is not None:
            if s_min > s_max:
                s_min, s_max = s_max, s_min
            return s_min, s_max, currency, period

    # Look for single value: e.g. "120k" or "80,000"
    single_match = re.search(r"(\d+(?:[.,]\d+)?\s*k?)", work, flags=re.IGNORECASE)
    if single_match:
        val = _parse_salary_amount(single_match.group(1))
        if val is not None and val > 0:
            return val, val, currency, period

    return None, None, None, None


class RemotiveSource(BaseJobSource):
    name = "Remotive"

    @property
    def capabilities(self) -> ProviderCapabilities:
        # Remotive is remote-only and supports search and location query params.
        return ProviderCapabilities(
            supports_location=True,
        )

    @property
    def is_enabled(self) -> bool:
        # Public API - no credentials required
        return True

    def fetch(self, criteria: SearchCriteria) -> list[NormalizedJob]:
        settings = get_settings()
        timeout = getattr(settings, "REMOTIVE_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)

        search_query = criteria.queries[0].strip() if criteria.queries and criteria.queries[0] else None
        location_query = criteria.locations[0].strip() if criteria.locations and criteria.locations[0] else None

        jobs: list[NormalizedJob] = []
        source_errors: list[str] = []

        try:
            jobs = self._search(search_query, location_query, timeout)
        except httpx.HTTPStatusError as e:
            source_errors.append(describe_status(e.response.status_code))
            logger.warning("Remotive HTTP error %s for query='%s'", e.response.status_code, search_query)
        except (httpx.TimeoutException, httpx.TransportError) as e:
            source_errors.append("timed out")
            logger.warning("Remotive request failed for query='%s': %s", search_query, type(e).__name__)
        except SourceUnavailableError as e:
            source_errors.append(str(e))
            logger.warning("Remotive source error for query='%s': %s", search_query, e)
        except Exception as e:
            source_errors.append("unexpected error")
            logger.exception("Remotive search failed for query='%s'", search_query)

        if not jobs and source_errors:
            raise SourceUnavailableError(
                f"Remotive was temporarily unavailable ({'; '.join(dict.fromkeys(source_errors))})."
            )

        return jobs

    def _search(
        self,
        search_query: str | None,
        location_query: str | None,
        timeout: float,
    ) -> list[NormalizedJob]:
        params: dict[str, str] = {}
        if search_query:
            params["search"] = search_query
        if location_query:
            params["location"] = location_query

        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }

        response = httpx.get(REMOTIVE_BASE_URL, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()

        try:
            data = response.json()
        except json.JSONDecodeError:
            logger.warning("Remotive returned malformed JSON")
            raise SourceUnavailableError("Remotive returned an invalid response.")

        if not isinstance(data, dict):
            logger.warning("Remotive returned non-dict JSON payload")
            raise SourceUnavailableError("Remotive returned an invalid response.")

        raw_jobs = data.get("jobs", [])
        if not isinstance(raw_jobs, list):
            return []

        jobs: list[NormalizedJob] = []
        for item in raw_jobs:
            if not isinstance(item, dict):
                continue

            raw_id = item.get("id")
            title = (item.get("title") or "").strip()
            if not raw_id or not title:
                continue

            company = (item.get("company_name") or "").strip()
            candidate_location = (item.get("candidate_required_location") or "").strip() or None

            # Clean HTML description
            raw_desc = item.get("description", "")
            description = strip_html(raw_desc) if raw_desc else None

            # CRITICAL URL RULE: Remotive item.url is the Remotive listing/source URL.
            # Only populate application_url if an explicit apply destination exists upstream.
            source_url = item.get("url") or None
            apply_url = item.get("apply_url") or item.get("application_url") or None

            # Publication date
            posted_at = None
            raw_date = item.get("publication_date")
            if raw_date:
                try:
                    posted_at = datetime.fromisoformat(
                        str(raw_date).replace("Z", "+00:00")
                    ).isoformat()
                except (ValueError, AttributeError):
                    posted_at = None

            # Job type -> employment_type
            raw_job_type = item.get("job_type")
            employment_type = None
            if raw_job_type and isinstance(raw_job_type, str):
                employment_type = _JOB_TYPE_MAP.get(raw_job_type.lower().strip())

            # Salary parsing
            raw_salary = item.get("salary")
            s_min, s_max, s_currency, s_period = parse_remotive_salary(raw_salary)

            # Skills from tags
            skills = None
            raw_tags = item.get("tags")
            if isinstance(raw_tags, list):
                skills = [str(t).strip() for t in raw_tags if str(t).strip()]

            # Category
            category = item.get("category") or None

            jobs.append(NormalizedJob(
                external_id=str(raw_id),
                title=title,
                company=company,
                location=candidate_location,
                description=description,
                employment_type=employment_type,
                experience_level=None,
                application_url=apply_url,
                source_url=source_url,
                source=self.name,
                posted_at=posted_at,
                remote=True,
                work_mode="remote",
                salary_min=s_min,
                salary_max=s_max,
                salary_currency=s_currency,
                salary_period=s_period,
                skills=skills,
                category=category,
                raw_data=item,
            ))

        return jobs
