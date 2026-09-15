"""Tests for Remotive provider adapter (Phase 7.0D.2)."""
import unittest
from unittest.mock import MagicMock, patch

import httpx

from app.services.job_sources.base import SearchCriteria, SourceUnavailableError
from app.services.job_sources.remotive import (
    RemotiveSource,
    parse_remotive_salary,
    strip_html,
)


class TestRemotiveSalaryParser(unittest.TestCase):
    def test_range_with_k_and_dollar(self):
        s_min, s_max, curr, period = parse_remotive_salary("$100k - $120k")
        self.assertEqual(s_min, 100000)
        self.assertEqual(s_max, 120000)
        self.assertEqual(curr, "USD")
        self.assertIsNone(period)

    def test_range_with_k_and_annual_period(self):
        s_min, s_max, curr, period = parse_remotive_salary("$90k - $110k / year")
        self.assertEqual(s_min, 90000)
        self.assertEqual(s_max, 110000)
        self.assertEqual(curr, "USD")
        self.assertEqual(period, "annual")

    def test_range_full_numbers_with_commas(self):
        s_min, s_max, curr, period = parse_remotive_salary("$80,000 - $100,000")
        self.assertEqual(s_min, 80000)
        self.assertEqual(s_max, 100000)
        self.assertEqual(curr, "USD")

    def test_single_amount_euro(self):
        s_min, s_max, curr, period = parse_remotive_salary("€60k")
        self.assertEqual(s_min, 60000)
        self.assertEqual(s_max, 60000)
        self.assertEqual(curr, "EUR")

    def test_currency_code_trailing(self):
        s_min, s_max, curr, period = parse_remotive_salary("50000 - 70000 CAD")
        self.assertEqual(s_min, 50000)
        self.assertEqual(s_max, 70000)
        self.assertEqual(curr, "CAD")

    def test_ambiguous_or_unparseable_returns_none(self):
        self.assertEqual(parse_remotive_salary("Competitive"), (None, None, None, None))
        self.assertEqual(parse_remotive_salary("DOE"), (None, None, None, None))
        self.assertEqual(parse_remotive_salary(""), (None, None, None, None))
        self.assertEqual(parse_remotive_salary(None), (None, None, None, None))
        self.assertEqual(parse_remotive_salary("TBD"), (None, None, None, None))


class TestRemotiveProvider(unittest.TestCase):
    def test_strip_html(self):
        html = "<div><p>Looking for a <strong>Full Stack Engineer</strong>.</p></div>"
        self.assertEqual(strip_html(html), "Looking for a Full Stack Engineer.")

    def test_is_enabled_always_true(self):
        source = RemotiveSource()
        self.assertTrue(source.is_enabled)
        self.assertTrue(source.capabilities.supports_location)

    def test_successful_parsing(self):
        payload = {
            "0-legal-notice": "Remotive job data is for non-commercial integration",
            "job-count": 2,
            "jobs": [
                {
                    "id": 54321,
                    "url": "https://remotive.com/remote-jobs/software-dev/senior-python-dev-54321",
                    "title": "Senior Python Developer",
                    "company_name": "Distributed Labs",
                    "category": "Software Development",
                    "tags": ["python", "django", "aws"],
                    "job_type": "full_time",
                    "publication_date": "2026-03-01T08:30:00",
                    "candidate_required_location": "Worldwide",
                    "salary": "$110k - $130k / year",
                    "description": "<p>Build cloud services with Python &amp; AWS.</p>",
                },
                {
                    "id": 98765,
                    "url": "https://remotive.com/remote-jobs/qa/qa-lead-98765",
                    "title": "QA Lead",
                    "company_name": "Quality First",
                    "category": "QA",
                    "tags": ["cypress", "pytest"],
                    "job_type": "contract",
                    "publication_date": "2026-03-02T10:00:00",
                    "candidate_required_location": "Europe",
                    "salary": "",
                    "description": "<div>Lead QA automation.</div>",
                },
            ],
        }

        def fake_get(url, params=None, headers=None, timeout=None):
            return httpx.Response(
                200,
                json=payload,
                request=httpx.Request("GET", url),
            )

        criteria = SearchCriteria(queries=["Python Developer"], locations=["Worldwide"])
        with patch("app.services.job_sources.remotive.httpx.get", side_effect=fake_get):
            jobs = RemotiveSource().fetch(criteria)

        self.assertEqual(len(jobs), 2)

        # Job 1 verification
        j1 = jobs[0]
        self.assertEqual(j1.external_id, "54321")
        self.assertEqual(j1.title, "Senior Python Developer")
        self.assertEqual(j1.company, "Distributed Labs")
        self.assertEqual(j1.location, "Worldwide")
        self.assertEqual(j1.description, "Build cloud services with Python & AWS.")
        self.assertEqual(j1.source, "Remotive")
        self.assertEqual(j1.source_url, "https://remotive.com/remote-jobs/software-dev/senior-python-dev-54321")
        # Explicit user contract: Remotive url is the listing page, NOT direct apply
        self.assertIsNone(j1.application_url)
        self.assertEqual(j1.employment_type, "Full-time")
        self.assertEqual(j1.skills, ["python", "django", "aws"])
        self.assertTrue(j1.remote)
        self.assertEqual(j1.work_mode, "remote")
        self.assertEqual(j1.salary_min, 110000)
        self.assertEqual(j1.salary_max, 130000)
        self.assertEqual(j1.salary_currency, "USD")
        self.assertEqual(j1.salary_period, "annual")
        self.assertEqual(j1.category, "Software Development")
        self.assertIsNotNone(j1.posted_at)

        # Job 2 verification
        j2 = jobs[1]
        self.assertEqual(j2.external_id, "98765")
        self.assertEqual(j2.title, "QA Lead")
        self.assertEqual(j2.company, "Quality First")
        self.assertEqual(j2.employment_type, "Contract")
        self.assertIsNone(j2.salary_min)
        self.assertIsNone(j2.salary_max)
        self.assertIsNone(j2.application_url)
        self.assertTrue(j2.remote)
        self.assertEqual(j2.work_mode, "remote")

    def test_query_and_location_passed_upstream(self):
        captured_params = {}

        def fake_get(url, params=None, headers=None, timeout=None):
            captured_params.update(params or {})
            return httpx.Response(
                200,
                json={"jobs": []},
                request=httpx.Request("GET", url),
            )

        criteria = SearchCriteria(queries=["DevOps"], locations=["Americas"])
        with patch("app.services.job_sources.remotive.httpx.get", side_effect=fake_get):
            RemotiveSource().fetch(criteria)

        self.assertEqual(captured_params.get("search"), "DevOps")
        self.assertEqual(captured_params.get("location"), "Americas")

    def test_empty_response(self):
        def fake_get(url, params=None, headers=None, timeout=None):
            return httpx.Response(
                200,
                json={"jobs": []},
                request=httpx.Request("GET", url),
            )

        criteria = SearchCriteria(queries=["nonexistent"])
        with patch("app.services.job_sources.remotive.httpx.get", side_effect=fake_get):
            jobs = RemotiveSource().fetch(criteria)

        self.assertEqual(jobs, [])

    def test_malformed_json_raises_controlled_error(self):
        def fake_get(url, params=None, headers=None, timeout=None):
            return httpx.Response(
                200,
                content=b"not-json{{{",
                request=httpx.Request("GET", url),
            )

        criteria = SearchCriteria(queries=["python"])
        with patch("app.services.job_sources.remotive.httpx.get", side_effect=fake_get):
            with self.assertRaises(SourceUnavailableError) as ctx:
                RemotiveSource().fetch(criteria)

        self.assertIn("Remotive", str(ctx.exception))
        self.assertIn("invalid response", str(ctx.exception))

    def test_non_dict_json_raises_controlled_error(self):
        def fake_get(url, params=None, headers=None, timeout=None):
            return httpx.Response(
                200,
                json=["unexpected", "array"],
                request=httpx.Request("GET", url),
            )

        criteria = SearchCriteria(queries=["python"])
        with patch("app.services.job_sources.remotive.httpx.get", side_effect=fake_get):
            with self.assertRaises(SourceUnavailableError) as ctx:
                RemotiveSource().fetch(criteria)

        self.assertIn("Remotive", str(ctx.exception))

    def test_http_error_raises_controlled_error(self):
        for status_code in [429, 500, 502]:
            def fake_get(url, params=None, headers=None, timeout=None):
                return httpx.Response(
                    status_code,
                    request=httpx.Request("GET", url),
                )

            criteria = SearchCriteria(queries=["python"])
            with patch("app.services.job_sources.remotive.httpx.get", side_effect=fake_get):
                with self.assertRaises(SourceUnavailableError) as ctx:
                    RemotiveSource().fetch(criteria)

            self.assertIn("Remotive", str(ctx.exception))

    def test_timeout_raises_controlled_error(self):
        def fake_get(url, params=None, headers=None, timeout=None):
            raise httpx.TimeoutException("Remotive timeout")

        criteria = SearchCriteria(queries=["python"])
        with patch("app.services.job_sources.remotive.httpx.get", side_effect=fake_get):
            with self.assertRaises(SourceUnavailableError) as ctx:
                RemotiveSource().fetch(criteria)

        self.assertIn("Remotive", str(ctx.exception))
        self.assertIn("timed out", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
