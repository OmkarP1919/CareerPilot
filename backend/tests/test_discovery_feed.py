"""Phase 7.0D.1 — Discovery feed tests.

Covers the 16 enumerated requirements plus API contract and fast-path
verification:

1.  Deterministic query generation
2.  Provider registry usage (not manual construction)
3.  Provider failure isolation
4.  Canonical normalization (pipeline)
5.  Cross-source deduplication (canonical_job_key)
6.  Profile matching with exact expected score
7.  Frozen 50/20/15/10/5 weight formula (unchanged)
8.  Ranking by profile match score (order)
9.  Incomplete profile (no skills/projects)
10. Empty profile (no Profile row)
11. No provider results
12. Duplicate external jobs across providers (single Job row)
13. Persistence safety (repeat refresh idempotent)
14. Existing /jobs/recommended endpoint compatibility
15. Manual discovery compatibility (existing endpoints intact)
16. Feed response contract
17. Feed endpoint does NOT call providers (fast-path guarantee)
18. Explanation attached from JobMatch
"""
import json
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base, get_db
from app.dependencies.auth import get_current_user
from app.models.job import Job
from app.models.job_match import JobMatch
from app.models.profile import (
    Education,
    Experience,
    Profile,
    Project,
    Skill,
    UserSkill,
)
from app.models.user import User
from app.api.jobs import router as jobs_router
from app.services import discovery_feed as feed
from app.services.job_discovery import get_recommended_jobs
from app.services.job_sources.base import (
    NormalizedJob,
    SearchCriteria,
    SourceResult,
    SourceStatus,
    SourceUnavailableError,
)
from app.services.job_sources.orchestrator import DiscoveryOrchestrator
from app.services.matching import calculate_match
from app.services.personalized_discovery import PersonalizedQueryBuilder


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_normalized(
    external_id,
    title="Backend Developer",
    company="Acme Corp",
    location="Pune, India",
    source="Jobicy",
    description=None,
    skills=None,
    employment_type="Full-time",
    posted_at="2026-08-20T10:00:00Z",
):
    return NormalizedJob(
        external_id=external_id,
        title=title,
        company=company,
        location=location,
        description=description or f"{title} role at {company}. We need Python and FastAPI skills.",
        source=source,
        employment_type=employment_type,
        posted_at=posted_at,
        skills=skills or [],
    )


class _FakeProvider:
    def __init__(self, name, jobs=None, error=None):
        self.name = name
        self._jobs = jobs or []
        self._error = error
        self.is_enabled = True

    def fetch(self, criteria):
        if self._error:
            raise self._error
        return list(self._jobs)

    @property
    def capabilities(self):
        from app.services.job_sources.base import ProviderCapabilities
        return ProviderCapabilities()


# ---------------------------------------------------------------------------
# A. Service-level unit tests
# ---------------------------------------------------------------------------


class TestDeterministicQueryGeneration(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        user = User(id="u1", firebase_uid="fb1", email="u1@test.com", name="U1")
        profile = Profile(
            id="p1", user_id="u1",
            preferred_roles="Backend Developer, Python Engineer",
            preferred_locations="Pune",
        )
        skill = Skill(id="s1", name="Python")
        us = UserSkill(id="us1", profile_id="p1", skill_id="s1", category="lang", skill=skill)
        edu = Education(
            id="e1", profile_id="p1",
            degree="B.Tech", college="XYZ", graduation_year="2026",
        )
        self.db.add_all([user, profile, skill, us, edu])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def test_context_is_deterministic(self):
        ctx1 = feed.build_context("u1", self.db)
        ctx2 = feed.build_context("u1", self.db)
        self.assertEqual(ctx1, ctx2)
        self.assertTrue(ctx1["has_profile"])
        self.assertTrue(ctx1["has_education"])
        self.assertEqual(ctx1["experience_level"], "student_fresher")


class TestProviderRegistryUsage(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        user = User(id="u1", firebase_uid="fb1", email="u1@test.com", name="U1")
        profile = Profile(
            id="p1", user_id="u1",
            preferred_roles="Backend Developer",
            preferred_locations="Pune",
        )
        skill = Skill(id="s1", name="Python")
        us = UserSkill(id="us1", profile_id="p1", skill_id="s1", category="lang", skill=skill)
        self.db.add_all([user, profile, skill, us])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    @patch.object(feed, "get_providers")
    @patch.object(DiscoveryOrchestrator, "search")
    def test_uses_registry_not_manual_construction(self, mock_search, mock_get):
        provider = _FakeProvider("Jobicy", jobs=[_make_normalized("reg1")])
        mock_get.return_value = [provider]
        mock_search.return_value = {
            "results": [SourceResult(source="Jobicy", status=SourceStatus.SUCCESS, jobs=[_make_normalized("reg1")])],
            "jobs": [_make_normalized("reg1")],
            "errors": [],
        }
        result = feed.refresh_feed("u1", self.db)
        mock_get.assert_called_once()
        self.assertGreater(result["new_jobs"], 0)
        self.assertEqual(self.db.query(Job).count(), 1)


class TestProviderFailureIsolation(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        user = User(id="u1", firebase_uid="fb1", email="u1@test.com", name="U1")
        profile = Profile(
            id="p1", user_id="u1",
            preferred_roles="Backend Developer",
            preferred_locations="Pune",
        )
        skill = Skill(id="s1", name="Python")
        us = UserSkill(id="us1", profile_id="p1", skill_id="s1", category="lang", skill=skill)
        self.db.add_all([user, profile, skill, us])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    @patch.object(feed, "get_providers")
    def test_one_fails_other_succeeds(self, mock_get):
        ok_provider = _FakeProvider("Jobicy", jobs=[_make_normalized("ok1", source="Jobicy")])
        fail_provider = _FakeProvider("Adzuna", error=SourceUnavailableError("timed out"))
        mock_get.return_value = [fail_provider, ok_provider]
        result = feed.refresh_feed("u1", self.db)
        self.assertEqual(result["new_jobs"], 1)
        self.assertEqual(result["sources"]["Jobicy"], 1)
        self.assertTrue(any("temporarily unavailable" in e for e in result["errors"]))
        self.assertGreater(self.db.query(Job).count(), 0)


class TestCrossSourceDeduplication(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        user = User(id="u1", firebase_uid="fb1", email="u1@test.com", name="U1")
        profile = Profile(
            id="p1", user_id="u1",
            preferred_roles="Backend Developer",
            preferred_locations="Pune",
        )
        skill = Skill(id="s1", name="Python")
        us = UserSkill(id="us1", profile_id="p1", skill_id="s1", category="lang", skill=skill)
        self.db.add_all([user, profile, skill, us])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    @patch.object(feed, "get_providers")
    def test_two_sources_same_job_one_row(self, mock_get):
        adz_job = _make_normalized("adz-1", source="Adzuna")
        jobicy_job = _make_normalized("job-1", source="Jobicy")
        provider = _FakeProvider("Adzuna", jobs=[adz_job, jobicy_job])
        mock_get.return_value = [provider]
        result = feed.refresh_feed("u1", self.db)
        self.assertEqual(self.db.query(Job).count(), 1)
        self.assertEqual(result["new_jobs"], 1)
        self.assertEqual(result["existing_jobs"], 0)


class TestProfileMatchingExactScore(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        user = User(id="u1", firebase_uid="fb1", email="u1@test.com", name="U1")
        profile = Profile(
            id="p1", user_id="u1",
            preferred_roles="Backend Developer",
            preferred_locations="Pune",
        )
        skill_py = Skill(id="s1", name="Python")
        skill_fa = Skill(id="s2", name="FastAPI")
        us1 = UserSkill(id="us1", profile_id="p1", skill_id="s1", category="lang", skill=skill_py)
        us2 = UserSkill(id="us2", profile_id="p1", skill_id="s2", category="fw", skill=skill_fa)
        proj = Project(
            id="pr1", profile_id="p1", name="TaskQueue",
            technologies="Python, FastAPI",
        )
        exp = Experience(
            id="ex1", profile_id="p1", company="Acme",
            role="Backend Dev", technologies="Python",
        )
        self.db.add_all([user, profile, skill_py, skill_fa, us1, us2, proj, exp])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def test_external_job_score_matches_frozen_formula(self):
        """External job without required_skills: skills_score=70 (inferred match),
        project_score=100, experience_score=100, role_score=80 (substring match on
        the single preferred entry "Backend Developer"), location_score=100.
        Frozen weights: 50/20/15/10/5 → overall=83."""
        job = MagicMock()
        job.title = "Backend Developer"
        job.company = "Acme"
        job.location = "Pune"
        job.required_skills = None
        job.description = "Python FastAPI Backend Developer role"

        result = calculate_match("u1", job, self.db)
        # skills: 2 inferred matches from desc → 70.0; project 1/1→100; exp 1/1→100;
        # role 80 ("backend developer" is a substring of the title but not a word match)
        expected = round(70 * 0.50 + 100 * 0.20 + 100 * 0.15 + 80 * 0.10 + 100 * 0.05)
        self.assertEqual(result["overall_score"], expected)  # 83


class TestWeightsUnchanged(unittest.TestCase):
    def test_frozen_formula_full_match(self):
        """With structured required_skills and full match: overall MUST be 100."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        db = Session()
        user = User(id="u1", firebase_uid="fb1", email="u1@test.com", name="U1")
        profile = Profile(id="p1", user_id="u1", preferred_roles="Backend, Developer", preferred_locations="Pune")
        sk1 = Skill(id="s1", name="Python")
        sk2 = Skill(id="s2", name="FastAPI")
        us1 = UserSkill(id="us1", profile_id="p1", skill_id="s1", category="lang", skill=sk1)
        us2 = UserSkill(id="us2", profile_id="p1", skill_id="s2", category="fw", skill=sk2)
        proj = Project(id="pr1", profile_id="p1", name="P", technologies="Python")
        exp = Experience(id="ex1", profile_id="p1", company="C", role="Backend Dev", technologies="Python")
        db.add_all([user, profile, sk1, sk2, us1, us2, proj, exp])
        db.commit()
        job = MagicMock()
        job.title = "Backend Developer"
        job.company = "Acme"
        job.location = "Pune"
        job.required_skills = "Python, FastAPI"
        job.description = "Build FastAPI services"
        result = calculate_match("u1", job, db)
        # skills=100 (2/2), project=100, exp=100, role=100 (word match "backend"),
        # loc=100 → 100
        self.assertEqual(result["overall_score"], 100)
        db.close()
        Base.metadata.drop_all(engine)

    def test_frozen_formula_skills_only_no_role_no_location(self):
        """Skills only (full match), no role alignment, no location → 60."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        db = Session()
        user = User(id="u1", firebase_uid="fb1", email="u1@test.com", name="U1")
        profile = Profile(id="p1", user_id="u1")  # no preferred_roles, no preferred_locations
        sk = Skill(id="s1", name="Python")
        us = UserSkill(id="us1", profile_id="p1", skill_id="s1", category="lang", skill=sk)
        db.add_all([user, profile, sk, us])
        db.commit()
        job = MagicMock()
        job.title = "Data Engineer"
        job.company = "Acme"
        job.location = "Remote"
        job.required_skills = "Python"
        job.description = "Build data pipelines"
        result = calculate_match("u1", job, db)
        # skills=100 (1/1); project=0; experience=0; role=50 (no preferred roles); location=50
        expected = round(100 * 0.50 + 0 * 0.20 + 0 * 0.15 + 50 * 0.10 + 50 * 0.05)
        self.assertEqual(result["overall_score"], expected)  # 60
        db.close()
        Base.metadata.drop_all(engine)


class TestRankingByProfileMatch(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        now = datetime.now(timezone.utc)
        user = User(id="u1", firebase_uid="fb1", email="u1@test.com", name="U1")
        profile = Profile(id="p1", user_id="u1", preferred_roles="Backend Developer", preferred_locations="Pune")
        sk = Skill(id="s1", name="Python")
        us = UserSkill(id="us1", profile_id="p1", skill_id="s1", category="lang", skill=sk)
        job_hi = Job(id="jh", user_id="u1", title="Python Dev", company="A", created_at=now)
        job_lo = Job(id="jl", user_id="u1", title="DevOps Engineer", company="B", created_at=now)
        m_hi = JobMatch(id="mh", user_id="u1", job_id="jh", overall_score=92, role_score=100)
        m_lo = JobMatch(id="ml", user_id="u1", job_id="jl", overall_score=45, role_score=30)
        self.db.add_all([user, profile, sk, us, job_hi, job_lo, m_hi, m_lo])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def test_feed_returns_higher_score_first(self):
        ctx = feed.build_context("u1", self.db)
        self.assertEqual(ctx["experience_level"], "student_fresher")
        result = feed.build_feed("u1", self.db)
        self.assertEqual(len(result["jobs"]), 2)
        scores = [r["match_score"] for r in result["jobs"]]
        self.assertEqual(scores, [92, 45])


class TestIncompleteProfile(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        user = User(id="u1", firebase_uid="fb1", email="u1@test.com", name="U1")
        # Profile with no skills, no projects, no experience, no roles
        profile = Profile(id="p1", user_id="u1", preferred_roles=None, preferred_locations=None)
        self.db.add_all([user, profile])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def test_refresh_returns_incomplete_error(self):
        result = feed.refresh_feed("u1", self.db)
        self.assertIn(feed.INCOMPLETE_PROFILE_MESSAGE, result["errors"])
        self.assertEqual(result["new_jobs"], 0)

    def test_feed_builds_gracefully(self):
        result = feed.build_feed("u1", self.db)
        self.assertEqual(result["jobs"], [])
        # No graduation year and no experience entries → student_fresher default.
        self.assertEqual(result["context"]["experience_level"], "student_fresher")


class TestEmptyProfile(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        user = User(id="u1", firebase_uid="fb1", email="u1@test.com", name="U1")
        self.db.add(user)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def test_refresh_returns_no_profile_error(self):
        result = feed.refresh_feed("u1", self.db)
        self.assertIn(feed.NO_PROFILE_MESSAGE, result["errors"])

    def test_feed_returns_empty_with_no_profile_error(self):
        result = feed.build_feed("u1", self.db)
        self.assertEqual(result["jobs"], [])
        self.assertFalse(result["context"]["has_profile"])
        self.assertIn(feed.NO_PROFILE_MESSAGE, result["errors"])


class TestNoProviderResults(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        user = User(id="u1", firebase_uid="fb1", email="u1@test.com", name="U1")
        profile = Profile(id="p1", user_id="u1", preferred_roles="Backend Developer")
        self.db.add_all([user, profile])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    @patch.object(feed, "get_providers")
    def test_refresh_succeeds_with_zero_results(self, mock_get):
        mock_get.return_value = [_FakeProvider("Jobicy", jobs=[])]
        result = feed.refresh_feed("u1", self.db)
        self.assertEqual(result["new_jobs"], 0)
        self.assertEqual(result["errors"], [])
        self.assertEqual(self.db.query(Job).count(), 0)


class TestDuplicateExternalJobs(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        user = User(id="u1", firebase_uid="fb1", email="u1@test.com", name="U1")
        profile = Profile(
            id="p1", user_id="u1",
            preferred_roles="Backend Developer",
            preferred_locations="Pune",
        )
        skill = Skill(id="s1", name="Python")
        us = UserSkill(id="us1", profile_id="p1", skill_id="s1", category="lang", skill=skill)
        self.db.add_all([user, profile, skill, us])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    @patch.object(feed, "get_providers")
    def test_two_providers_one_job_single_row(self, mock_get):
        adz_job = _make_normalized("x1", source="Adzuna")
        jobicy_job = _make_normalized("x2", source="Jobicy")
        mock_get.return_value = [
            _FakeProvider("Adzuna", jobs=[adz_job]),
            _FakeProvider("Jobicy", jobs=[jobicy_job]),
        ]
        result = feed.refresh_feed("u1", self.db)
        self.assertEqual(self.db.query(Job).count(), 1)
        self.assertEqual(result["new_jobs"], 1)
        job = self.db.query(Job).one()
        self.assertIsNotNone(job.external_id)


class TestPersistenceSafety(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        user = User(id="u1", firebase_uid="fb1", email="u1@test.com", name="U1")
        profile = Profile(
            id="p1", user_id="u1",
            preferred_roles="Backend Developer",
            preferred_locations="Pune",
        )
        skill = Skill(id="s1", name="Python")
        us = UserSkill(id="us1", profile_id="p1", skill_id="s1", category="lang", skill=skill)
        self.db.add_all([user, profile, skill, us])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    @patch.object(feed, "get_providers")
    def test_repeat_refresh_no_duplicate_rows(self, mock_get):
        job = _make_normalized("safe1")
        mock_get.return_value = [_FakeProvider("Jobicy", jobs=[job])]
        res1 = feed.refresh_feed("u1", self.db)
        job_count = self.db.query(Job).count()
        match_count = self.db.query(JobMatch).filter(JobMatch.user_id == "u1").count()
        first_match = (
            self.db.query(JobMatch)
            .filter(JobMatch.user_id == "u1")
            .first()
        )
        assert first_match is not None
        score_first = first_match.overall_score

        res2 = feed.refresh_feed("u1", self.db)
        self.assertEqual(self.db.query(Job).count(), job_count)
        self.assertEqual(
            self.db.query(JobMatch).filter(JobMatch.user_id == "u1").count(),
            match_count,
        )
        second_match = (
            self.db.query(JobMatch)
            .filter(JobMatch.user_id == "u1")
            .first()
        )
        assert second_match is not None
        score_second = second_match.overall_score
        self.assertEqual(score_first, score_second)
        self.assertEqual(res2["existing_jobs"], 1)


class TestExplanationAttached(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        user = User(id="u1", firebase_uid="fb1", email="u1@test.com", name="U1")
        profile = Profile(
            id="p1", user_id="u1",
            preferred_roles="Backend Developer",
            preferred_locations="Pune",
        )
        skill = Skill(id="s1", name="Python")
        us = UserSkill(id="us1", profile_id="p1", skill_id="s1", category="lang", skill=skill)
        job = Job(id="j1", user_id="u1", title="Backend Dev", company="Acme", description="Python FastAPI role")
        match = JobMatch(
            id="m1", user_id="u1", job_id="j1",
            overall_score=85, skills_score=70, project_score=100,
            experience_score=100, role_score=100, location_score=100,
            matched_skills=json.dumps(["python", "fastapi"]),
            missing_skills=json.dumps([]),
            relevant_projects=json.dumps(["proj"]),
            relevant_experience=json.dumps(["eng at acme"]),
            explanation="Overall match: 85%. Strong skill overlap.",
        )
        self.db.add_all([user, profile, skill, us, job, match])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def test_feed_includes_explanation(self):
        result = feed.build_feed("u1", self.db)
        self.assertEqual(len(result["jobs"]), 1)
        self.assertEqual(result["jobs"][0]["explanation"], "Overall match: 85%. Strong skill overlap.")


# ---------------------------------------------------------------------------
# B. API-level integration tests
# ---------------------------------------------------------------------------


class TestFeedEndpoint(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        self.user = User(id="u1", firebase_uid="fb1", email="u1@test.com", name="U1")
        self.profile = Profile(
            id="p1", user_id="u1",
            preferred_roles="Backend Developer",
            preferred_locations="Pune",
        )
        self.skill = Skill(id="s1", name="Python")
        self.us = UserSkill(id="us1", profile_id="p1", skill_id="s1", category="lang", skill=self.skill)
        self.db = self.Session()
        self.db.add_all([self.user, self.profile, self.skill, self.us])
        self.db.commit()

        self.app = FastAPI()
        self.app.include_router(jobs_router)
        self.app.dependency_overrides[get_db] = lambda: self.Session()
        self.app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(self.app)

    def tearDown(self):
        self.engine.dispose()

    def _seed_job_and_match(self, score=85, explanation="Match test"):
        job = Job(id="jf1", user_id="u1", title="Python Dev", company="Acme", description="Python FastAPI role")
        m = JobMatch(
            id="mf1", user_id="u1", job_id="jf1",
            overall_score=score, role_score=100, location_score=100,
            matched_skills=json.dumps(["python"]),
            missing_skills=json.dumps([]),
            relevant_projects=json.dumps([]),
            relevant_experience=json.dumps([]),
            explanation=explanation,
        )
        db = self.Session()
        db.add_all([job, m])
        db.commit()
        db.close()

    def test_feed_response_contract(self):
        self._seed_job_and_match()
        resp = self.client.get("/jobs/feed")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("jobs", body)
        self.assertIn("context", body)
        self.assertIn("errors", body)
        self.assertIn("total", body)
        self.assertIn("refreshed", body)
        self.assertEqual(len(body["jobs"]), 1)
        j = body["jobs"][0]
        self.assertEqual(j["job"]["id"], "jf1")
        self.assertEqual(j["match_score"], 85)
        self.assertIn("python", j["matched_skills"])
        self.assertEqual(j["explanation"], "Match test")
        self.assertTrue(body["context"]["has_profile"])

    def test_feed_endpoint_does_not_call_providers(self):
        self._seed_job_and_match()
        with patch.object(feed, "get_providers") as mock_providers:
            self.client.get("/jobs/feed")
            mock_providers.assert_not_called()

    def test_feed_empty_profile_returns_200(self):
        db = self.Session()
        no_profile_user = User(id="u2", firebase_uid="fb2", email="u2@test.com", name="U2")
        db.add(no_profile_user)
        db.commit()

        self.app.dependency_overrides[get_current_user] = lambda: no_profile_user
        resp = self.client.get("/jobs/feed")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["jobs"], [])
        self.assertIn(feed.NO_PROFILE_MESSAGE, body["errors"])
        db.close()

    def test_recommended_endpoint_still_works(self):
        self._seed_job_and_match()
        resp = self.client.get("/jobs/recommended")
        self.assertEqual(resp.status_code, 200)
        jobs = resp.json()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["match_score"], 85)

    def test_manual_discovery_endpoint_still_works(self):
        """POST /jobs/discover/personalized still functions (not broken by feed)."""
        resp = self.client.post("/jobs/discover/personalized")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("queries_used", body)
        self.assertIn("errors", body)


if __name__ == "__main__":
    unittest.main()
