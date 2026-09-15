"""Tests for Adzuna provider fixes and enrichments (Phase 7.0D.2)."""
import unittest
from unittest.mock import MagicMock, patch

import httpx

from app.services.job_sources.adzuna import AdzunaSource, ADZUNA_SUPPORTED_COUNTRIES
from app.services.job_sources.base import SearchCriteria, SourceUnavailableError


class TestAdzunaProvider(unittest.TestCase):
    def _settings(self, country="us"):
        return MagicMock(
            ADZUNA_APP_ID="fake_app_id",
            ADZUNA_APP_KEY="fake_app_key",
            ADZUNA_COUNTRY=country,
            ADZUNA_TIMEOUT_SECONDS=10.0,
        )

    def test_india_country_in_supported_set(self):
        self.assertIn("in", ADZUNA_SUPPORTED_COUNTRIES)

    def test_explicit_criteria_country_overrides_env_default(self):
        captured_urls = []

        def fake_get(url, params=None, timeout=None):
            captured_urls.append(url)
            return httpx.Response(
                200,
                json={"results": []},
                request=httpx.Request("GET", url),
            )

        criteria = SearchCriteria(queries=["Python Developer"], country="in")
        with patch("app.services.job_sources.adzuna.get_settings", return_value=self._settings(country="us")), \
             patch("app.services.job_sources.adzuna.httpx.get", side_effect=fake_get):
            AdzunaSource().fetch(criteria)

        self.assertTrue(any("/in/search/" in u for u in captured_urls))
        self.assertFalse(any("/us/search/" in u for u in captured_urls))

    def test_env_default_country_used_when_criteria_country_absent(self):
        captured_urls = []

        def fake_get(url, params=None, timeout=None):
            captured_urls.append(url)
            return httpx.Response(
                200,
                json={"results": []},
                request=httpx.Request("GET", url),
            )

        criteria = SearchCriteria(queries=["Python Developer"], country=None)
        with patch("app.services.job_sources.adzuna.get_settings", return_value=self._settings(country="gb")), \
             patch("app.services.job_sources.adzuna.httpx.get", side_effect=fake_get):
            AdzunaSource().fetch(criteria)

        self.assertTrue(any("/gb/search/" in u for u in captured_urls))

    def test_india_error_does_not_fall_back_to_us(self):
        captured_urls = []

        def fake_get(url, params=None, timeout=None):
            captured_urls.append(url)
            # Simulate 500 error on India endpoint
            return httpx.Response(
                500,
                request=httpx.Request("GET", url),
            )

        criteria = SearchCriteria(queries=["Python Developer"], country="in")
        with patch("app.services.job_sources.adzuna.get_settings", return_value=self._settings(country="us")), \
             patch("app.services.job_sources.adzuna.httpx.get", side_effect=fake_get):
            with self.assertRaises(SourceUnavailableError) as ctx:
                AdzunaSource().fetch(criteria)

        self.assertIn("Adzuna was temporarily unavailable", str(ctx.exception))
        # Ensure NO request was made to /us/search/
        self.assertFalse(any("/us/search/" in u for u in captured_urls))
        self.assertTrue(all("/in/search/" in u for u in captured_urls))

    def test_normalized_job_enrichment(self):
        payload = {
            "results": [
                {
                    "id": "adz-101",
                    "title": "Senior Python Engineer",
                    "company": {"display_name": "Tech Corp India"},
                    "location": {"display_name": "Bengaluru, Karnataka", "area": ["India", "Karnataka"]},
                    "description": "Develop scalable APIs.",
                    "redirect_url": "https://adzuna.com/land/101",
                    "created": "2026-03-01T10:00:00Z",
                    "contract_type": "permanent",
                    "is_remote": 1,
                    "salary_min": 1800000.0,
                    "salary_max": 2400000.0,
                    "salary_currency": "INR",
                }
            ]
        }

        def fake_get(url, params=None, timeout=None):
            return httpx.Response(
                200,
                json=payload,
                request=httpx.Request("GET", url),
            )

        criteria = SearchCriteria(queries=["Python Engineer"], country="in")
        with patch("app.services.job_sources.adzuna.get_settings", return_value=self._settings(country="us")), \
             patch("app.services.job_sources.adzuna.httpx.get", side_effect=fake_get):
            jobs = AdzunaSource().fetch(criteria)

        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertEqual(job.external_id, "adz-101")
        self.assertEqual(job.title, "Senior Python Engineer")
        self.assertEqual(job.company, "Tech Corp India")
        self.assertEqual(job.location, "Bengaluru, Karnataka")
        self.assertEqual(job.country, "in")
        self.assertEqual(job.employment_type, "Full-time")
        self.assertEqual(job.application_url, "https://adzuna.com/land/101")
        self.assertTrue(job.remote)
        self.assertEqual(job.work_mode, "remote")
        self.assertEqual(job.salary_min, 1800000)
        self.assertEqual(job.salary_max, 2400000)
        self.assertEqual(job.salary_currency, "INR")

    def test_remote_false_and_missing_salary_enrichment(self):
        payload = {
            "results": [
                {
                    "id": "adz-102",
                    "title": "Onsite Developer",
                    "company": {"display_name": "Local Corp"},
                    "location": {"display_name": "London, UK"},
                    "description": "Office role.",
                    "redirect_url": "https://adzuna.com/land/102",
                    "created": "2026-03-02T10:00:00Z",
                    "is_remote": 0,
                }
            ]
        }

        def fake_get(url, params=None, timeout=None):
            return httpx.Response(
                200,
                json=payload,
                request=httpx.Request("GET", url),
            )

        criteria = SearchCriteria(queries=["Developer"], country="gb")
        with patch("app.services.job_sources.adzuna.get_settings", return_value=self._settings(country="gb")), \
             patch("app.services.job_sources.adzuna.httpx.get", side_effect=fake_get):
            jobs = AdzunaSource().fetch(criteria)

        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertFalse(job.remote)
        self.assertEqual(job.work_mode, "onsite")
        self.assertIsNone(job.salary_min)
        self.assertIsNone(job.salary_max)
        self.assertIsNone(job.salary_currency)
        self.assertEqual(job.country, "gb")

    def test_existing_supported_countries_still_work(self):
        captured_urls = []

        def fake_get(url, params=None, timeout=None):
            captured_urls.append(url)
            return httpx.Response(
                200,
                json={"results": []},
                request=httpx.Request("GET", url),
            )

        for c in ["gb", "us", "ca", "de", "au"]:
            criteria = SearchCriteria(queries=["Dev"], country=c)
            with patch("app.services.job_sources.adzuna.get_settings", return_value=self._settings()), \
                 patch("app.services.job_sources.adzuna.httpx.get", side_effect=fake_get):
                AdzunaSource().fetch(criteria)

        self.assertEqual(len(captured_urls), 5)
        for c in ["gb", "us", "ca", "de", "au"]:
            self.assertTrue(any(f"/{c}/search/" in u for u in captured_urls))


if __name__ == "__main__":
    unittest.main()
