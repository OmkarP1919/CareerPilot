"""Discovery orchestrator for multi-source job search.

The orchestrator is provider-agnostic: it holds a list of providers that all
implement the common ``BaseJobSource`` interface and drives them uniformly. It
contains NO provider-specific HTTP or parse logic.

Key responsibilities:
- Iterate over all (enabled) providers.
- Isolate per-source failures so a single failing source never fails the whole
  request.
- Preserve bounded timeouts (each provider enforces its own timeout).
- Collect per-source status metadata.
- Optionally run independent providers concurrently (bounded concurrency).
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Sequence

from app.services.job_sources.base import (
    BaseJobSource,
    NormalizedJob,
    SearchCriteria,
    SourceResult,
    SourceStatus,
    SourceUnavailableError,
)

logger = logging.getLogger(__name__)

MAX_CONCURRENCY = 4


class DiscoveryOrchestrator:
    """Runs the same discovery work across N providers and aggregates results."""

    def __init__(self, providers: Sequence[BaseJobSource]):
        self.providers = list(providers)

    def search(self, criteria: SearchCriteria, concurrency: bool = False) -> dict:
        """Execute a search across all providers.

        Args:
            criteria: The normalized search criteria for all providers.
            concurrency: If True, run independent providers concurrently.

        Returns:
            A dict with:
                results: list[SourceResult] for each provider.
                jobs: all normalized jobs aggregated from successful sources.
                errors: collected user-safe error strings for failed sources.
        """
        results: list[SourceResult] = []
        jobs: list[NormalizedJob] = []

        if concurrency and len(self.providers) > 1:
            results, jobs = self._search_concurrent(criteria)
        else:
            for provider in self.providers:
                result = self._search_one(provider, criteria)
                results.append(result)
                if result.status == SourceStatus.SUCCESS:
                    jobs.extend(result.jobs)

        errors = [
            r.error_message
            for r in results
            if r.error_message is not None
        ]

        return {
            "results": results,
            "jobs": jobs,
            "errors": errors,
        }

    def search_filtered(self, criteria: SearchCriteria, concurrency: bool = False) -> dict:
        """Search across all providers, then run the common discovery pipeline.

        This is an OPT-IN extension that does not alter :meth:`search`. After
        aggregating provider results it runs normalization -> filtering ->
        sorting (and optional final pagination) from the common pipeline layer,
        so caller-facing jobs are canonicalized and filtered.

        Returns a dict with:
            results: list[SourceResult] (raw, per-provider).
            raw_jobs: aggregated normalized jobs BEFORE the common pipeline.
            jobs: jobs AFTER normalization + filtering + sorting.
            errors: collected user-safe error strings.
            filters_applied: filters evaluated by the common layer.
        """
        base = self.search(criteria, concurrency=concurrency)
        raw_jobs = base["jobs"]

        from app.services.job_sources.pipeline import run_pipeline

        outcome = run_pipeline(
            raw_jobs,
            criteria,
            page=criteria.page,
            page_size=criteria.page_size,
        )

        return {
            "results": base["results"],
            "raw_jobs": raw_jobs,
            "jobs": outcome["jobs"],
            "total": outcome["total"],
            "filters_applied": outcome["filters_applied"],
            "errors": base["errors"],
        }


    def _search_one(self, provider: BaseJobSource, criteria: SearchCriteria) -> SourceResult:
        """Run a single provider and convert any failure into a SourceResult."""
        if not provider.is_enabled:
            logger.debug("Provider %s is disabled, skipping", provider.name)
            return SourceResult(
                source=provider.name,
                status=SourceStatus.DISABLED,
            )
        try:
            fetched = provider.fetch(criteria)
            return SourceResult(
                source=provider.name,
                status=SourceStatus.SUCCESS,
                jobs=fetched,
            )
        except SourceUnavailableError as e:
            logger.warning("Provider %s unavailable: %s", provider.name, e)
            return SourceResult(
                source=provider.name,
                status=SourceStatus.UNAVAILABLE,
                error_message=f"{provider.name} was temporarily unavailable.",
            )
        except Exception:
            logger.exception("Provider %s search failed", provider.name)
            return SourceResult(
                source=provider.name,
                status=SourceStatus.UNAVAILABLE,
                error_message=f"{provider.name} was temporarily unavailable.",
            )

    def _search_concurrent(self, criteria: SearchCriteria) -> tuple[list[SourceResult], list[NormalizedJob]]:
        """Run all providers concurrently with bounded thread count.

        Results are re-ordered to match provider order so consumers see
        deterministic output even when providers finish in a different order.
        """
        max_workers = min(MAX_CONCURRENCY, len(self.providers))

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(self._search_one, provider, criteria): provider
                for provider in self.providers
            }
            collected: dict[str, SourceResult] = {}
            for future in as_completed(future_map):
                result = future.result()
                collected[result.source] = result

        ordered_results = [collected[p.name] for p in self.providers if p.name in collected]

        jobs: list[NormalizedJob] = []
        for result in ordered_results:
            if result.status == SourceStatus.SUCCESS:
                jobs.extend(result.jobs)

        return ordered_results, jobs
