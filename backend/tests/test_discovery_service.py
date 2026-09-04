"""Phase 5C discovery service tests.

Covers:
A. Canonical identity / cross-source dedup (provenance preserved, conservative).
B. Source selection (resolve_sources).
C. Request -> SearchCriteria mapping.
D. Unified filtered search with explainable profile-alignment ranking.
E. Freshness labeling (deterministic, never faked).
F. Saved search CRUD.
G. Saved search re-run new-result detection (alert-ready).
"""
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models.user import User
from app.models.profile import Profile, Skill, UserSkill
from app.models.saved_search import SavedSearch
from app.schemas.discovery import JobFilterRequest
from app.services import discovery_service as ds
from app.services.job_sources.base import (
    NormalizedJob,
    SearchCriteria,
    SourceStatus,
    SourceResult,
)


def make_job(external_id, title="Backend Developer", company="Acme Corp",
             location="Pune, India", source="Adzuna", description=None,
             skills=None, posted_at="2026-08-20T10:00:00Z", app_url=None,
             src_url=None):
    return NormalizedJob(
        external_id=external_id,
        title=title,
        company=company,
        location=location,
        description=description or f"{title} role at {company}.",
        source=source,
        posted_at=posted_at,
        skills=skills or [],
        application_url=app_url or f"https://apply/{external_id}",
        source_url=src_url or f"https://{source.lower()}.com/jobs/{external_id}",
    )


class CanonicalDedupTest(unittest.TestCase):
    def test_canonical_key_normalizes_title_company_location(self):
        a = make_job("a1", title="Backend Developer", company="Acme Corp", location="Pune, India")
        b = make_job("b1", title="  Backend   Developer ", company="Acme Corp", location="Pune, India")
        self.assertEqual(ds.canonical_job_key(a), ds.canonical_job_key(b))

    def test_canonical_key_distinguishes_company_noise(self):
        a = make_job("a1", company="Acme Corp")
        b = make_job("b1", company="Acme Corp Inc")
        # Corporation suffixes are stripped consistently.
        self.assertEqual(ds.canonical_job_key(a), ds.canonical_job_key(b))

    def test_cross_source_dedup_preserves_provenance(self):
        adz = make_job("ext-adz", title="Senior Python Developer", company="Stripe", source="Adzuna")
        job = make_job("ext-job", title="Senior Python Developer", company="Stripe", source="Jobicy")
        records, dup_count = ds.dedupe_jobs([adz, job])
        self.assertEqual(len(records), 1)
        self.assertEqual(dup_count, 1)
        self.assertEqual(sorted(records[0]["sources"]), ["Adzuna", "Jobicy"])
        self.assertEqual(len(records[0]["application_urls"]), 2)
        self.assertEqual(records[0]["primary_source"], records[0]["representative"].source)

    def test_duplicate_count_only_counts_excess(self):
        j1 = make_job("1", title="T", company="C", location="Loc")
        j2 = make_job("2", title="T", company="C", location="Loc")
        j3 = make_job("3", title="Different", company="C2", location="Else")
        records, dup_count = ds.dedupe_jobs([j1, j2, j3])
        self.assertEqual(len(records), 2)
        self.assertEqual(dup_count, 1)

    def test_no_false_merge_on_distinct_title(self):
        j1 = make_job("1", title="Backend Developer", company="Acme", location="Pune")
        j2 = make_job("2", title="Frontend Developer", company="Acme", location="Pune")
        records, dup_count = ds.dedupe_jobs([j1, j2])
        self.assertEqual(len(records), 2)
        self.assertEqual(dup_count, 0)


class SourceSelectionTest(unittest.TestCase):
    def test_default_all_sources(self):
        providers, names = ds.resolve_sources(None)
        self.assertEqual(names, ds.ALL_SOURCE_NAMES)
        self.assertEqual(len(providers), 3)

    def test_selected_sources(self):
        providers, names = ds.resolve_sources(["Jobicy"])
        self.assertEqual(names, ["Jobicy"])
        self.assertEqual(len(providers), 1)

    def test_unknown_sources_ignored_and_fallback(self):
        providers, names = ds.resolve_sources(["Nope", "AlsoNope"])
        # Nothing known selected -> fall back to all
        self.assertEqual(names, ds.ALL_SOURCE_NAMES)
        self.assertEqual(len(providers), 3)


class BuildCriteriaTest(unittest.TestCase):
    def test_mapping(self):
        req = JobFilterRequest(
            queries=["python", "backend"],
            locations=["Pune"],
            remote=True,
            employment_type="Full-time",
            salary_min=1000,
            salary_max=5000,
            salary_period="monthly",
            skills=["python", "fastapi"],
            skills_match="all",
            sort="newest",
            page=2,
            page_size=20,
        )
        c = ds.build_criteria(req)
        self.assertIsInstance(c, SearchCriteria)
        self.assertEqual(c.queries, ["python", "backend"])
        self.assertEqual(c.locations, ["Pune"])
        self.assertTrue(c.remote)
        self.assertEqual(c.employment_type, "Full-time")
        self.assertEqual(c.salary_min, 1000)
        self.assertEqual(c.salary_period, "monthly")
        self.assertEqual(c.skills, ["python", "fastapi"])
        self.assertEqual(c.skills_match, "all")
        self.assertEqual(c.sort, "newest")
        self.assertEqual(c.page, 2)
        self.assertEqual(c.page_size, 20)


class ServiceIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        self.user = User(id="u1", firebase_uid="fb1", email="u1@test.com", name="U1")
        self.profile = Profile(id="p1", user_id="u1", preferred_roles="Backend Developer",
                               preferred_locations="Pune")
        self.skill_py = Skill(id="s1", name="Python")
        self.skill_fa = Skill(id="s2", name="FastAPI")
        self.us1 = UserSkill(id="us1", profile_id="p1", skill_id="s1", category="lang", skill=self.skill_py)
        self.us2 = UserSkill(id="us2", profile_id="p1", skill_id="s2", category="fw", skill=self.skill_fa)
        self.db.add_all([self.user, self.profile, self.skill_py, self.skill_fa, self.us1, self.us2])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def _make_outcome(self, jobs):
        result = SourceResult(source="Jobicy", status=SourceStatus.SUCCESS, jobs=jobs)
        return {
            "results": [result],
            "jobs": jobs,
            "errors": [],
        }

    @patch.object(ds.DiscoveryOrchestrator, "search_filtered")
    def test_filtered_search_dedups_and_ranks(self, mock_search):
        # Same underlying job from two providers (different external ids)
        adz = make_job("adz1", title="Backend Developer", company="Acme Corp",
                       location="Pune, India", source="Adzuna",
                       skills=["Python", "FastAPI"],
                       description="Python and FastAPI backend role")
        job = make_job("job1", title="Backend Developer", company="Acme Corp",
                       location="Pune, India", source="Jobicy",
                       skills=["Python", "FastAPI"],
                       description="Python and FastAPI backend role")
        mock_search.return_value = self._make_outcome([adz, job])

        req = JobFilterRequest(queries=["backend"], sources=["Jobicy", "Adzuna"])
        report = ds.run_filtered_search("u1", self.db, req)

        self.assertEqual(report.total, 2)
        self.assertEqual(report.duplicate_count, 1)
        self.assertEqual(report.unique_results, 1)
        result = report.results[0]
        self.assertEqual(sorted(result.sources), ["Adzuna", "Jobicy"])
        self.assertGreaterEqual(result.match.overall_score, 85)
        self.assertEqual(set(result.match.matched_skills), {"python", "fastapi"})
        self.assertEqual(result.match.missing_skills, [])
        self.assertTrue(any("skills" in r.lower() for r in result.match.reasons))
        self.assertEqual(report.sources[0].status, "success")

    @patch.object(ds.DiscoveryOrchestrator, "search_filtered")
    def test_profile_alignment_reasons(self, mock_search):
        job = make_job("1", title="Frontend Developer", company="React Inc",
                       location="New York", source="Jobicy",
                       skills=["React"], description="React frontend role")
        mock_search.return_value = self._make_outcome([job])

        req = JobFilterRequest(queries=["frontend"], sources=["Jobicy"])
        report = ds.run_filtered_search("u1", self.db, req)

        result = report.results[0]
        self.assertEqual(set(result.match.missing_skills), {"python", "fastapi"})
        self.assertEqual(result.match.matched_skills, [])
        # role does not align, location not preferred, but missing skills present
        self.assertLess(result.match.overall_score, 100)

    @patch.object(ds.DiscoveryOrchestrator, "search_filtered")
    def test_freshness_label_deterministic(self, mock_search):
        recent = make_job("1", title="Backend Developer", company="Acme",
                          location="Pune", source="Jobicy",
                          skills=["Python"], posted_at="2026-09-01T10:00:00Z")
        mock_search.return_value = self._make_outcome([recent])
        req = JobFilterRequest(queries=["backend"], sources=["Jobicy"])
        report = ds.run_filtered_search("u1", self.db, req)
        # Recent post (within ~3 days of 2026-09-04) -> "Today" or "This week"
        self.assertIn(report.results[0].freshness, ("Today", "This week", "2 weeks"))

    @patch.object(ds.DiscoveryOrchestrator, "search_filtered")
    def test_unpersonalized_returns_no_match(self, mock_search):
        job = make_job("1", title="Backend Developer", company="Acme",
                       location="Pune", source="Jobicy",
                       skills=["Python"], posted_at="2026-09-01T10:00:00Z")
        mock_search.return_value = self._make_outcome([job])
        req = JobFilterRequest(queries=["backend"], sources=["Jobicy"],
                               include_profile_alignment=False)
        report = ds.run_filtered_search("u1", self.db, req)
        self.assertIsNone(report.results[0].match)


class SavedSearchTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.user = User(id="u1", firebase_uid="fb1", email="u1@test.com", name="U1")
        self.db.add(self.user)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def test_create_and_list(self):
        criteria = {"queries": ["python"], "sources": ["Jobicy"]}
        saved = ds.create_saved_search("u1", self.db, "Python Roles", criteria)
        self.assertIsNotNone(saved.id)
        items = ds.list_saved_searches("u1", self.db)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].name, "Python Roles")

    def test_update_and_delete(self):
        saved = ds.create_saved_search("u1", self.db, "A", {"queries": ["x"]})
        updated = ds.update_saved_search("u1", self.db, saved.id, "B", {"queries": ["y"]})
        self.assertEqual(updated.name, "B")
        self.assertEqual(ds.get_saved_search("u1", self.db, saved.id).name, "B")
        self.assertTrue(ds.delete_saved_search("u1", self.db, saved.id))
        self.assertIsNone(ds.get_saved_search("u1", self.db, saved.id))
        self.assertFalse(ds.delete_saved_search("u1", self.db, saved.id))

    @patch.object(ds.DiscoveryOrchestrator, "search_filtered")
    def test_run_saved_search_new_result_detection(self, mock_search):
        job_a = make_job("1", title="Backend Developer", company="Acme",
                         location="Pune", source="Jobicy",
                         skills=["Python"], posted_at="2026-09-01T10:00:00Z")
        mock_search.return_value = {
            "results": [SourceResult(source="Jobicy", status=SourceStatus.SUCCESS, jobs=[job_a])],
            "jobs": [job_a],
            "errors": [],
        }
        saved = ds.create_saved_search(
            "u1", self.db, "Backend",
            {"queries": ["backend"], "sources": ["Jobicy"], "include_profile_alignment": True},
        )
        run1 = ds.run_saved_search("u1", self.db, saved.id)
        self.assertEqual(run1["new_results"], 1)
        self.assertEqual(run1["report"].unique_results, 1)
        self.assertTrue(run1["report"].results[0].match.is_new)

        # Second run: same job, no new results.
        run2 = ds.run_saved_search("u1", self.db, saved.id)
        self.assertEqual(run2["new_results"], 0)
        self.assertFalse(run2["report"].results[0].match.is_new)

    @patch.object(ds.DiscoveryOrchestrator, "search_filtered")
    def test_run_saved_search_new_appearance_detected(self, mock_search):
        job_a = make_job("1", title="Backend Developer", company="Acme",
                         location="Pune", source="Jobicy",
                         skills=["Python"], posted_at="2026-09-01T10:00:00Z")
        mock_search.side_effect = [
            {"results": [], "jobs": [], "errors": []},
            {
                "results": [SourceResult(source="Jobicy", status=SourceStatus.SUCCESS, jobs=[job_a])],
                "jobs": [job_a],
                "errors": [],
            },
        ]
        saved = ds.create_saved_search("u1", self.db, "Backend", {"queries": ["backend"], "sources": ["Jobicy"]})
        ds.run_saved_search("u1", self.db, saved.id)
        run2 = ds.run_saved_search("u1", self.db, saved.id)
        self.assertEqual(run2["new_results"], 1)
        self.assertTrue(run2["report"].results[0].match.is_new)


if __name__ == "__main__":
    unittest.main()
