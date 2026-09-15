"""RemoteOK job source provider adapter.

Fetches remote listings from the RemoteOK public API:
GET https://remoteok.com/api

Terms and Attribution:
RemoteOK listings are remote-only roles. CareerPilot links back to the RemoteOK
listing URL (``source_url``) and application target (``apply_url``) and attributes
RemoteOK as the source. No API credentials are required.
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

REMOTEOK_BASE_URL = "https://remoteok.com/api"
DEFAULT_TIMEOUT_SECONDS = 20.0
USER_AGENT = "CareerPilot/1.0 (JobDiscovery; +https://careerpilot.app)"


import html

def strip_html(text: str) -> str:
    """Remove HTML tags from a string, unescape entities, and normalize whitespace."""
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"\s+", " ", clean)
    clean = re.sub(r"\s+([.,!?;:])", r"\1", clean)
    return html.unescape(clean).strip()



class RemoteOKSource(BaseJobSource):
    name = "RemoteOK"

    @property
    def capabilities(self) -> ProviderCapabilities:
        # RemoteOK is remote-only and supports tag-style query filtering. It does
        # not pass location, salary, pagination, etc. upstream, so all filter
        # dimensions are left to the canonical pipeline layer.
        return ProviderCapabilities()

    @property
    def is_enabled(self) -> bool:
        # Public API - no credentials required
        return True

    def fetch(self, criteria: SearchCriteria) -> list[NormalizedJob]:
        settings = get_settings()
        timeout = getattr(settings, "REMOTEOK_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)

        tag = None
        if criteria.queries and criteria.queries[0]:
            # RemoteOK supports tag-style keyword filtering via `?tag=<tag>`
            tag = criteria.queries[0].strip().lower()

        jobs: list[NormalizedJob] = []
        source_errors: list[str] = []

        try:
            jobs = self._search(tag, timeout)
        except httpx.HTTPStatusError as e:
            source_errors.append(describe_status(e.response.status_code))
            logger.warning("RemoteOK HTTP error %s for tag='%s'", e.response.status_code, tag)
        except (httpx.TimeoutException, httpx.TransportError) as e:
            source_errors.append("timed out")
            logger.warning("RemoteOK request failed for tag='%s': %s", tag, type(e).__name__)
        except SourceUnavailableError as e:
            source_errors.append(str(e))
            logger.warning("RemoteOK source error for tag='%s': %s", tag, e)
        except Exception as e:
            source_errors.append("unexpected error")
            logger.exception("RemoteOK search failed for tag='%s'", tag)

        if not jobs and source_errors:
            raise SourceUnavailableError(
                f"RemoteOK was temporarily unavailable ({'; '.join(dict.fromkeys(source_errors))})."
            )

        return jobs

    def _search(self, tag: str | None, timeout: float) -> list[NormalizedJob]:
        params: dict[str, str] = {}
        if tag:
            params["tag"] = tag

        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }

        response = httpx.get(REMOTEOK_BASE_URL, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()

        try:
            data = response.json()
        except json.JSONDecodeError:
            logger.warning("RemoteOK returned malformed JSON")
            raise SourceUnavailableError("RemoteOK returned an invalid response.")

        if not isinstance(data, list):
            logger.warning("RemoteOK returned non-list JSON payload")
            raise SourceUnavailableError("RemoteOK returned an invalid response.")

        jobs: list[NormalizedJob] = []
        for item in data:
            if not isinstance(item, dict):
                continue

            # Skip RemoteOK legal disclaimer / terms header object
            if "legal" in item and "position" not in item:
                continue

            # Must have minimal identifier and title
            raw_id = item.get("id")
            title = (item.get("position") or "").strip()
            if not raw_id or not title:
                continue

            company = (item.get("company") or "").strip()
            location = (item.get("location") or "").strip() or None

            # Clean HTML description
            raw_desc = item.get("description", "")
            description = strip_html(raw_desc) if raw_desc else None

            # Application & source URLs
            apply_url = item.get("apply_url") or None
            source_url = item.get("url") or None

            # Posted timestamp
            posted_at = None
            raw_date = item.get("date")
            if raw_date:
                try:
                    posted_at = datetime.fromisoformat(
                        str(raw_date).replace("Z", "+00:00")
                    ).isoformat()
                except (ValueError, AttributeError):
                    posted_at = None

            # Salary min/max (0 is sentinel for hidden/not provided)
            salary_min = None
            raw_min = item.get("salary_min")
            if raw_min is not None:
                try:
                    val = int(round(float(raw_min)))
                    if val > 0:
                        salary_min = val
                except (ValueError, TypeError):
                    salary_min = None

            salary_max = None
            raw_max = item.get("salary_max")
            if raw_max is not None:
                try:
                    val = int(round(float(raw_max)))
                    if val > 0:
                        salary_max = val
                except (ValueError, TypeError):
                    salary_max = None

            raw_currency = item.get("salary_currency") or item.get("currency")
            salary_currency = str(raw_currency).strip() if raw_currency else None

            # Skills from tags
            skills = None
            raw_tags = item.get("tags")
            if isinstance(raw_tags, list):
                skills = [str(t).strip() for t in raw_tags if str(t).strip()]

            jobs.append(NormalizedJob(
                external_id=str(raw_id),
                title=title,
                company=company,
                location=location,
                description=description,
                employment_type=None,
                experience_level=None,
                application_url=apply_url,
                source_url=source_url,
                source=self.name,
                posted_at=posted_at,
                remote=True,
                work_mode="remote",
                salary_min=salary_min,
                salary_max=salary_max,
                salary_currency=salary_currency,
                skills=skills,
                raw_data=item,
            ))

        return jobs
