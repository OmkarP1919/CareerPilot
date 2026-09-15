"""Tests for RemoteOK provider adapter (Phase 7.0D.2)."""
import unittest
from unittest.mock import MagicMock, patch

import httpx

from app.services.job_sources.base import SearchCriteria, SourceUnavailableError
from app.services.job_sources.remoteok import RemoteOKSource, strip_html


class TestRemoteOKProvider(unittest.TestCase):
    def test_strip_html(self):
        html = "<p>Looking for a <strong>Senior Engineer</strong> &amp; leader.<br/>Apply now!</p>"
        cleaned = strip_html(html)
        self.assertEqual(cleaned, "Looking for a Senior Engineer & leader. Apply now!")


    def test_is_enabled_always_true(self):
        source = RemoteOKSource()
        self.assertTrue(source.is_enabled)

    def test_successful_parsing(self):
        payload = [
            {"legal": "This API is for personal use only", "terms": "Legal text"},
            {
                "id": "12345",
                "epoch": 1710000000,
                "date": "2026-03-01T12:00:00+00:00",
                "company": "Acme Remote",
                "position": "Staff Backend Engineer",
                "tags": ["python", "fastapi", "postgresql"],
                "description": "<div>We are hiring a <b>Backend Engineer</b>.</div>",
                "location": "Worldwide",
                "salary_min": 120000,
                "salary_max": 160000,
                "apply_url": "https://remoteok.com/apply/12345",
                "url": "https://remoteok.com/remote-jobs/12345",
            },
            {
                # Job with 0 salary (sentinel for hidden/unspecified)
                "id": "67890",
                "date": "2026-03-02T15:00:00Z",
                "company": "Startup X",
                "position": "Frontend Dev",
                "tags": ["react", "typescript"],
                "description": "<p>React developer needed.</p>",
                "location": "Anywhere",
                "salary_min": 0,
                "salary_max": 0,
                "apply_url": "https://startup.com/jobs/dev",
                "url": "https://remoteok.com/remote-jobs/67890",
            },
        ]

        def fake_get(url, params=None, headers=None, timeout=None):
            return httpx.Response(
                200,
                json=payload,
                request=httpx.Request("GET", url),
            )

        criteria = SearchCriteria(queries=["python"])
        with patch("app.services.job_sources.remoteok.httpx.get", side_effect=fake_get):
            jobs = RemoteOKSource().fetch(criteria)

        self.assertEqual(len(jobs), 2)

        # Job 1 verification
        j1 = jobs[0]
        self.assertEqual(j1.external_id, "12345")
        self.assertEqual(j1.title, "Staff Backend Engineer")
        self.assertEqual(j1.company, "Acme Remote")
        self.assertEqual(j1.location, "Worldwide")
        self.assertEqual(j1.description, "We are hiring a Backend Engineer.")
        self.assertEqual(j1.application_url, "https://remoteok.com/apply/12345")
        self.assertEqual(j1.source_url, "https://remoteok.com/remote-jobs/12345")
        self.assertEqual(j1.source, "RemoteOK")
        self.assertTrue(j1.remote)
        self.assertEqual(j1.work_mode, "remote")
        self.assertEqual(j1.salary_min, 120000)
        self.assertEqual(j1.salary_max, 160000)
        self.assertEqual(j1.skills, ["python", "fastapi", "postgresql"])
        self.assertIsNotNone(j1.posted_at)

        # Job 2 verification: salary 0 -> None
        j2 = jobs[1]
        self.assertEqual(j2.external_id, "67890")
        self.assertIsNone(j2.salary_min)
        self.assertIsNone(j2.salary_max)
        self.assertEqual(j2.skills, ["react", "typescript"])
        self.assertTrue(j2.remote)
        self.assertEqual(j2.work_mode, "remote")

    def test_query_passed_as_tag(self):
        captured_params = {}

        def fake_get(url, params=None, headers=None, timeout=None):
            captured_params.update(params or {})
            return httpx.Response(
                200,
                json=[],
                request=httpx.Request("GET", url),
            )

        criteria = SearchCriteria(queries=["FastAPI Developer"])
        with patch("app.services.job_sources.remoteok.httpx.get", side_effect=fake_get):
            RemoteOKSource().fetch(criteria)

        self.assertEqual(captured_params.get("tag"), "fastapi developer")

    def test_empty_response(self):
        def fake_get(url, params=None, headers=None, timeout=None):
            return httpx.Response(
                200,
                json=[],
                request=httpx.Request("GET", url),
            )

        criteria = SearchCriteria(queries=["rare-niche-tag"])
        with patch("app.services.job_sources.remoteok.httpx.get", side_effect=fake_get):
            jobs = RemoteOKSource().fetch(criteria)

        self.assertEqual(jobs, [])

    def test_malformed_json_raises_controlled_error(self):
        def fake_get(url, params=None, headers=None, timeout=None):
            return httpx.Response(
                200,
                content=b"not-valid-json{{{",
                request=httpx.Request("GET", url),
            )

        criteria = SearchCriteria(queries=["python"])
        with patch("app.services.job_sources.remoteok.httpx.get", side_effect=fake_get):
            with self.assertRaises(SourceUnavailableError) as ctx:
                RemoteOKSource().fetch(criteria)

        self.assertIn("RemoteOK", str(ctx.exception))
        self.assertIn("invalid response", str(ctx.exception))

    def test_non_list_json_raises_controlled_error(self):
        def fake_get(url, params=None, headers=None, timeout=None):
            return httpx.Response(
                200,
                json={"error": "unexpected format"},
                request=httpx.Request("GET", url),
            )

        criteria = SearchCriteria(queries=["python"])
        with patch("app.services.job_sources.remoteok.httpx.get", side_effect=fake_get):
            with self.assertRaises(SourceUnavailableError) as ctx:
                RemoteOKSource().fetch(criteria)

        self.assertIn("RemoteOK", str(ctx.exception))

    def test_http_error_raises_controlled_error(self):
        for status_code in [429, 500, 503]:
            def fake_get(url, params=None, headers=None, timeout=None):
                return httpx.Response(
                    status_code,
                    request=httpx.Request("GET", url),
                )

            criteria = SearchCriteria(queries=["python"])
            with patch("app.services.job_sources.remoteok.httpx.get", side_effect=fake_get):
                with self.assertRaises(SourceUnavailableError) as ctx:
                    RemoteOKSource().fetch(criteria)

            self.assertIn("RemoteOK", str(ctx.exception))

    def test_timeout_raises_controlled_error(self):
        def fake_get(url, params=None, headers=None, timeout=None):
            raise httpx.TimeoutException("RemoteOK timeout")

        criteria = SearchCriteria(queries=["python"])
        with patch("app.services.job_sources.remoteok.httpx.get", side_effect=fake_get):
            with self.assertRaises(SourceUnavailableError) as ctx:
                RemoteOKSource().fetch(criteria)

        self.assertIn("RemoteOK", str(ctx.exception))
        self.assertIn("timed out", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
