"""Canonical discovery normalization, filtering and sorting layer (Phase 5B).

This module is the common, provider-agnostic layer of the discovery pipeline:

    SearchCriteria
         -> Provider
         -> SourceResult / NormalizedJob
         -> canonical normalization & enrichment
         -> filtering
         -> sorting
         -> final discovery result

Providers translate provider-specific API payloads into :class:`NormalizedJob`.
This module is responsible for the common semantics: normalization, filtering,
sorting and consistent missing-data behavior. It contains NO provider-specific
parsing. Provider-specific data must never leak into the rest of the
application through anything other than ``NormalizedJob``.

Design rules enforced here:

* Normalization is deterministic and conservative. No values are invented;
  missing data stays ``None`` / ``unspecified``.
* Filters are applied only where reliable normalized data exists. A criterion
  a provider did not support upstream is applied here against the returned
  ``NormalizedJob`` when it can be evaluated reliably; otherwise the filter
  follows the documented missing-data policy (see below).
* Radius is NOT implemented because there are no reliable coordinates in the
  current architecture. We never pretend radius filtering was performed.
* Salary is parsed without mixing pay periods (annual / monthly / hourly are
  kept distinct or left unparsed when ambiguous).
"""
from __future__ import annotations

import re
import logging
from datetime import datetime, timezone
from typing import Iterable, Sequence

from app.services.job_sources.base import NormalizedJob, SearchCriteria

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Canonical vocabularies
# ---------------------------------------------------------------------------

#: Canonical employment-type vocabulary (lowercase, hyphenated).
EMPLOYMENT_TYPES = {
    "full-time", "part-time", "contract", "internship", "temporary",
    "freelance", "volunteer", "other", "unspecified",
}

#: Canonical experience-level vocabulary (lowercase).
EXPERIENCE_LEVELS = {
    "internship", "entry", "junior", "mid", "senior", "lead",
    "manager", "director", "executive", "unspecified",
}

#: Canonical work-mode vocabulary.
WORK_MODES = {"remote", "hybrid", "onsite", "unspecified"}

#: Supported deterministic sort modes.
SORT_MODES = {"newest", "oldest", "salary", "relevance"}

#: Canonical pay-period vocabulary. Periods are NEVER converted between each
#: other; a job's period is preserved and comparisons across incompatible
#: periods are refused rather than silently converted.
SALARY_PERIODS = {"annual", "monthly", "weekly", "daily", "hourly", "unknown"}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _clean(text: str | None) -> str:
    """Collapse whitespace on a string; return '' for None/empty.

    Non-string inputs (e.g. malformed provider data) are coerced to their
    string form defensively so normalization never crashes discovery.
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    return re.sub(r"\s+", " ", text.strip())


def _norm_token(text: str | None) -> str:
    """Lowercase, collapse whitespace — a normalized comparison key."""
    return _clean(text).lower()


# ---------------------------------------------------------------------------
# 1. Title / company
# ---------------------------------------------------------------------------

def normalize_title(title: str | None) -> str:
    """Normalize whitespace while preserving meaningful title text."""
    return _clean(title)


def normalize_company(company: str | None) -> str:
    """Normalize whitespace and obvious surrounding noise for a company name.

    Legitimate company names are not altered beyond whitespace trimming.
    """
    cleaned = _clean(company)
    return cleaned


# ---------------------------------------------------------------------------
# 2. Location / city / country
# ---------------------------------------------------------------------------

#: Deterministic country-code map (city/country keyword -> ISO 3166 alpha-2).
#: This is a small, conservative map reused by the common layer; it is the
#: authoritative source for derive_country_code. Do not call a geocoding API.
COUNTRY_MAP: dict[str, str] = {
    "india": "in",
    "pune": "in",
    "mumbai": "in",
    "bangalore": "in",
    "bengaluru": "in",
    "delhi": "in",
    "hyderabad": "in",
    "chennai": "in",
    "gurgaon": "in",
    "gurugram": "in",
    "noida": "in",
    "kolkata": "in",
    "united kingdom": "gb",
    "uk": "gb",
    "great britain": "gb",
    "england": "gb",
    "scotland": "gb",
    "wales": "gb",
    "london": "gb",
    "manchester": "gb",
    "birmingham": "gb",
    "edinburgh": "gb",
    "united states": "us",
    "usa": "us",
    "u.s.a": "us",
    "america": "us",
    "san francisco": "us",
    "san francisco bay area": "us",
    "new york": "us",
    "new york city": "us",
    "seattle": "us",
    "austin": "us",
    "california": "us",
    "chicago": "us",
    "canada": "ca",
    "toronto": "ca",
    "vancouver": "ca",
    "montreal": "ca",
    "germany": "de",
    "berlin": "de",
    "munich": "de",
    "frankfurt": "de",
    "australia": "au",
    "sydney": "au",
    "melbourne": "au",
    "singapore": "sg",
    "new zealand": "nz",
    "france": "fr",
    "paris": "fr",
    "netherlands": "nl",
    "amsterdam": "nl",
    "spain": "es",
    "madrid": "es",
    "italy": "it",
    "switzerland": "ch",
    "zurich": "ch",
    "brazil": "br",
    "mexico": "mx",
    "japan": "jp",
    "tokyo": "jp",
}


def derive_country_code(parts: Iterable[str | None]) -> str | None:
    """Deterministically resolve an ISO country code from location parts.

    Checks structured ``country`` first, then matches known city/country
    keywords in a case-insensitive, token-substring manner. Returns None when
    the country cannot be determined; it never invents one.
    """
    for part in parts:
        if not part:
            continue
        low = _norm_token(part)
        # A bare ISO alpha-2 / alpha-3 code is accepted directly.
        if re.fullmatch(r"[a-z]{2}", low) and low in {
            "in", "gb", "us", "ca", "de", "au", "sg", "nz",
            "fr", "nl", "es", "it", "ch", "br", "mx", "jp", "za", "pl", "ru",
        }:
            return low
        if low in COUNTRY_MAP:
            return COUNTRY_MAP[low]
        for keyword, code in COUNTRY_MAP.items():
            # Whole-word token match to avoid false positives
            # (e.g. "us" must not match inside "business").
            if re.search(rf"(?<![a-z]){re.escape(keyword)}(?![a-z])", low):
                return code
    return None


#: Country / region names that are never a city (used to avoid mis-classifying
#: a country segment as the city when deriving city from free text).
_REGION_ONLY_TERMS = {
    "india", "united kingdom", "uk", "great britain", "england", "scotland",
    "wales", "united states", "usa", "u.s.a", "america", "california",
    "canada", "germany", "australia", "singapore", "new zealand", "france",
    "netherlands", "spain", "italy", "switzerland", "brazil", "mexico",
    "japan", "europe", "european union", "remote", "anywhere",
}

#: Work-mode tokens that are never a city.
_WORK_MODE_PHRASES_BY_TOKEN = {
    "remote", "hybrid", "onsite", "on-site", "on site", "wfh",
    "work from home", "office", "in-office", "in office", "in-person",
}


def normalize_location(job: NormalizedJob) -> None:
    """Normalize / derive city and country on a NormalizedJob in place.

    Preference order for country:
      1. structured ``job.country`` (if already a plausible code)
      2. derived from the free-text ``job.location`` via COUNTRY_MAP
    City is derived from the first (most specific) non-empty location segment
    ONLY when it does not itself look like a country or a region. This is
    conservative — ambiguous/unstructured locations are left as free text.
    """
    if not job.location:
        return

    # 1. Country: structured field first, then derive from location text.
    if not job.country:
        derived = derive_country_code([job.location])
        if derived:
            job.country = derived

    # 2. City: take the first segment that is NOT a recognized country/region
    # name and is not a work-mode keyword. We keep this deliberately
    # conservative: we do not guess a city when the string is just a country.
    if not job.city:
        segments = [s.strip() for s in re.split(r"[,\-/]", job.location) if s.strip()]
        for seg in segments:
            seg_low = _norm_token(seg)
            # Skip pure country/region names (never a city) and bare
            # two-letter country codes.
            if seg_low in _REGION_ONLY_TERMS or re.fullmatch(r"[a-z]{2}", seg_low):
                continue
            # A work-mode keyword is not a city.
            if seg_low in _WORK_MODE_PHRASES_BY_TOKEN:
                continue
            job.city = seg
            break


# ---------------------------------------------------------------------------
# 3. Work mode (remote / hybrid / onsite / unspecified)
# ---------------------------------------------------------------------------

#: Phrases that strongly indicate a work mode from LOCATION text. Location is
#: strong evidence and may classify onsite, hybrid, or remote.
_HYBRID_PHRASES = {
    "hybrid", "hybrid remote", "hybrid work", "hybrid - remote",
    "hybrid (remote/onsite)", "partially remote", "flexible hybrid",
    "hybrid/onsite", "hybrid/remote", "remote hybrid",
}
_REMOTE_PHRASES = {
    "remote", "work from home", "wfh", "fully remote", "100% remote",
    "work remotely", "home based", "remote-first", "remote first",
    "telecommute", "telecommuting", "virtual",
}
_ONSITE_PHRASES = {
    "onsite", "on-site", "on site", "in office", "in-person", "in person",
    "on premises", "office", "at office", "onsite only", "on-site only",
}

#: Phrase sets for DESCRIPTION text. Description is WEAK evidence: it may only
#: strongly indicate hybrid or remote. Bare 'office'/'onsite'/'in person' /
#: 'on site' mentions inside a body of text are deliberately excluded so that
#: a field role that happens to mention an office is not misclassified onsite.
_DESC_REMOTE_PHRASES = _REMOTE_PHRASES
_DESC_HYBRID_PHRASES = _HYBRID_PHRASES


def _match_any(text: str, phrases: set[str]) -> bool:
    """Return True when any whole-word-aware phrase appears in ``text``."""
    if not text:
        return False
    for phrase in phrases:
        if re.search(rf"(?<![a-z]){re.escape(phrase)}(?![a-z])", text):
            return True
    return False


def normalize_work_mode(job: NormalizedJob) -> None:
    """Determine the canonical work mode and set ``job.work_mode`` in place.

    Policy (hardened in 5B.1):
      * Strong text evidence (``location``/``description``) is classified
        first; ``location`` may classify onsite, ``description`` may only
        strongly indicate hybrid/remote (bare 'office'/'onsite' inside a body
        of text is ignored so a field role is not misforced onsite).
      * The source-flagged ``remote`` boolean is trusted only as a fallback,
        and it is NOT allowed to override strong contradictory text: a
        ``remote=True`` flag with onsite text (or vice versa) is a
        contradiction and resolves to ``unspecified``.
    """
    text_mode = _classify_work_mode_text(job)
    flag_mode = "remote" if job.remote is True else ("onsite" if job.remote is False else None)

    if text_mode is not None:
        if flag_mode is not None and _work_modes_contradict(flag_mode, text_mode):
            job.work_mode = "unspecified"
            return
        job.work_mode = text_mode
        return

    if flag_mode is not None:
        job.work_mode = flag_mode
        return

    job.work_mode = "unspecified"


def _work_modes_contradict(a: str, b: str) -> bool:
    """True when two modes are strict opposites (remote vs onsite)."""
    return (a == "remote" and b == "onsite") or (a == "onsite" and b == "remote")


def _classify_work_mode_text(job: NormalizedJob) -> str | None:
    """Classify work mode from location/description text, or None if unclear."""
    location_evidence = _clean(job.location).lower()
    desc_evidence = _clean(job.description)[:400].lower()

    if _match_any(desc_evidence, _DESC_HYBRID_PHRASES):
        return "hybrid"
    if _match_any(desc_evidence, _DESC_REMOTE_PHRASES):
        return "remote"
    if _match_any(location_evidence, _HYBRID_PHRASES):
        return "hybrid"
    if _match_any(location_evidence, _REMOTE_PHRASES):
        return "remote"
    if _match_any(location_evidence, _ONSITE_PHRASES):
        return "onsite"
    return None


# ---------------------------------------------------------------------------
# 4. Employment type
# ---------------------------------------------------------------------------

_EMPLOYMENT_ALIASES: dict[str, str] = {
    "permanent": "full-time",
    "fulltime": "full-time",
    "full time": "full-time",
    "full-time": "full-time",
    "full": "full-time",
    "part time": "part-time",
    "parttime": "part-time",
    "part-time": "part-time",
    "part": "part-time",
    "contract": "contract",
    "contractor": "contract",
    "contract basis": "contract",
    "temporary": "temporary",
    "temp": "temporary",
    "freelance": "freelance",
    "freelancer": "freelance",
    "internship": "internship",
    "intern": "internship",
    "internships": "internship",
    "volunteer": "volunteer",
    "volunteering": "volunteer",
    "other": "other",
}


def normalize_employment_type(job: NormalizedJob) -> None:
    """Canonicalize ``job.employment_type`` in place into the vocabulary.

    Only known aliases are mapped; anything unknown becomes ``"unspecified"``
    rather than being fabricated. The raw provider value remains in
    ``raw_data`` for provenance.
    """
    if not job.employment_type:
        job.employment_type = "unspecified"
        return

    # If already canonical, keep it.
    key = _norm_token(job.employment_type)
    if key in EMPLOYMENT_TYPES:
        job.employment_type = key
        return

    mapped = _EMPLOYMENT_ALIASES.get(key)
    if mapped:
        job.employment_type = mapped
        return

    # Handle e.g. "Full-time / Permanent" -> first known alias wins.
    for part in re.split(r"[/&,]", key):
        part = part.strip()
        mapped_part = _EMPLOYMENT_ALIASES.get(part)
        if mapped_part:
            job.employment_type = mapped_part
            return

    job.employment_type = "unspecified"


# ---------------------------------------------------------------------------
# 5. Internship classification
# ---------------------------------------------------------------------------

#: Phrases that, if seen in a job title, strongly indicate an internship role.
_INTERNSHIP_TITLE_TERMS = {"intern", "internship", "trainee", "graduate trainee"}


def classify_internship(job: NormalizedJob) -> bool:
    """Return True when the job is confidently an internship.

    Uses provider-flagged employment_type, a canonical category, or title
    text. We intentionally do NOT scan the full description for the word
    'intern' (a description may mention interning responsibilities without the
    role being an internship).
    """
    if job.employment_type == "internship":
        return True

    category_low = _norm_token(job.category)
    if category_low in {"internship", "internships", "intern"}:
        return True

    title_low = _norm_token(job.title)
    for term in _INTERNSHIP_TITLE_TERMS:
        if re.search(rf"(?<![a-z]){re.escape(term)}(?![a-z])", title_low):
            return True

    return False


# ---------------------------------------------------------------------------
# 6. Experience level
# ---------------------------------------------------------------------------

_EXPERIENCE_ALIASES: dict[str, str] = {
    "entry": "entry",
    "entry level": "entry",
    "entry-level": "entry",
    "junior": "junior",
    "jr": "junior",
    "jr.": "junior",
    "mid": "mid",
    "mid level": "mid",
    "mid-level": "mid",
    "intermediate": "mid",
    "senior": "senior",
    "sr": "senior",
    "sr.": "senior",
    "snr": "senior",
    "lead": "lead",
    "tech lead": "lead",
    "manager": "manager",
    "director": "director",
    "executive": "executive",
    "c-level": "executive",
    "intern": "internship",
    "internship": "internship",
    "graduate": "entry",
    "fresher": "entry",
    "student": "entry",
}


def normalize_experience_level(job: NormalizedJob) -> None:
    """Conservatively canonicalize ``job.experience_level`` in place.

    Only clear aliases are mapped; anything unrecognized becomes
    ``"unspecified"``. A numeric "2-4 years" is NOT auto-inferred to a seniority
    band because there is no established deterministic mapping here.
    """
    if not job.experience_level:
        job.experience_level = "unspecified"
        return

    key = _norm_token(job.experience_level)
    if key in EXPERIENCE_LEVELS:
        job.experience_level = key
        return

    # "X years", "n+ years" -> cannot reliably map to a band -> unspecified.
    if re.search(r"\b\d{1,2}\s*\+?\s*years?\b", key):
        job.experience_level = "unspecified"
        return

    mapped = _EXPERIENCE_ALIASES.get(key)
    job.experience_level = mapped if mapped else "unspecified"


# ---------------------------------------------------------------------------
# 7. Salary
# ---------------------------------------------------------------------------

_CURRENCY_SYMBOLS: dict[str, str] = {
    "$": "USD",
    "usd": "USD",
    "inr": "INR",
    "rs": "INR",
    "rs.": "INR",
    "₹": "INR",
    "eur": "EUR",
    "€": "EUR",
    "gbp": "GBP",
    "£": "GBP",
    "uah": "UAH",
    "cad": "CAD",
    "aud": "AUD",
    "sgd": "SGD",
    "nzd": "NZD",
    "jpy": "JPY",
}

#: Pay-period markers. We keep the period but never convert amounts across
#: periods. When a period is present we record it in a suffix and leave the
#: numeric min/max unparsed if converting would change the annual meaning.
_PAY_PERIOD_MARKERS = {"per year", "/year", "annually", "per annum", "pa",
                       "per month", "/month", "monthly", "per hour", "/hour",
                       "hourly", "weekly"}


def _strip_number(raw_number: str) -> int | None:
    """Parse a bare numeric string with comma/space thousands separators."""
    cleaned = re.sub(r"[,\s]", "", raw_number)
    cleaned = re.sub(r"\b\.0\b", "", cleaned)
    if not re.fullmatch(r"\d{1,15}", cleaned):
        return None
    return int(cleaned)


def normalize_salary(job: NormalizedJob) -> None:
    """Safely parse/validate salary fields on a NormalizedJob in place.

    - Coerces numeric ``salary_min``/``salary_max`` to int.
    - Does NOT convert pay periods. If a raw free-text salary contains a
      period marker, we leave numeric fields untouched rather than risk
      mixing e.g. a monthly figure with an annual comparison. This is the
      documented safety rule from Phase 5B / hardened in 5B.1.
    - Normalizes ``salary_period`` into the canonical vocabulary, defaulting
      to ``"unknown"`` when the period is absent or unrecognized. It never
      guesses a period.
    """
    if job.salary_min is not None:
        try:
            job.salary_min = int(job.salary_min)
        except (TypeError, ValueError):
            job.salary_min = None
    if job.salary_max is not None:
        try:
            job.salary_max = int(job.salary_max)
        except (TypeError, ValueError):
            job.salary_max = None
    if job.salary_min is not None and job.salary_min < 0:
        job.salary_min = None
    if job.salary_max is not None and job.salary_max < 0:
        job.salary_max = None

    raw_period = getattr(job, "salary_period", None)
    if raw_period is None:
        job.salary_period = "unknown"
    else:
        period = _norm_token(raw_period)
        job.salary_period = period if period in SALARY_PERIODS else "unknown"


# ---------------------------------------------------------------------------
# 8. Skills
# ---------------------------------------------------------------------------

def normalize_skills(skills: Iterable[str] | None) -> list[str]:
    """Return a deterministic, deduplicated, canonical list of skills.

    Normalization is case/whitespace folding only — no taxonomy, no LLM.
    Duplicates (case/space variants) collapse to the first-seen variant.
    """
    if not skills:
        return []
    seen: dict[str, str] = {}
    order: list[str] = []
    for raw in skills:
        if not raw:
            continue
        cleaned = _clean(raw)
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen[key] = cleaned
        order.append(cleaned)
    return order


# ---------------------------------------------------------------------------
# 9. Category
# ---------------------------------------------------------------------------

#: Small, documented canonical category vocabulary. Only mapped when the
#: source provides a clear signal; otherwise left unset.
CATEGORY_ALIASES: dict[str, str] = {
    "software engineering": "software-engineering",
    "software development": "software-engineering",
    "software dev": "software-engineering",
    "software": "software-engineering",
    "engineering - software": "software-engineering",
    "it engineering": "software-engineering",
    "it & software": "software-engineering",
    "information technology": "software-engineering",
    "it": "software-engineering",
    "data science": "data",
    "data": "data",
    "data analytics": "data",
    "analytics": "data",
    "machine learning": "data",
    "artificial intelligence": "data",
    "ai/ml": "data",
    "design": "design",
    "product design": "design",
    "ui/ux": "design",
    "marketing": "marketing",
    "sales": "sales",
    "customer service": "customer-service",
    "support": "customer-service",
    "human resources": "human-resources",
    "hr": "human-resources",
    "finance": "finance",
    "operations": "operations",
    "project management": "project-management",
    "engineering manager": "engineering-management",
    "management": "management",
}


def normalize_category(job: NormalizedJob) -> None:
    """Conservatively canonicalize ``job.category`` in place (lowercase).

    Only maps known aliases; unknown categories are preserved as-is (lowercased)
    when they are non-empty, otherwise left None. We never hallucinate a category
    from a vague description.
    """
    if not job.category:
        return
    key = _norm_token(job.category)
    mapped = CATEGORY_ALIASES.get(key)
    if mapped:
        job.category = mapped
        return
    job.category = key if key else None


# ---------------------------------------------------------------------------
# 10. Dates / freshness
# ---------------------------------------------------------------------------

def parse_iso_datetime(value: str | None) -> datetime | None:
    """Parse an ISO-8601 string into a timezone-aware datetime, or None.

    Never raises. Invalid dates return None. Naive datetimes are assumed UTC
    for consistent comparison (documented behavior).
    """
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError, TypeError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def normalize_dates(job: NormalizedJob) -> None:
    """Validate ``posted_at``/``updated_at`` on a NormalizedJob in place.

    Invalid provider dates are set to None so they cannot crash downstream
    filtering/sorting. ``posted_at`` is never substituted from ``fetched_at``.
    """
    if job.posted_at is not None and parse_iso_datetime(job.posted_at) is None:
        job.posted_at = None
    if job.updated_at is not None and parse_iso_datetime(job.updated_at) is None:
        job.updated_at = None


# ---------------------------------------------------------------------------
# Full normalization
# ---------------------------------------------------------------------------

def normalize_job(job: NormalizedJob) -> NormalizedJob:
    """Apply all canonical normalization rules to a single job (in place)."""
    job.title = normalize_title(job.title)
    job.company = normalize_company(job.company)
    normalize_location(job)
    normalize_work_mode(job)
    normalize_employment_type(job)
    normalize_experience_level(job)
    normalize_salary(job)
    normalize_dates(job)
    if job.skills:
        job.skills = normalize_skills(job.skills)
    normalize_category(job)
    return job


def normalize_jobs(jobs: Iterable[NormalizedJob]) -> list[NormalizedJob]:
    """Normalize an iterable of jobs, defensively tolerating malformed entries."""
    result: list[NormalizedJob] = []
    for job in jobs:
        try:
            result.append(normalize_job(job))
        except Exception:
            logger.exception("Skipping job that failed normalization")
    return result


# ---------------------------------------------------------------------------
# Filtering engine
# ---------------------------------------------------------------------------

#: Missing-data policy documentation. Filters treat missing data deterministically:
#:  - A filter with an explicit constraint excludes a job whose data is unknown
#:    (we do NOT treat missing salary as zero, missing remote as on-site, etc.).
#:  - A filter with no constraint is a no-op.
#: This prevents silently passing jobs that did not actually satisfy an
#: explicit requested constraint.


def _canonical_period(period: str | None) -> str:
    """Map a raw salary-period value to the canonical vocabulary ('unknown' fallback)."""
    if not period:
        return "unknown"
    p = _norm_token(period)
    return p if p in SALARY_PERIODS else "unknown"


def _salary_comparable(job: NormalizedJob, c: SearchCriteria) -> bool:
    """Return True only when a job's salary is safely comparable to the request.

    Salary comparisons MUST NOT silently compare incompatible pay periods or
    currencies. Policy (documented):

    * Period: when the request declares a specific period
      (``c.salary_period``), a job is comparable only if it declares the SAME
      known period. A job with a different or unknown period fails. When the
      request declares no period, the legacy numeric fallback applies (both
      sides treated as compatible) — the request simply did not pin a unit.
    * Currency: when the request declares a currency (``c.salary_currency``),
      a job with a different or unknown currency fails. We never convert
      currencies. When the request declares no currency, no currency gate is
      applied (there is nothing to compare it against).
    """
    req_period = _canonical_period(getattr(c, "salary_period", None))
    if req_period != "unknown":
        job_period = _canonical_period(getattr(job, "salary_period", None))
        if job_period != req_period:
            return False

    req_currency = (getattr(c, "salary_currency", None) or "").strip().upper()
    if req_currency:
        job_currency = (job.salary_currency or "").strip().upper()
        if not job_currency or job_currency != req_currency:
            return False
    return True


def _salary_boundaries_ok(job: NormalizedJob, c: SearchCriteria) -> bool:
    """Numeric range-overlap check against the requested salary bounds.

    A job with no salary boundaries at all fails an explicit salary filter
    (missing data never satisfies an explicit constraint). A job with a single
    boundary is compared on the boundary it exposes: ``salary_min`` is the
    lower bound of its range, ``salary_max`` the upper bound.
    """
    job_min = job.salary_min
    job_max = job.salary_max
    if job_min is None and job_max is None:
        return False
    if c.salary_min is not None:
        upper_or_point = job_max if job_max is not None else job_min
        if upper_or_point is not None and upper_or_point < c.salary_min:
            return False
    if c.salary_max is not None:
        lower_or_point = job_min if job_min is not None else job_max
        if lower_or_point is not None and lower_or_point > c.salary_max:
            return False
    return True


def _norm_loc_city(loc: str | None) -> str:
    return _norm_token(loc)


def _location_matches(job: NormalizedJob, requested: str) -> bool:
    """Deterministic location match.

    Matches when the requested location token appears as a whole word in the
    job's normalized city or full location text. It never matches merely
    because two cities share a region (e.g. Pune vs Mumbai both in Maharashtra)
    — only an actual city/term match passes.
    """
    req = _norm_token(requested)
    if not req:
        return True
    haystacks = [
        _norm_loc_city(job.city),
        _norm_loc_city(job.location),
    ]
    for hay in haystacks:
        if not hay:
            continue
        if re.search(rf"(?<![a-z]){re.escape(req)}(?![a-z])", hay):
            return True
    return False


def _skill_present(
    token: str, job_skills: set[str], job_text: str, _seen: dict[str, bool]
) -> bool:
    """Whether a normalized skill token is present in a job.

    Structured ``job.skills`` match exactly. Free-text scanning is used only
    for multi-character tokens: a single-character token (e.g. 'c') would
    false-positive too easily against arbitrary description text (the 'c' in
    "acquisitions"), so it may only match against authoritative structured
    skills.
    """
    if token in _seen:
        return _seen[token]
    result = False
    if token in job_skills:
        result = True
    elif len(token) <= 1:
        result = False
    else:
        result = re.search(rf"(?<![a-z]){re.escape(token)}(?![a-z])", job_text) is not None
    _seen[token] = result
    return result


def _job_has_all_skills(job: NormalizedJob, requested: list[str]) -> bool:
    req = [_norm_token(x) for x in requested if x and _norm_token(x)]
    if not req:
        return True
    job_skills = {_norm_token(s) for s in (job.skills or [])}
    job_text = (" ".join([_norm_token(job.title),
                          _norm_token(job.category or ""),
                          _clean(job.description or "")[:500]]).lower())
    seen: dict[str, bool] = {}
    for r in req:
        if not _skill_present(r, job_skills, job_text, seen):
            return False
    return True


def _job_has_any_skill(job: NormalizedJob, requested: list[str]) -> bool:
    req = [_norm_token(x) for x in requested if x and _norm_token(x)]
    if not req:
        return True
    job_skills = {_norm_token(s) for s in (job.skills or [])}
    job_text = (" ".join([_norm_token(job.title),
                          _norm_token(job.category or ""),
                          _clean(job.description or "")[:500]]).lower())
    seen: dict[str, bool] = {}
    for r in req:
        if _skill_present(r, job_skills, job_text, seen):
            return True
    return False


def apply_filters(jobs: Iterable[NormalizedJob], criteria: SearchCriteria) -> list[NormalizedJob]:
    """Filter normalized jobs against the common-layer criteria.

    Returns a new list. Only criteria that can be reliably evaluated from
    normalized job data are applied; the rest are no-ops (they were either
    already handled upstream by a provider that supports them, or are
    documented as unsupported).

    Missing-data policy:
    * location  : a job with no location fails an explicit location filter.
    * work mode : a job whose mode is unknown fails an explicit work-mode filter.
    * employment_type: a job with unspecified type fails an explicit filter.
    * experience: a job with unspecified level fails an explicit filter.
    * internship: uses classify_internship() when requested.
    * posted_after: a job with no posted_at fails an explicit posted_after filter.
    * salary_min/max: a job with no salary fails an explicit salary filter.
    * category / skills: a job that cannot be evaluated fails the filter.
    """
    result: list[NormalizedJob] = []
    for job in jobs:
        if not _passes(job, criteria):
            continue
        result.append(job)
    return result


def _passes(job: NormalizedJob, c: SearchCriteria) -> bool:
    # Location
    if c.locations:
        matched_any = False
        for loc in c.locations:
            if _location_matches(job, loc):
                matched_any = True
                break
        if not matched_any:
            return False

    # Work mode
    if c.remote is not None:
        # An explicit remote=True filter keeps remote/hybrid (both allow remote
        # work); remote=False keeps hybrid/onsite. Unknown modes fail.
        if c.remote is True:
            if job.work_mode not in ("remote", "hybrid"):
                return False
        else:
            if job.work_mode not in ("hybrid", "onsite"):
                return False

    # Employment type
    if c.employment_type:
        expected = _norm_token(c.employment_type)
        if _norm_token(job.employment_type or "") != expected:
            return False

    # Experience level
    if c.experience_level:
        expected = _norm_token(c.experience_level)
        if _norm_token(job.experience_level or "") != expected:
            return False

    # Internship
    if c.internship_only is not None:
        is_intern = classify_internship(job)
        if c.internship_only is True and not is_intern:
            return False
        if c.internship_only is False and is_intern:
            return False

    # Posted after
    if c.posted_after:
        bound = parse_iso_datetime(c.posted_after)
        job_posted = parse_iso_datetime(job.posted_at)
        if bound is not None and (job_posted is None or job_posted < bound):
            return False

    # Salary minimum / maximum
    if c.salary_min is not None or c.salary_max is not None:
        if not _salary_comparable(job, c):
            return False
        if not _salary_boundaries_ok(job, c):
            return False

    # Categories
    if c.categories:
        job_cats = [_norm_token(job.category or "")]
        ok = False
        for cat in c.categories:
            cc = _norm_token(cat)
            if not cc:
                continue
            if any(cc == jc or (jc and cc in jc) for jc in job_cats):
                ok = True
                break
        if not ok:
            return False

    # Skills
    if c.skills:
        if c.skills_match == "all":
            if not _job_has_all_skills(job, c.skills):
                return False
        else:
            if not _job_has_any_skill(job, c.skills):
                return False

    return True


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------

def _sort_key_newest(job: NormalizedJob):
    return (-_epoch(parse_iso_datetime(job.posted_at)) if job.posted_at else 0)


def _epoch(dt: datetime | None) -> int:
    if dt is None:
        return 0
    try:
        return int(dt.timestamp())
    except (OverflowError, OSError, ValueError):
        return 0


def _salary_sort_value(job: NormalizedJob) -> int | None:
    """Sort comparator value: salary_max when present, else salary_min."""
    if job.salary_max is not None:
        return job.salary_max
    return job.salary_min


def _salary_sort_missing(job: NormalizedJob) -> int:
    """A job is 'missing' for salary sorting only when it has no boundary."""
    return 0 if (_salary_sort_value(job) is not None) else 1


#: Deterministic grouping order for salary sorting so that jobs with a known,
#: compatible pay period are kept together and not interleaved by raw value
#: with jobs of a different period. Unknown-per-period jobs sort last.
_PERIOD_RANK = {
    "annual": 0,
    "monthly": 1,
    "weekly": 2,
    "daily": 3,
    "hourly": 4,
    "unknown": 5,
}


def apply_sort(jobs: Sequence[NormalizedJob], sort: str | None) -> list[NormalizedJob]:
    """Deterministically sort normalized jobs.

    Supported modes:
      - newest  : posted_at descending (missing last)
      - oldest  : posted_at ascending (missing last)
      - salary  : salary_max descending (missing last)
      - relevance / default (None): no reordering (provider order preserved)

    Deterministic tie-breaking: posted_at, then source, then external_id.
    Missing values never crash or produce unstable ordering.
    """
    mode = (sort or "relevance").lower()
    if mode not in SORT_MODES:
        mode = "relevance"

    ordered = list(jobs)

    if mode == "newest":
        ordered.sort(
            key=lambda j: (_epoch(parse_iso_datetime(j.posted_at)) == 0,
                           -_epoch(parse_iso_datetime(j.posted_at)),
                           j.source, j.external_id),
        )
    elif mode == "oldest":
        ordered.sort(
            key=lambda j: (_epoch(parse_iso_datetime(j.posted_at)) == 0,
                           _epoch(parse_iso_datetime(j.posted_at)),
                           j.source, j.external_id),
        )
    elif mode == "salary":
        # Group by known pay period (annual first ... unknown last) so jobs of
        # one period are not interleaved with jobs of another by raw value,
        # then order by salary within each period group (missing last).
        ordered.sort(
            key=lambda j: (
                _PERIOD_RANK.get(_canonical_period(getattr(j, "salary_period", None)), 5),
                _salary_sort_missing(j),
                -(_salary_sort_value(j) or 0),
                j.source, j.external_id,
            ),
        )

    return ordered


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------
def run_pipeline(
    jobs: Iterable[NormalizedJob],
    criteria: SearchCriteria,
    sort: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> dict:
    """Run normalization -> filtering -> sorting -> pagination.

    Args:
        jobs: raw NormalizedJob objects (as returned by providers).
        criteria: canonical search criteria (filters applied here).
        sort: override sort mode (defaults to criteria.sort).
        page / page_size: final (post-filter) pagination offsets over the
            globally filtered, sorted result set.

    Returns:
        dict with:
          jobs:         filtered+sorted list.
          total:        number of jobs before final pagination slicing.
          filters_applied: list of filter names that were evaluated.
    """
    normalized = normalize_jobs(jobs)
    filtered = apply_filters(normalized, criteria)
    mode = sort if sort is not None else criteria.sort
    sorted_jobs = apply_sort(filtered, mode)

    total = len(sorted_jobs)

    filters_applied = []
    if criteria.locations:
        filters_applied.append("location")
    if criteria.remote is not None:
        filters_applied.append("work_mode")
    if criteria.employment_type:
        filters_applied.append("employment_type")
    if criteria.experience_level:
        filters_applied.append("experience_level")
    if criteria.internship_only is not None:
        filters_applied.append("internship")
    if criteria.posted_after:
        filters_applied.append("posted_after")
    if criteria.salary_min is not None or criteria.salary_max is not None:
        filters_applied.append("salary")
    if criteria.categories:
        filters_applied.append("category")
    if criteria.skills:
        filters_applied.append("skills")

    if page is not None and page_size is not None and page_size > 0:
        start = (max(page, 1) - 1) * page_size
        sliced = sorted_jobs[start:start + page_size]
    else:
        sliced = sorted_jobs

    return {
        "jobs": sliced,
        "total": total,
        "filters_applied": filters_applied,
    }
