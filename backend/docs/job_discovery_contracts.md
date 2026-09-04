# Job Discovery — Hardened Provider Contracts (Phase 5A.1)

This document is the authoritative reference for the multi-source job discovery
architecture. It defines the canonical provider contract that every job source
adapter, the orchestrator and the registry must honor, plus the design rules we
apply and the features deliberately deferred to later phases.

Module: `backend/app/services/job_sources/`

## 1. Canonical contracts (in `base.py`)

### `SearchCriteria` — the provider contract

`SearchCriteria` is the **only** object a provider receives. It is the canonical,
provider-neutral search request and carries the union of filter dimensions the
discovery system cares about:

| Field             | Type             | Meaning                                              |
|-------------------|------------------|------------------------------------------------------|
| `queries`         | `list[str]`      | Free-text keywords / role terms (always expected).   |
| `locations`       | `list[str] \| None` | Location / city terms.                             |
| `country`         | `str \| None`    | ISO 3166-1 alpha-2 country code, when known.         |
| `radius`          | `str \| None`    | Search radius (provider-specific unit).              |
| `remote`          | `bool \| None`   | Restrict to remote roles.                            |
| `employment_type` | `str \| None`    | e.g. `"Full-time"`, `"Part-time"`, `"Contract"`.     |
| `experience_level`| `str \| None`    | e.g. `"entry"`, `"mid"`, `"senior"`.                 |
| `internship_only` | `bool \| None`   | `True` keep internships only, `False` exclude, `None` no constraint. |
| `posted_after`    | `str \| None`    | ISO-8601 bound: only jobs posted at/after this time. |
| `salary_min`      | `int \| None`    | Minimum salary amount.                               |
| `salary_max`      | `int \| None`    | Maximum salary amount.                               |
| `salary_period`   | `str \| None`    | Optional canonical pay period (`annual`/`monthly`/`weekly`/`daily`/`hourly`). When set, salary filters apply ONLY to jobs declaring the SAME period; incompatible/unknown periods are refused (never converted). `None` → legacy numeric fallback. |
| `salary_currency` | `str \| None`    | Optional ISO 4217 currency. When set, only jobs declaring that exact currency are salary-compared (never converted). `None` → no currency gate. |
| `page` / `page_size` | `int`         | 1-based pagination.                                  |
| `sort`            | `str \| None`    | Ordering hint (provider-specific).                   |
| `categories`      | `list[str] \| None` | Category / sector terms.                          |
| `skills`          | `list[str] \| None` | Required skill keywords.                          |
| `skills_match`    | `Literal["any","all"]` | Skill filter match mode (default `"any"`).     |

Design rule: providers read ONLY this object. No loose provider-specific
`**kwargs` are allowed to cross the provider boundary.

### `ProviderCapabilities` — what a provider ACTUALLY applies

A capability is `True` only when the corresponding `SearchCriteria` field is
genuinely passed/used by the adapter's current request code — **not** merely
because the upstream API documentation mentions it. This is the metadata the
future application-layer filter engine uses to decide which filters must be
applied CareerPilot-side after a provider returns jobs.

Current honest capabilities:

| Provider | Supported (passes upstream) |
|----------|------------------------------|
| Adzuna   | `supports_location`, `supports_pagination` |
| Jobicy   | *(none — keyword/tag search only)* |
| Jooble   | `supports_location` |

Anything not listed above is `False` by design, even when the upstream API
documents it, until an adapter actually passes it.

### `NormalizedJob` — canonical job record

All adapters return `NormalizedJob` with these freshness/time semantics:

* `posted_at` — when the source says the job was **posted** (ISO-8601).
* `updated_at` — when the source says the listing was **updated** (ISO-8601),
  or `None` when the source provides no distinct update time.
* `fetched_at` — when CareerPilot retrieved it (not a field on `NormalizedJob`).

**Freshness rule:** never substitute `fetched_at` for `posted_at`. Keep
`posted_at` populated from the source's own posting/update timestamp.

Jooble exposes a single `updated` timestamp and no distinct `posted` timestamp.
We map it to `posted_at` as a documented pragmatic proxy (keeps recency ranking
working) and leave `updated_at` as `None`.

`NormalizedJob` also carries `external_id`, `title`, `company`, `location`,
`city`, `country`, `description`, `employment_type`, `experience_level`,
`application_url`, `source_url`, `source`, `remote`, `work_mode`,
`salary_min/max/currency/period`, `category`, `skills`, and `raw_data` (retained
for debugging only; never shown to users).

`work_mode` is an additive canonical work classification (`remote`, `hybrid`,
`onsite`, `unspecified`) added in Phase 5B. It does NOT change the legacy
boolean `remote` field — both coexist. `unspecified` means the mode could not
be reliably determined.

Work-mode classification (hardened in 5B.1): `location` is strong evidence and
may classify onsite; `description` is weak evidence and may only strongly
indicate hybrid/remote (bare `office`/`onsite` inside a body of text is ignored
so a field role is not misforced onsite). A source-flagged `remote` boolean is
trusted only as a fallback and is never allowed to override strong
contradictory text — a `remote=True` flag with onsite text (or vice versa) is a
contradiction and resolves to `unspecified`.

### `SourceResult` and `SourceStatus`

`SourceResult` is the per-provider outcome object with `source`, `status`,
`jobs`, `error_message` and `total_count`.

`SourceStatus` values: `SUCCESS`, `UNAVAILABLE`, `RATE_LIMITED`, `UNAUTHORIZED`,
`TIMEOUT`, `MALFORMED_RESPONSE`, `DISABLED`.

Error policy: avoid fake precision. Generic failures map to generic
`UNAVAILABLE`; only a genuinely identified cause uses a more specific status.
All user-facing error strings are sanitized — never raw response bodies, API
keys, stack traces or PII.

## 2. Provider responsibilities

A `BaseJobSource` adapter is responsible ONLY for:

1. reading a `SearchCriteria`,
2. applying the criteria it genuinely supports (per its `capabilities`),
3. returning a list of `NormalizedJob`,
4. bounding every outbound request with a timeout.

It must not be aware of the orchestrator or other providers.
`fetch(self, criteria: SearchCriteria) -> list[NormalizedJob]` is the abstract
interface. `is_enabled` lets a provider report a clean `disabled` status
without attempting a network call when credentials are missing.

## 3. The orchestrator (`DiscoveryOrchestrator`)

* Provider-agnostic; contains no provider-specific HTTP/parse logic.
* Calls `provider.fetch(criteria)` passing the **same** `SearchCriteria` object
  to every provider (no kwargs splitting).
* Isolates per-source failures — one failing source never fails the whole request.
* Bounded concurrency (`MAX_CONCURRENCY = 4`) with deterministic ordering of
  results regardless of completion order.
   * `DISABLED` providers are reported with `SourceStatus.DISABLED` (no fetch).
* Does NOT deduplicate — duplicates live downstream in the repository layer.

## 4. The registry (`registry.py`)

`get_providers()` is the single authoritative factory for **new** callers. It
returns only *configured* providers and silently skips unconfigured ones.
`get_all_provider_names()` returns all known names.

> **Why `personalized_discovery.py` does NOT use the registry:** it constructs
> `[AdzunaSource(), JobicySource(), JoobleSource()]` manually. The registry
> gates out unconfigured providers, which would change the externally visible
> per-source `source_statuses`/`sources_count` (unconfigured sources should
> report `DISABLED` rather than vanish) and would break existing test patches on
> `personalized_discovery.AdzunaSource`/`JobicySource`. New callers that do not
> need the `disabled` status may use `get_providers()`.

## 5. Phase 5B — canonical normalization, filtering & sorting (`pipeline.py`)

Module: `backend/app/services/job_sources/pipeline.py`

### 5.1 Canonical pipeline

```
SearchCriteria -> Provider -> SourceResult / NormalizedJob
               -> normalization -> filtering -> sorting -> final result
```

The discovery layer is fully provider-agnostic. Providers only translate API
responses into `NormalizedJob`; normalization/filtering/sorting live in the
common `pipeline.py`. `DiscoveryOrchestrator.search_filtered()` is the opt-in
entrypoint that runs the pipeline after `search()`; the raw `search()` (used by
`personalized_discovery`) is left unchanged to preserve its external
persistence behavior.

### 5.2 Normalization (deterministic, conservative)

| Dimension | Rule |
|-----------|------|
| Title / Company | collapse whitespace only; never rewrite meaningful text |
| Location | normalize free text; derive `city` + `country` from structured fields first, else from known city/country keywords via `COUNTRY_MAP` |
| Work mode | `remote`, `hybrid`, `onsite`, `unspecified`; location text is strong evidence, description text only strongly signals hybrid/remote, contradictory `remote` flag + text → `unspecified` |
| Employment type | canonical vocabulary: `full-time, part-time, contract, internship, temporary, freelance, volunteer, other, unspecified` |
| Internship | via `employment_type`, `category`, or title terms only (never from description mentions alone) |
| Experience | canonical vocabulary: `internship, entry, junior, mid, senior, lead, manager, director, executive, unspecified`; numeric "N years" → `unspecified` |
| Salary | coerce numeric min/max; **never convert pay periods or currencies**; `salary_period` normalized to the canonical vocabulary (`annual`/`monthly`/`weekly`/`daily`/`hourly`/`unknown`); vague/ambiguous text left unparsed |
| Skills | case/space fold + dedup, first-seen variant preserved; no taxonomy, no LLM. Single-character skills match ONLY authoritative structured skills, never free text |
| Category | conservative canonical map (`engineering` alone is NOT remapped to `software-engineering`); unknown values preserved lowercased or left unset — never hallucinated |
| Dates | parse ISO-8601 to timezone-aware UTC (naive assumed UTC); invalid dates → `None` so they can't crash |

### 5.3 Filtering, AND semantics & missing-data behavior

Filters always AND together: a job must satisfy **every** supplied criterion to
pass. Filters apply ONLY where reliable normalized data exists.

**Missing data never satisfies an explicit constraint**: a job with no salary
fails an explicit salary filter, a job with unknown work mode fails an explicit
work-mode filter, an unknown pay period fails a request that pins a specific
period, etc. (missing salary is never treated as zero, missing remote never as
on-site, an unknown period is never guessed).

Supported filters: `locations` (exact whole-word city/term match — Pune "in
Maharashtra" never matches Mumbai), `remote` (True → remote+hybrid; False →
hybrid+onsite), `employment_type`, `experience_level`, `internship_only`,
`posted_after`, `salary_min`/`salary_max`, `categories`, `skills` (ANY default,
or ALL via `skills_match="all"`).

**Salary / currency compatibility (5B.1):**
* Pay periods are **never converted**. When the request pins a specific
  `salary_period`, only jobs with that same known period are numerically
  compared; a job with a different or unknown period is refused (not converted
  to the request's unit).
* When the request pins **no** period, the legacy numeric fallback applies —
  the request simply did not pin a unit.
* Currencies are **never converted**. A currency gate applies only when the
  request specifies `salary_currency`; then only jobs declaring that exact
  currency are salary-compared. With no request currency, no gate is applied.
* A job exposing only `salary_min` is compared by that lower boundary (min-only
  is not "missing").

### 5.4 Radius limitation

**Radius is NOT implemented.** There are no reliable coordinates in the current
architecture, no geocoding service is introduced, and no distance math is
invented. `SearchCriteria.radius` is carried but never claimed as applied.

### 5.5 Sorting & pagination

Deterministic sorts: `newest` (posted_at desc, missing last), `oldest` (asc,
missing last), `salary`, `relevance`/default (provider order). Tie-break:
`posted_at`, then `source`, then `external_id`.

`salary` sort groups jobs by known pay period (annual → monthly → weekly →
daily → hourly → unknown) then orders by salary within each period group;
"missing" for sorting means a job with **no** salary boundary (a min-only job
sorts by `salary_min` and is not "missing").

Pagination in the common layer is **post-filter, post-sort** slicing over the
globally filtered set — it is explicitly NOT provider pagination. Callers must
not conflate a common-layer `page` with a provider's `page`.

> **Known limitation (double pagination under-fill):** if a caller requests a
> common-layer `page`/`page_size` larger than what a single provider page
> returned, the provider may under-fill and the common layer cannot refill from
> later provider pages. This is documented and out of scope — no false
> refill/rollover behavior is claimed.

## 6. Persistence gap (documented — no DB migration this phase)

The `Job` model persists `external_id`, `title`, `company`, `location`,
`employment_type`, `experience_level`, `description`, `required_skills`,
`application_url`, `source`, `posted_at`, `fetched_at`.

It does **not** yet persist: `country`, `city`, `remote`, `salary_min`,
`salary_max`, `salary_currency`, `updated_at`, `source_url`, `category`, `skills`.

The DB uses `Base.metadata.create_all` with no Alembic. This gap is intentionally
documented here and NOT migrated in this phase because it is out of scope and
would require a schema decision. Job persistence continues to use `posted_at`
for recency ranking.

## 7. Deferred to later phases (NOT implemented here)

* Cross-provider deduplication and ranking (Phase 5C).
* Applying the common normalization/filtering pipeline inside the persistent
  discovery flows (`job_discovery.discover_jobs`,
  `personalized_discovery`) — intentionally NOT wired in Phase 5B to avoid
  altering their externally observable persistence behavior. The opt-in
  `search_filtered()` pipeline is available for new callers.
* Adding new providers, or using registry in `personalized_discovery`.
* DB schema migration to persist the extended `NormalizedJob` fields
  (including `work_mode`).
* Geocoding / radius support.

## 8. Tests

* `tests/test_discovery_pipeline.py` — Phase 5B normalization, filtering,
  sorting, missing-data semantics, radius limitation, and orchestration wiring.
* `tests/test_multi_source_discovery.py` — provider interface, orchestrator,
  concurrency, registry, capabilities, criteria mapping, normalization,
  Jooble/Adzuna/Jobicy providers against mocked HTTP.
* `tests/test_personalized_discovery.py` — end-to-end personalized discovery
  and legacy `discover_jobs` execution.

## 9. Phase 5C - Advanced Job Discovery

Phase 5C adds an additive discovery layer on top of the 5B/5B.1 architecture.
It does NOT modify the canonical matching weights (`matching.py` 50/20/15/10/5)
nor the externally observable behavior of `personalized_discovery`. All new
behavior is opt-in and lives in dedicated modules.

### 9.1 Additive modules

| Module | Purpose |
|--------|---------|
| `app/services/discovery_service.py` | Source selection, unified filtered search, cross-source dedup with provenance, freshness, explainable ranking, saved searches, new-result detection. |
| `app/schemas/discovery.py` | Pydantic request/response models for the new endpoints. |
| `app/api/discovery.py` | New REST endpoints under `/jobs/discovery/*`. |
| `app/models/saved_search.py` | NEW table (never ALTERs an existing table). |

### 9.2 Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/jobs/discovery/filtered` | Unified, source-selectable, deduplicated filtered search. |
| GET  | `/jobs/discovery/sources` | Return the selectable source names. |
| GET  | `/jobs/discovery/saved-searches` | List the current user's saved searches. |
| POST | `/jobs/discovery/saved-searches` | Save the current criteria. |
| POST | `/jobs/discovery/saved-searches/{id}/run` | Replay a saved search and report NEW results. |
| PUT  | `/jobs/discovery/saved-searches/{id}` | Rename / update a saved search. |
| DELETE | `/jobs/discovery/saved-searches/{id}` | Delete a saved search. |

### 9.3 Deterministic canonical identity & cross-source dedup

`canonical_job_key(job)` derives a source-agnostic identity from normalized
title + employer + location (company legal suffixes like `Inc`/`LLC`/`Corp` are
stripped). Dedup merges the same listing across providers into ONE result while
preserving provenance (list of sources and their URLs). Merging is deliberately
conservative: FALSE MERGES ARE WORSE THAN DUPLICATES, so only the strongest
identity signals are used.

### 9.4 Freshness (deterministic, never faked)

A `freshness` label (Today / This week / 2 weeks / This month / 3 months / Older /
unknown) is derived ONLY from `posted_at`. Missing `posted_at` yields `unknown`;
we never substitute fetched time.

### 9.5 Explainable ranking (additive heuristic)

`rank_record()` produces a deterministic profile-alignment score with explicit,
documented sub-scores and human-readable reasons. It uses the EXISTING profile
data (skills, preferred roles, preferred locations). It does NOT call the
canonical `matching.py` and does NOT change its weights. Documented weights:

| Component | Weight |
|-----------|--------|
| Skills alignment  | 50 |
| Preferred-role alignment | 25 |
| Location alignment | 15 |
| Freshness | 10 |

`overall_score` is a weighted average of the four 0-100 sub-scores. Reasons are
always present and explain the score. When `include_profile_alignment=false`,
results are returned deduplicated but unranked.

### 9.6 Saved searches & new-result detection (alert-ready)

A saved search stores canonical criteria JSON. Re-running it stores the set of
canonical job keys seen at the last run (`last_seen_keys`) and reports which
results are NEW since then (`new_results` + per-record `is_new`). This is a
clean base for a future scheduled alert without touching existing tables.

### 9.7 Persistence policy

The existing `jobs` table is NEVER altered (`create_all` does not add columns to
existing tables and there is no Alembic). Saved-search + seen-state live in the
new `saved_searches` table. Cross-source dedup/provenance is computed at the
response level of a discovery run.

### 9.8 Tests

* `tests/test_discovery_service.py` - canonical key, cross-source dedup with
  provenance, source selection, criteria mapping, filtered search with ranking,
  freshness, saved-search CRUD, and new-result detection.
* Existing 5B/5B.1 tests (pipeline, multi_source, personalized) remain green.
