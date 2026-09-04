import json
import logging
import re
from datetime import datetime
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

JOOBLE_BASE_URL = "https://jooble.org/api"
RESULTS_PER_PAGE = 10


#: Currency symbols Jooble may use inline, mapped to ISO 4217 codes.
_CURRENCY_BY_SYMBOL = {
    "₹": "INR",
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
}

#: Deterministic pay-period markers (checked in order). We preserve the period
#: but never convert amounts across periods; ambiguous strings default to
#: "unknown" rather than guessing.
_PERIOD_ALIASES = [
    (("per year", "/year", "/yr", "annually", "annual", "per annum"), "annual"),
    (("per month", "/month", "/mo", "monthly"), "monthly"),
    (("per week", "/week", "weekly"), "weekly"),
    (("per day", "/day", "daily"), "daily"),
    (("per hour", "/hour", "hourly"), "hourly"),
]


def _detect_salary_period(raw: str) -> str:
    """Return the canonical pay period for a salary string, or 'unknown'."""
    low = raw.lower()
    for aliases, period in _PERIOD_ALIASES:
        for alias in aliases:
            if re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", low):
                return period
    return "unknown"


def _parse_salary(
    raw_salary: str | None,
) -> tuple[int | None, int | None, str | None, str]:
    """Parse a Jooble salary string into (min, max, currency, period).

    Handles trailing 3-letter codes ('17,600 UAH'), leading/inline currency
    symbols ('₹6,00,000 - ₹9,00,000', '$80,000 - $100,000'), ranges and single
    amounts, and deterministic pay-period markers. Currency is preserved but
    never converted; amounts are not converted across pay periods.
    """
    if not raw_salary:
        return None, None, None, "unknown"
    cleaned = raw_salary.strip()
    period = _detect_salary_period(cleaned)

    currency = None
    # Trailing 3-letter ISO currency code, e.g. "17,600 UAH".
    trailing_code = re.search(r"\s+([A-Z]{3})\s*$", cleaned)
    if trailing_code:
        currency = trailing_code.group(1)
        amount_part = cleaned[:trailing_code.start()]
    else:
        amount_part = cleaned

    # Leading currency symbol (only meaningful at the start).
    stripped = amount_part.lstrip()
    if not currency:
        for symbol, code in _CURRENCY_BY_SYMBOL.items():
            if stripped.startswith(symbol):
                currency = code
                break

    # Remove all currency symbols so ranges like "₹6,00,000 - ₹9,00,000" parse.
    symbols = "".join(_CURRENCY_BY_SYMBOL.keys())
    amount_part = re.sub("[" + re.escape(symbols) + "]", "", amount_part)
    # Remove inline currency codes and stray letters.
    amount_part = re.sub(r"[A-Za-z]+", "", amount_part)
    # Remove commas and whitespace.
    amount_part = re.sub(r"[,\s]", "", amount_part)

    range_match = re.match(r"(\d+)\s*-\s*(\d+)", amount_part)
    if range_match:
        return int(range_match.group(1)), int(range_match.group(2)), currency, period
    single_match = re.match(r"(\d+)", amount_part)
    if single_match:
        val = int(single_match.group(1))
        return val, val, currency, period
    return None, None, None, period


class JoobleSource(BaseJobSource):
    name = "Jooble"

    @property
    def capabilities(self) -> ProviderCapabilities:
        # The current adapter only sends `keywords` and `location`. Although the
        # Jooble API also documents salary/page/etc., this adapter does NOT pass
        # those criteria upstream yet, so only location is reported as
        # supported. Do NOT claim a capability the adapter does not use.
        return ProviderCapabilities(
            supports_location=True,
        )

    @property
    def is_enabled(self) -> bool:
        settings = get_settings()
        return bool(settings.JOOBLE_API_KEY)

    def fetch(self, criteria: SearchCriteria) -> list[NormalizedJob]:
        settings = get_settings()
        api_key = settings.JOOBLE_API_KEY
        timeout = settings.JOOBLE_TIMEOUT_SECONDS

        if not api_key:
            logger.warning("Jooble API key not configured, skipping")
            return []

        jobs: list[NormalizedJob] = []
        source_errors: list[str] = []
        primary_location = criteria.locations[0] if criteria.locations else ""

        for query in criteria.queries[:2]:
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

            salary_min, salary_max, salary_currency, salary_period = _parse_salary(item.get("salary"))

            employment_type = item.get("type")
            if employment_type:
                employment_type = employment_type.strip()

            # Jooble exposes a single "updated" timestamp (listing update time)
            # and no distinct "posted" timestamp. We use it as the posted_at
            # freshness proxy to keep recency ordering working; updated_at is
            # left None because Jooble does not distinguish the two. This is a
            # documented pragmatic fallback, NOT fetched_at substitution.
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
                salary_period=salary_period,
                raw_data=item,
            ))

        return jobs
