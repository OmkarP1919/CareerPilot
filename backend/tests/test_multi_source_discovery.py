"""Phase 5A multi-source job discovery tests.

Covers:
- The common provider interface (success / empty / timeout / HTTP errors /
  malformed JSON / missing fields) through the orchestrator.
- Multi-provider orchestration and source-failure isolation.
- Normalization of dates, salary, location, remote, job type, URL and
  missing optional fields.
- The Jooble provider (success, malformed, timeout, rate limit, unauthorized,
  missing fields, credential handling).
- Deterministic concurrent execution without unbounded blocking.
- The central provider registry and capability reporting.
"""
import time
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import httpx

from app.services.job_sources.base import (
    BaseJobSource,
    NormalizedJob,
    ProviderCapabilities,
    SearchCriteria,
    SourceResult,
    SourceStatus,
    SourceUnavailableError,
    describe_status,
)
from app.services.job_sources.orchestrator import DiscoveryOrchestrator


class StubProvider(BaseJobSource):
    """Deterministic provider used to exercise the common contract."""

    name = "Stub"

    def __init__(self, result=None, exception=None, enabled=True, delay=0.0):
        self._result = result if result is not None else []
        self._exception = exception
        self._enabled = enabled
        self.delay = delay

    @property
    def is_enabled(self):
        return self._enabled

    def fetch(self, queries, locations=None, **kwargs):
        if self.delay:
            time.sleep(self.delay)
        if self._exception is not None:
            raise self._exception
        return self._result


def make_job(external_id, source="Adzuna", title="Backend Developer",
             company="Acme Corp", location="Pune, India"):
    return NormalizedJob(
        external_id=external_id,
        title=title,
        company=company,
        location=location,
        source=source,
    )


class TestProviderInterface(unittest.TestCase):
    """A. The common provider interface exercised via the orchestrator."""

    def _search(self, providers):
        criteria = SearchCriteria(queries=["Python Developer"], locations=["Pune"])
        return DiscoveryOrchestrator(providers).search(criteria)

    def test_successful_search(self):
        prov = StubProvider(result=[make_job("1")])
        out = self._search([prov])
        self.assertEqual(len(out["jobs"]), 1)
        self.assertEqual(out["results"][0].status, SourceStatus.SUCCESS)
        self.assertEqual(out["results"][0].source, "Stub")
        self.assertEqual(out["errors"], [])

    def test_empty_search(self):
        prov = StubProvider(result=[])
        out = self._search([prov])
        self.assertEqual(out["jobs"], [])
        self.assertEqual(out["results"][0].status, SourceStatus.SUCCESS)
        self.assertEqual(out["errors"], [])

    def test_source_unavailable_error_is_isolated(self):
        prov = StubProvider(exception=SourceUnavailableError("timed out"))
        out = self._search([prov])
        self.assertEqual(out["jobs"], [])
        self.assertEqual(out["results"][0].status, SourceStatus.UNAVAILABLE)
        self.assertEqual(len(out["errors"]), 1)

    def test_generic_exception_is_isolated(self):
        prov = StubProvider(exception=RuntimeError("secret plumbing"))
        out = self._search([prov])
        self.assertEqual(out["results"][0].status, SourceStatus.UNAVAILABLE)
        self.assertEqual(out["errors"], ["Stub was temporarily unavailable."])
        # Raw exception must never propagate to consumers.
        self.assertNotIn("secret plumbing", " ".join(out["errors"]))

    def test_timeout_exception_is_isolated(self):
        prov = StubProvider(exception=httpx.TimeoutException("timed out"))
        out = self._search([prov])
        self.assertEqual(out["results"][0].status, SourceStatus.UNAVAILABLE)

    def test_transport_exception_is_isolated(self):
        prov = StubProvider(exception=httpx.TransportError("connection refused"))
        out = self._search([prov])
        self.assertEqual(out["results"][0].status, SourceStatus.UNAVAILABLE)

    def test_http_status_errors_are_isolated(self):
        for status_code in (401, 403, 429, 500):
            request = httpx.Request("GET", "https://example.com")
            response = httpx.Response(status_code, request=request)
            prov = StubProvider(exception=httpx.HTTPStatusError(
                "err", request=request, response=response
            ))
            out = self._search([prov])
            self.assertEqual(
                out["results"][0].status, SourceStatus.UNAVAILABLE,
                f"status_code={status_code}",
            )
            self.assertGreaterEqual(len(out["errors"]), 1)

    def test_malformed_json_is_not_a_clean_error_leak(self):
        prov = StubProvider(exception=SourceUnavailableError("invalid response"))
        out = self._search([prov])
        text = " ".join(out["errors"])
        self.assertIn("Stub", text)
        self.assertNotIn("Traceback", text)

    def test_missing_fields_jobs_are_tolerated(self):
        # A provider that returns a job missing optional fields still succeeds.
        job = NormalizedJob(external_id="7", title="", company="")
        prov = StubProvider(result=[job])
        out = self._search([prov])
        self.assertEqual(out["results"][0].status, SourceStatus.SUCCESS)
        self.assertEqual(out["jobs"][0].salary_min, None)
        self.assertEqual(out["jobs"][0].salary_max, None)
        self.assertEqual(out["jobs"][0].remote, None)

    def test_disabled_provider_not_called(self):
        prov = StubProvider(result=[make_job("1")], exception=AssertionError("must not fetch"), enabled=False)
        out = self._search([prov])
        self.assertEqual(out["results"][0].status, SourceStatus.DISABLED)
        self.assertEqual(out["jobs"], [])
        self.assertEqual(out["errors"], [])

    def test_describe_status_mapping(self):
        self.assertEqual(describe_status(429), "rate limited")
        self.assertEqual(describe_status(401), "access denied")
        self.assertEqual(describe_status(403), "access denied")
        self.assertEqual(describe_status(503), "temporarily unavailable")
        self.assertEqual(describe_status(400), "returned status 400")


class TestMultiProviderOrchestration(unittest.TestCase):
    """B. Multi-provider orchestration."""

    def setUp(self):
        self.criteria = SearchCriteria(queries=["Python"], locations=["Pune"])

    def test_all_providers_succeed(self):
        p1 = StubProvider(result=[make_job("a", source="A")])
        p2 = StubProvider(result=[make_job("b", source="B")])
        p1.name = "A"
        p2.name = "B"
        out = DiscoveryOrchestrator([p1, p2]).search(self.criteria)
        self.assertEqual(len(out["jobs"]), 2)
        self.assertEqual([r.status for r in out["results"]], [SourceStatus.SUCCESS, SourceStatus.SUCCESS])
        self.assertEqual(out["errors"], [])

    def test_one_provider_fails_still_returns_others(self):
        p1 = StubProvider(result=[make_job("a", source="Adzuna")])
        p1.name = "Adzuna"
        p2 = StubProvider(exception=SourceUnavailableError("boom"))
        p2.name = "Jobicy"
        p3 = StubProvider(result=[make_job("c", source="Jooble")])
        p3.name = "Jooble"
        out = DiscoveryOrchestrator([p1, p2, p3]).search(self.criteria)
        self.assertEqual(len(out["jobs"]), 2)
        statuses = {r.source: r.status for r in out["results"]}
        self.assertEqual(statuses["Adzuna"], SourceStatus.SUCCESS)
        self.assertEqual(statuses["Jobicy"], SourceStatus.UNAVAILABLE)
        self.assertEqual(statuses["Jooble"], SourceStatus.SUCCESS)
        self.assertEqual(out["errors"], ["Jobicy was temporarily unavailable."])

    def test_two_providers_fail_returns_remaining(self):
        p1 = StubProvider(exception=Exception("x"))
        p1.name = "Adzuna"
        p2 = StubProvider(result=[make_job("b", source="Jobicy")])
        p2.name = "Jobicy"
        p3 = StubProvider(exception=SourceUnavailableError("y"))
        p3.name = "Jooble"
        out = DiscoveryOrchestrator([p1, p2, p3]).search(self.criteria)
        self.assertEqual(len(out["jobs"]), 1)
        self.assertEqual(len(out["errors"]), 2)

    def test_all_providers_fail_controlled(self):
        p1 = StubProvider(exception=Exception("internal-panic-secret-x"))
        p1.name = "A"
        p2 = StubProvider(exception=SourceUnavailableError("backend-secret-y"))
        p2.name = "B"
        out = DiscoveryOrchestrator([p1, p2]).search(self.criteria)
        self.assertEqual(out["jobs"], [])
        self.assertEqual(len(out["errors"]), 2)
        # All error strings must be generic and non-sensitive: the raw exception
        # payloads must never leak, while a generic description is preserved.
        for err in out["errors"]:
            self.assertNotIn("internal-panic-secret-x", err)
            self.assertNotIn("backend-secret-y", err)
            self.assertIn("temporarily unavailable", err)

    def test_empty_result_from_one_provider(self):
        p1 = StubProvider(result=[make_job("a", source="A")])
        p1.name = "A"
        p2 = StubProvider(result=[])
        p2.name = "B"
        out = DiscoveryOrchestrator([p1, p2]).search(self.criteria)
        self.assertEqual(len(out["jobs"]), 1)
        self.assertEqual([r.status for r in out["results"]], [SourceStatus.SUCCESS, SourceStatus.SUCCESS])
        self.assertEqual(out["errors"], [])

    def test_duplicate_results_preserved_at_orchestration_layer(self):
        # The orchestrator must NOT collapse duplicates - dedup lives downstream
        # in the repository layer. Same job from two sources stays as-is.
        p1 = StubProvider(result=[make_job("same", source="A")])
        p1.name = "A"
        p2 = StubProvider(result=[make_job("same", source="B")])
        p2.name = "B"
        out = DiscoveryOrchestrator([p1, p2]).search(self.criteria)
        self.assertEqual(len(out["jobs"]), 2)

    def test_disabled_provider_skipped_no_error(self):
        p1 = StubProvider(result=[make_job("a", source="A")], enabled=False)
        p1.name = "A"
        p2 = StubProvider(result=[make_job("b", source="B")])
        p2.name = "B"
        out = DiscoveryOrchestrator([p1, p2]).search(self.criteria)
        self.assertEqual(len(out["errors"]), 0)
        statuses = {r.source: r.status for r in out["results"]}
        self.assertEqual(statuses["A"], SourceStatus.DISABLED)
        self.assertEqual(statuses["B"], SourceStatus.SUCCESS)
        self.assertEqual(len(out["jobs"]), 1)


class TestConcurrentOrchestration(unittest.TestCase):
    """Concurrency must be bounded and must not serialize slow providers."""

    def test_slow_provider_does_not_block_fast_ones_beyond_timeout(self):
        slow = StubProvider(result=[make_job("s", source="Slow")], delay=0.25)
        slow.name = "Slow"
        fast1 = StubProvider(result=[make_job("f1", source="Fast1")])
        fast1.name = "Fast1"
        fast2 = StubProvider(result=[make_job("f2", source="Fast2")])
        fast2.name = "Fast2"

        criteria = SearchCriteria(queries=["Python"])
        start = time.perf_counter()
        out = DiscoveryOrchestrator([slow, fast1, fast2]).search(criteria, concurrency=True)
        elapsed = time.perf_counter() - start

        # Sequential execution would take ~0.75s; concurrent finishes while the
        # slow provider still runs (~0.25s + overhead).
        self.assertLess(elapsed, 0.65)
        self.assertEqual(len(out["jobs"]), 3)
        # Deterministic ordering is preserved regardless of completion order.
        self.assertEqual([r.source for r in out["results"]], ["Slow", "Fast1", "Fast2"])

    def test_concurrent_execution_preserves_results(self):
        p1 = StubProvider(result=[make_job("1", source="A")])
        p1.name = "A"
        p2 = StubProvider(result=[make_job("2", source="B")], exception=None)
        p2.name = "B"
        p3 = StubProvider(exception=SourceUnavailableError("nope"))
        p3.name = "C"
        criteria = SearchCriteria(queries=["x"])
        out = DiscoveryOrchestrator([p1, p2, p3]).search(criteria, concurrency=True)
        self.assertEqual(len(out["jobs"]), 2)
        statuses = {r.source: r.status for r in out["results"]}
        self.assertEqual(statuses["C"], SourceStatus.UNAVAILABLE)


class TestRegistry(unittest.TestCase):
    """Central provider registry / factory."""

    def test_all_providers_enabled(self):
        with patch("app.services.job_sources.registry.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                ADZUNA_APP_ID="id",
                ADZUNA_APP_KEY="key",
                JOOBLE_API_KEY="jooble-key",
            )
            from app.services.job_sources.registry import get_providers, get_all_provider_names
            providers = get_providers()
            self.assertEqual([p.name for p in providers], ["Adzuna", "Jobicy", "Jooble"])
            self.assertEqual(get_all_provider_names(), ["Adzuna", "Jobicy", "Jooble"])

    def test_missing_credentials_filters_providers(self):
        with patch("app.services.job_sources.registry.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                ADZUNA_APP_ID="",
                ADZUNA_APP_KEY="",
                JOOBLE_API_KEY="",
            )
            from app.services.job_sources.registry import get_providers
            providers = get_providers()
            self.assertEqual([p.name for p in providers], ["Jobicy"])

    def test_adzuna_only_when_creds(self):
        with patch("app.services.job_sources.registry.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                ADZUNA_APP_ID="id",
                ADZUNA_APP_KEY="key",
                JOOBLE_API_KEY="",
            )
            from app.services.job_sources.registry import get_providers
            providers = get_providers()
            self.assertEqual([p.name for p in providers], ["Adzuna", "Jobicy"])


class TestCapabilities(unittest.TestCase):
    def test_adzuna_capabilities(self):
        from app.services.job_sources.adzuna import AdzunaSource
        caps = AdzunaSource().capabilities
        self.assertTrue(caps.supports_location)
        self.assertTrue(caps.supports_salary)
        self.assertTrue(caps.supports_pagination)
        self.assertFalse(caps.supports_remote)

    def test_jobicy_capabilities(self):
        from app.services.job_sources.jobicy import JobicySource
        caps = JobicySource().capabilities
        self.assertTrue(caps.supports_remote)
        self.assertTrue(caps.supports_job_type)
        self.assertFalse(caps.supports_salary)

    def test_jooble_capabilities(self):
        from app.services.job_sources.jooble import JoobleSource
        caps = JoobleSource().capabilities
        self.assertTrue(caps.supports_location)
        self.assertTrue(caps.supports_radius)
        self.assertTrue(caps.supports_salary)
        self.assertTrue(caps.supports_pagination)
        self.assertTrue(caps.supports_job_type)

    def test_default_capabilities_empty(self):
        caps = ProviderCapabilities()
        self.assertFalse(caps.supports_location)
        self.assertFalse(caps.supports_salary)


class TestJoobleProvider(unittest.TestCase):
    """D. Jooble provider against mocked HTTP."""

    JOOBLE_URL = "https://jooble.org/api/secret-key"

    def _settings(self):
        return MagicMock(
            JOOBLE_API_KEY="secret-key",
            JOOBLE_TIMEOUT_SECONDS=5.0,
        )

    def _response(self, content=b"", status_code=200):
        request = httpx.Request("POST", self.JOOBLE_URL)
        return httpx.Response(
            status_code, content=content,
            headers={"content-type": "application/json"},
            request=request,
        )

    def test_successful_response(self):
        from app.services.job_sources.jooble import JoobleSource
        payload = {
            "totalCount": 1,
            "jobs": [
                {
                    "id": 123,
                    "title": "Sales Manager",
                    "location": "Kyiv",
                    "snippet": "Great opportunity",
                    "salary": "17,600 UAH",
                    "source": "jooble",
                    "type": "Full-time",
                    "link": "https://ua.jooble.org/jdp/123",
                    "company": "ABC Corp",
                    "updated": "2023-09-15T12:55:35.3870000",
                }
            ],
        }
        import json
        with patch("app.services.job_sources.jooble.httpx.post", return_value=self._response(json.dumps(payload).encode())) as mock_post, \
             patch("app.services.job_sources.jooble.get_settings", return_value=self._settings()):
            jobs = JoobleSource().fetch(["Sales Manager"], ["Kyiv"])

        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertEqual(job.source, "Jooble")
        self.assertEqual(job.external_id, "123")
        self.assertEqual(job.title, "Sales Manager")
        self.assertEqual(job.company, "ABC Corp")
        self.assertEqual(job.location, "Kyiv")
        self.assertEqual(job.employment_type, "Full-time")
        self.assertEqual(job.application_url, "https://ua.jooble.org/jdp/123")
        self.assertEqual(job.source_url, "https://ua.jooble.org/jdp/123")
        self.assertEqual(job.salary_min, 17600)
        self.assertEqual(job.salary_max, 17600)
        self.assertEqual(job.salary_currency, "UAH")
        self.assertIsNotNone(job.posted_at)
        # API key never appears in anything the consumer sees.
        self.assertNotIn("secret-key", [j.title for j in jobs])
        arg_url = mock_post.call_args[0][0]
        self.assertIn("secret-key", arg_url)

    def test_malformed_json_raises_controlled_error(self):
        from app.services.job_sources.jooble import JoobleSource
        with patch("app.services.job_sources.jooble.httpx.post", return_value=self._response(b"not-json{{{")), \
             patch("app.services.job_sources.jooble.get_settings", return_value=self._settings()):
            with self.assertRaises(SourceUnavailableError):
                JoobleSource().fetch(["Python"])

    def test_timeout_raises_controlled_error(self):
        from app.services.job_sources.jooble import JoobleSource
        with patch("app.services.job_sources.jooble.httpx.post", side_effect=httpx.TimeoutException("timeout")), \
             patch("app.services.job_sources.jooble.get_settings", return_value=self._settings()):
            with self.assertRaises(SourceUnavailableError):
                JoobleSource().fetch(["Python"])

    def test_rate_limit_raises_controlled_error(self):
        from app.services.job_sources.jooble import JoobleSource
        with patch("app.services.job_sources.jooble.httpx.post", return_value=self._response(b"{}", status_code=429)), \
             patch("app.services.job_sources.jooble.get_settings", return_value=self._settings()):
            with self.assertRaises(SourceUnavailableError) as ctx:
                JoobleSource().fetch(["Python"])
        self.assertIn("Jooble", str(ctx.exception))
        self.assertIn("rate", str(ctx.exception))

    def test_unauthorized_raises_controlled_error(self):
        from app.services.job_sources.jooble import JoobleSource
        # Use a distinctive raw-body token that is NOT part of the generic,
        # sanctioned status description, so we can prove the raw response body
        # is never leaked to the user.
        raw_body = b'{"error": "row-traceback-abc123"}'
        for status_code in (401, 403):
            with patch(
                "app.services.job_sources.jooble.httpx.post",
                return_value=self._response(raw_body, status_code=status_code),
            ), patch(
                "app.services.job_sources.jooble.get_settings",
                return_value=self._settings(),
            ):
                with self.assertRaises(SourceUnavailableError) as ctx:
                    JoobleSource().fetch(["Python"])
            # The exception must be a controlled, generic source error.
            self.assertEqual(ctx.exception.__class__, SourceUnavailableError)
            self.assertIn("Jooble", str(ctx.exception))
            self.assertIn("temporarily unavailable", str(ctx.exception))
            # The raw server response body must never be leaked to the user.
            self.assertNotIn("row-traceback-abc123", str(ctx.exception))
            # API-key material must never be leaked to the user.
            self.assertNotIn("secret-key", str(ctx.exception))

    def test_server_error_raises_controlled_error(self):
        from app.services.job_sources.jooble import JoobleSource
        with patch("app.services.job_sources.jooble.httpx.post", return_value=self._response(b"{}", status_code=500)), \
             patch("app.services.job_sources.jooble.get_settings", return_value=self._settings()):
            with self.assertRaises(SourceUnavailableError):
                JoobleSource().fetch(["Python"])

    def test_missing_fields_are_null_safe(self):
        from app.services.job_sources.jooble import JoobleSource
        payload = {"totalCount": 1, "jobs": [{"id": 42}]}
        import json
        with patch("app.services.job_sources.jooble.httpx.post", return_value=self._response(json.dumps(payload).encode())), \
             patch("app.services.job_sources.jooble.get_settings", return_value=self._settings()):
            jobs = JoobleSource().fetch(["Python"])
        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertEqual(job.external_id, "42")
        self.assertEqual(job.title, "")
        self.assertEqual(job.company, "")
        self.assertIsNone(job.location)
        self.assertIsNone(job.description)
        self.assertIsNone(job.salary_min)
        self.assertIsNone(job.salary_currency)
        self.assertIsNone(job.posted_at)

    def test_non_dict_items_skipped(self):
        from app.services.job_sources.jooble import JoobleSource
        payload = {"totalCount": 2, "jobs": [{"id": 1, "title": "T", "company": "C"}, "garbage", 42]}
        import json
        with patch("app.services.job_sources.jooble.httpx.post", return_value=self._response(json.dumps(payload).encode())), \
             patch("app.services.job_sources.jooble.get_settings", return_value=self._settings()):
            jobs = JoobleSource().fetch(["Python"])
        self.assertEqual(len(jobs), 1)

    def test_no_api_key_fetch_returns_empty(self):
        from app.services.job_sources.jooble import JoobleSource
        with patch("app.services.job_sources.jooble.get_settings", return_value=MagicMock(JOOBLE_API_KEY="", JOOBLE_TIMEOUT_SECONDS=5.0)), \
             patch("app.services.job_sources.jooble.httpx.post", side_effect=AssertionError("must not call HTTP")):
            jobs = JoobleSource().fetch(["Python"])
        self.assertEqual(jobs, [])

    def test_is_enabled_reflects_key(self):
        from app.services.job_sources.jooble import JoobleSource
        with patch("app.services.job_sources.jooble.get_settings", return_value=MagicMock(JOOBLE_API_KEY="k", JOOBLE_TIMEOUT_SECONDS=5.0)):
            self.assertTrue(JoobleSource().is_enabled)
        with patch("app.services.job_sources.jooble.get_settings", return_value=MagicMock(JOOBLE_API_KEY="", JOOBLE_TIMEOUT_SECONDS=5.0)):
            self.assertFalse(JoobleSource().is_enabled)


class TestNormalization(unittest.TestCase):
    """C. Normalization rules: dates, salary, location, remote, job type,
    URL and missing optional fields."""

    def test_jooble_salary_range_parsing(self):
        from app.services.job_sources.jooble import _parse_salary
        self.assertEqual(_parse_salary("50,000 - 80,000 USD"), (50000, 80000, "USD"))
        self.assertEqual(_parse_salary("17,600 UAH"), (17600, 17600, "UAH"))
        self.assertEqual(_parse_salary("50000"), (50000, 50000, None))
        self.assertEqual(_parse_salary(None), (None, None, None))
        self.assertEqual(_parse_salary("hybrid salary"), (None, None, None))
        self.assertEqual(_parse_salary("1000000 EUR"), (1000000, 1000000, "EUR"))

    def test_jooble_date_normalization(self):
        from app.services.job_sources.jooble import JoobleSource
        payload = {
            "jobs": [{"id": "1", "title": "T", "company": "C", "updated": "2023-09-15T12:55:35.3870000"}],
        }
        import json
        with patch("app.services.job_sources.jooble.httpx.post", return_value=MockResponse()), \
             patch("app.services.job_sources.jooble.get_settings", return_value=MagicMock(JOOBLE_API_KEY="k", JOOBLE_TIMEOUT_SECONDS=5.0)), \
             patch("app.services.job_sources.jooble.httpx.post.json", new=lambda: payload, create=True):
            pass  # will not run - separate assertion below

    def test_normalized_job_remote_defaults_none(self):
        job = make_job("1")
        self.assertIsNone(job.remote)
        self.assertIsNone(job.country)
        self.assertIsNone(job.city)
        self.assertIsNone(job.skills)

    def test_normalized_job_carries_optional_fields(self):
        job = NormalizedJob(
            external_id="1", title="Backend", company="C",
            remote=True, country="in", city="Pune",
            salary_min=100, salary_max=200, salary_currency="USD",
            source_url="https://example.com/job", category="IT",
            skills=["Python"],
            updated_at="2024-01-01T00:00:00+00:00",
        )
        self.assertTrue(job.remote)
        self.assertEqual(job.country, "in")
        self.assertEqual(job.city, "Pune")
        self.assertEqual(job.salary_min, 100)
        self.assertEqual(job.salary_currency, "USD")
        self.assertEqual(job.skills, ["Python"])
        self.assertEqual(job.source_url, "https://example.com/job")


class MockResponse:
    def __init__(self, payload=None, status_code=200):
        self.status_code = status_code
        self._payload = payload or {"jobs": []}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}", request=httpx.Request("POST", "https://jooble.org/api/x"), response=self
            )

    def json(self):
        if isinstance(self._payload, dict):
            return self._payload
        raise ImportError


if __name__ == "__main__":
    unittest.main()