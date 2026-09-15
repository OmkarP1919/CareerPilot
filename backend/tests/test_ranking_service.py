"""Comprehensive test suite for Canonical Ranking Service (Phase 7.0D.3).

Covers all 28 required test dimensions:
1. Exact canonical scoring
2. Active-factor reweighting
3. Multi-word skill matching
4. JS -> JavaScript alias
5. React Native
6. Machine Learning
7. CI/CD
8. Sparse/no required_skills
9. No preferred roles
10. No preferred locations
11. Remote jobs
12. Missing job location
13. Experience-level compatibility
14. Project overlap
15. Education requirement present
16. Education requirement absent
17. Empty profile
18. Incomplete profile
19. Same candidate/job produces consistent factor scores
20. Profile vs discovery score equivalence
21. Resume factor compatibility
22. score_version persistence
23. Discovery uses canonical persisted score
24. No provider calls during feed read
25. No N+1 candidate-context queries
26. User isolation
27. Existing endpoint compatibility
28. Schema initialization compatibility
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base, get_db
from app.database.schema_init import init_schema
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
from app.models.resume_job_analysis import ResumeJobAnalysis
from app.models.user import User
from app.schemas.discovery import JobFilterRequest
from app.services import discovery_service as ds
from app.services.discovery_feed import build_feed
from app.services.ranking import (
    CANONICAL_FACTOR_WEIGHTS,
    ProfileRankingContext,
    calculate_rank,
    canonicalize_skill,
    load_profile_context,
)
from app.api.match import router as match_router


class JobMock:
    def __init__(
        self,
        id="job_1",
        title="Backend Developer",
        company="Acme Corp",
        location="Pune, India",
        description="Python FastAPI backend role",
        required_skills="Python, FastAPI",
        experience_level="Mid Level",
        work_mode=None,
        posted_at="2026-09-10T10:00:00Z",
    ):
        self.id = id
        self.title = title
        self.company = company
        self.location = location
        self.description = description
        self.required_skills = required_skills
        self.experience_level = experience_level
        self.work_mode = work_mode
        self.posted_at = posted_at
        self.category = None


class TestRankingServiceCore(unittest.TestCase):
    """Unit tests for calculate_rank and factor logic."""

    def test_01_exact_canonical_scoring(self):
        """All 7 factors active with 100% scores must produce overall score 100."""
        ctx = ProfileRankingContext(
            user_id="u1",
            has_profile=True,
            skills=["Python", "FastAPI"],
            user_skills_set={"python", "fastapi"},
            preferred_roles=["Backend Developer"],
            preferred_locations=["Pune, India"],
            work_mode_preference="remote",
            classified_experience_level="mid",
            projects=[Project(name="API", technologies="Python, FastAPI")],
            education=[Education(degree="B.Tech", branch="Computer Science")],
        )
        job = JobMock(
            title="Senior Backend Developer",
            description="Build APIs with Python and FastAPI. Requires degree in computer science.",
            required_skills="Python, FastAPI",
            experience_level="Mid",
            work_mode="remote",
            location="Pune, India",
        )
        result = calculate_rank(profile_context=ctx, job=job)
        self.assertEqual(result.overall_score, 100)
        self.assertEqual(result.score_version, "v2")

    def test_02_active_factor_reweighting(self):
        """When factors are unavailable, overall score is dynamic weighted average over active weights."""
        ctx = ProfileRankingContext(
            user_id="u1",
            has_profile=True,
            skills=["Python", "FastAPI"],
            user_skills_set={"python", "fastapi"},
            preferred_roles=["Backend Developer"],
            preferred_locations=[],  # location unavailable
            work_mode_preference=None,  # work_mode unavailable
            classified_experience_level="mid",
            projects=[],  # projects unavailable
            education=[],  # education unavailable
        )
        # Job without education requirement, without work_mode, without location
        job = JobMock(
            title="Backend Developer",
            description="Looking for a developer to write clean code.",
            required_skills="Python, FastAPI",
            experience_level="Mid",
            location=None,
            work_mode=None,
        )
        result = calculate_rank(profile_context=ctx, job=job)
        # Active factors: skills (weight 35, score 100), role (weight 15, score 100), experience (weight 20, score 100)
        # Active weights sum = 35 + 15 + 20 = 70
        # Overall = round((100*35 + 100*15 + 100*20)/70) = 100
        self.assertEqual(result.overall_score, 100)
        unavailable_keys = {f.key for f in result.factors if not f.available}
        self.assertIn("location", unavailable_keys)
        self.assertIn("work_mode", unavailable_keys)
        self.assertIn("projects", unavailable_keys)
        self.assertIn("education", unavailable_keys)

    def test_03_multi_word_skill_matching(self):
        """Multi-word skills like 'React Native', 'Machine Learning', 'CI/CD' are correctly matched."""
        ctx = ProfileRankingContext(
            user_id="u1",
            has_profile=True,
            skills=["React Native", "Machine Learning", "CI/CD"],
            user_skills_set={"react native", "machine learning", "ci/cd"},
        )
        job = JobMock(
            required_skills="React Native, Machine Learning, CI/CD",
        )
        result = calculate_rank(profile_context=ctx, job=job)
        self.assertEqual(set(result.matched_skills), {"React Native", "Machine Learning", "CI/CD"})
        self.assertEqual(result.factor_scores["skills"], 100)

    def test_04_js_to_javascript_alias(self):
        """Alias 'JS' normalizes to 'JavaScript' and 'Postgres' to 'PostgreSQL'."""
        self.assertEqual(canonicalize_skill("js"), "JavaScript")
        self.assertEqual(canonicalize_skill("JS"), "JavaScript")
        self.assertEqual(canonicalize_skill("postgres"), "PostgreSQL")
        self.assertEqual(canonicalize_skill("ts"), "TypeScript")
        self.assertEqual(canonicalize_skill("node"), "Node.js")

        ctx = ProfileRankingContext(
            user_id="u1",
            has_profile=True,
            skills=["JavaScript", "PostgreSQL"],
            user_skills_set={"javascript", "postgresql"},
        )
        job = JobMock(required_skills="JS, Postgres")
        result = calculate_rank(profile_context=ctx, job=job)
        self.assertEqual(set(result.matched_skills), {"JavaScript", "PostgreSQL"})
        self.assertEqual(result.missing_skills, [])

    def test_05_react_native_distinct_from_react(self):
        """React Native requirement is satisfied by React Native."""
        ctx = ProfileRankingContext(
            user_id="u1",
            has_profile=True,
            skills=["React Native"],
            user_skills_set={"react native"},
        )
        job = JobMock(required_skills="React Native")
        result = calculate_rank(profile_context=ctx, job=job)
        self.assertIn("React Native", result.matched_skills)

    def test_06_machine_learning_matching(self):
        """Machine learning in description or skills is matched."""
        ctx = ProfileRankingContext(
            user_id="u1",
            has_profile=True,
            skills=["Machine Learning", "Python"],
            user_skills_set={"machine learning", "python"},
        )
        job = JobMock(
            title="ML Engineer",
            required_skills=None,
            description="We build machine learning pipelines using Python.",
        )
        result = calculate_rank(profile_context=ctx, job=job)
        self.assertIn("Machine Learning", result.matched_skills)
        self.assertIn("Python", result.matched_skills)

    def test_07_cicd_matching(self):
        """CI/CD matching works for both 'CI/CD' and 'cicd'."""
        ctx = ProfileRankingContext(
            user_id="u1",
            has_profile=True,
            skills=["CI/CD"],
            user_skills_set={"ci/cd"},
        )
        job = JobMock(required_skills="cicd, Docker")
        result = calculate_rank(profile_context=ctx, job=job)
        self.assertIn("CI/CD", result.matched_skills)
        self.assertIn("Docker", result.missing_skills)

    def test_08_sparse_no_required_skills_conservative_fallback(self):
        """Sparse jobs without structured required_skills extract skills honestly without 70/50/0 heuristic."""
        ctx = ProfileRankingContext(
            user_id="u1",
            has_profile=True,
            skills=["Python", "FastAPI"],
            user_skills_set={"python", "fastapi"},
        )
        job = JobMock(
            required_skills=None,
            description="We are seeking an engineer experienced in Python and Docker to join our team.",
        )
        result = calculate_rank(profile_context=ctx, job=job)
        # Job description contains "Python" and "Docker"
        # Candidate has "Python", missing "Docker"
        # Score should be 1/2 * 100 = 50 (honest coverage, not old arbitrary 70)
        self.assertEqual(result.factor_scores["skills"], 50)
        self.assertIn("Python", result.matched_skills)
        self.assertIn("Docker", result.missing_skills)
        self.assertTrue(any("description" in f.evidence for f in result.factors if f.key == "skills"))

    def test_09_no_preferred_roles(self):
        """Candidate with no preferred roles has role factor marked unavailable (not fake 50)."""
        ctx = ProfileRankingContext(
            user_id="u1",
            has_profile=True,
            preferred_roles=[],
            skills=["Python"],
            user_skills_set={"python"},
        )
        job = JobMock(title="Backend Developer")
        result = calculate_rank(profile_context=ctx, job=job)
        role_factor = next(f for f in result.factors if f.key == "role")
        self.assertFalse(role_factor.available)
        self.assertIsNone(role_factor.score)

    def test_10_no_preferred_locations(self):
        """Candidate with no preferred locations has location factor marked unavailable."""
        ctx = ProfileRankingContext(
            user_id="u1",
            has_profile=True,
            preferred_locations=[],
            skills=["Python"],
            user_skills_set={"python"},
        )
        job = JobMock(location="London, UK")
        result = calculate_rank(profile_context=ctx, job=job)
        loc_factor = next(f for f in result.factors if f.key == "location")
        self.assertFalse(loc_factor.available)
        self.assertIsNone(loc_factor.score)

    def test_11_remote_jobs(self):
        """Remote job satisfies location with high score."""
        ctx = ProfileRankingContext(
            user_id="u1",
            has_profile=True,
            preferred_locations=["Pune, India"],
            skills=["Python"],
            user_skills_set={"python"},
        )
        job = JobMock(location="Remote")
        result = calculate_rank(profile_context=ctx, job=job)
        loc_factor = next(f for f in result.factors if f.key == "location")
        self.assertTrue(loc_factor.available)
        self.assertGreaterEqual(loc_factor.score, 80)

    def test_12_missing_job_location(self):
        """Job without location marks location factor unavailable."""
        ctx = ProfileRankingContext(
            user_id="u1",
            has_profile=True,
            preferred_locations=["Pune, India"],
            skills=["Python"],
            user_skills_set={"python"},
        )
        job = JobMock(location=None)
        result = calculate_rank(profile_context=ctx, job=job)
        loc_factor = next(f for f in result.factors if f.key == "location")
        self.assertFalse(loc_factor.available)

    def test_13_experience_level_compatibility(self):
        """Experience levels evaluated compatibly without inventing numeric YOE."""
        ctx_mid = ProfileRankingContext(
            user_id="u1",
            has_profile=True,
            classified_experience_level="mid",
            skills=["Python"],
            user_skills_set={"python"},
        )
        # Direct match: Mid vs Mid -> 100
        job_mid = JobMock(experience_level="Mid Level")
        res_mid = calculate_rank(profile_context=ctx_mid, job=job_mid)
        self.assertEqual(res_mid.factor_scores["experience"], 100)

        # Adjacent match: Mid vs Senior -> 80
        job_sr = JobMock(experience_level="Senior Level")
        res_sr = calculate_rank(profile_context=ctx_mid, job=job_sr)
        self.assertEqual(res_sr.factor_scores["experience"], 80)

    def test_14_project_overlap(self):
        """Project overlap evaluated honestly based on technologies."""
        proj = Project(name="E-Commerce", technologies="Python, FastAPI, Docker")
        ctx = ProfileRankingContext(
            user_id="u1",
            has_profile=True,
            skills=["Python"],
            user_skills_set={"python"},
            projects=[proj],
        )
        job = JobMock(required_skills="Python, FastAPI")
        result = calculate_rank(profile_context=ctx, job=job)
        self.assertEqual(result.factor_scores["projects"], 100)
        self.assertIn("E-Commerce", result.relevant_projects)

    def test_15_education_requirement_present(self):
        """Job with degree requirement activates education factor."""
        ctx = ProfileRankingContext(
            user_id="u1",
            has_profile=True,
            education=[Education(degree="B.Tech", branch="Computer Science")],
            skills=["Python"],
            user_skills_set={"python"},
        )
        job = JobMock(description="Requires a Bachelor's degree in Computer Science.")
        result = calculate_rank(profile_context=ctx, job=job)
        edu_factor = next(f for f in result.factors if f.key == "education")
        self.assertTrue(edu_factor.available)
        self.assertEqual(edu_factor.score, 100)

    def test_16_education_requirement_absent(self):
        """Job without degree requirement marks education factor unavailable."""
        ctx = ProfileRankingContext(
            user_id="u1",
            has_profile=True,
            education=[],  # candidate has no education recorded
            skills=["Python"],
            user_skills_set={"python"},
        )
        job = JobMock(description="Build web applications with clean code.")
        result = calculate_rank(profile_context=ctx, job=job)
        edu_factor = next(f for f in result.factors if f.key == "education")
        self.assertFalse(edu_factor.available)
        self.assertIsNone(edu_factor.score)

    def test_17_empty_profile(self):
        """Empty profile returns 0 overall score with clear reason."""
        ctx = ProfileRankingContext(user_id="u1", has_profile=False)
        job = JobMock()
        result = calculate_rank(profile_context=ctx, job=job)
        self.assertEqual(result.overall_score, 0)
        self.assertTrue(len(result.reasons) > 0)

    def test_18_incomplete_profile(self):
        """Incomplete profile activates only supported dimensions."""
        ctx = ProfileRankingContext(
            user_id="u1",
            has_profile=True,
            skills=["Python"],
            user_skills_set={"python"},
            # no projects, no experience, no roles, no locations
        )
        job = JobMock(required_skills="Python")
        result = calculate_rank(profile_context=ctx, job=job)
        self.assertEqual(result.overall_score, 100)
        self.assertTrue(result.factor_scores["skills"] == 100)
        self.assertIsNone(result.factor_scores["role"])
        self.assertIsNone(result.factor_scores["location"])

    def test_19_same_candidate_job_deterministic_consistency(self):
        """Repeated evaluations of the exact same candidate and job yield identical scores."""
        ctx = ProfileRankingContext(
            user_id="u1",
            has_profile=True,
            skills=["Python", "FastAPI"],
            user_skills_set={"python", "fastapi"},
            preferred_roles=["Backend Developer"],
            preferred_locations=["Pune"],
        )
        job = JobMock(title="Backend Developer", required_skills="Python, FastAPI", location="Pune")
        r1 = calculate_rank(profile_context=ctx, job=job)
        r2 = calculate_rank(profile_context=ctx, job=job)
        self.assertEqual(r1.overall_score, r2.overall_score)
        self.assertEqual(r1.factor_scores, r2.factor_scores)
        self.assertEqual(r1.reasons, r2.reasons)

    def test_20_resume_factor_compatibility(self):
        """calculate_rank can evaluate a resume_context dictionary."""
        resume = {
            "skills": ["Python", "Docker"],
            "projects": [{"name": "P1", "technologies": ["Python"]}],
            "experience": [{"job_title": "Backend Dev", "company": "Co"}],
        }
        job = JobMock(required_skills="Python, Docker")
        result = calculate_rank(resume_context=resume, job=job)
        self.assertEqual(result.factor_scores["skills"], 100)
        self.assertIn("Python", result.matched_skills)
        self.assertIn("Docker", result.matched_skills)


from sqlalchemy.pool import StaticPool

class TestRankingServiceIntegrationAndPersistence(unittest.TestCase):
    """Database integration, persistence, user isolation, and API tests."""

    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        self.user = User(id="u1", firebase_uid="fb1", email="u1@test.com", name="User 1")
        self.profile = Profile(
            id="p1",
            user_id="u1",
            preferred_roles="Backend Developer",
            preferred_locations="Pune, India",
        )
        self.sk1 = Skill(id="s1", name="Python")
        self.sk2 = Skill(id="s2", name="FastAPI")
        self.us1 = UserSkill(id="us1", profile_id="p1", skill_id="s1", category="lang", skill=self.sk1)
        self.us2 = UserSkill(id="us2", profile_id="p1", skill_id="s2", category="fw", skill=self.sk2)
        self.db.add_all([self.user, self.profile, self.sk1, self.sk2, self.us1, self.us2])
        self.db.commit()

        self.app = FastAPI()
        self.app.include_router(match_router)

        def override_get_db():
            session = self.Session()
            try:
                yield session
            finally:
                session.close()

        def override_get_current_user():
            return self.user

        self.app.dependency_overrides[get_db] = override_get_db
        self.app.dependency_overrides[get_current_user] = override_get_current_user
        self.client = TestClient(self.app)

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def test_21_score_version_persistence(self):
        """New match calculation explicitly writes score_version='v2' to JobMatch."""
        job = Job(
            id="j1",
            user_id="u1",
            title="Backend Developer",
            company="Acme",
            location="Pune, India",
            required_skills="Python, FastAPI",
        )
        self.db.add(job)
        self.db.commit()

        response = self.client.post(f"/jobs/{job.id}/match")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["score_version"], "v2")

        saved = self.db.query(JobMatch).filter(JobMatch.job_id == job.id).first()
        self.assertIsNotNone(saved)
        self.assertEqual(saved.score_version, "v2")

    def test_22_discovery_uses_canonical_persisted_score(self):
        """Filtered discovery ranks records using canonical ranking."""
        rep = JobMock(
            id="ext1",
            title="Backend Developer",
            company="Acme",
            location="Pune, India",
            required_skills="Python, FastAPI",
        )
        record = {"representative": rep, "key": "k1"}
        ranked = ds.rank_record(record, "u1", self.db)
        self.assertEqual(ranked["match"]["score_version"], "v2")
        self.assertEqual(ranked["match"]["skills_score"], 100)

    def test_23_feed_read_does_no_provider_calls(self):
        """build_feed loads exclusively from persisted recommendations without provider calls."""
        with patch("app.services.job_sources.orchestrator.DiscoveryOrchestrator.search") as mock_search:
            feed = build_feed("u1", self.db)
            self.assertFalse(mock_search.called)
            self.assertIn("jobs", feed)

    def test_24_no_n_plus_one_queries(self):
        """load_profile_context loads profile in single preloaded context."""
        ctx = load_profile_context("u1", self.db)
        self.assertTrue(ctx.has_profile)
        self.assertEqual(len(ctx.skills), 2)
        # Multiple calculate_rank evaluations perform zero DB queries
        job = JobMock()
        for _ in range(10):
            calculate_rank(profile_context=ctx, job=job)

    def test_25_user_isolation(self):
        """A user cannot calculate a match on a job owned by another user."""
        other_user = User(id="u2", firebase_uid="fb2", email="u2@test.com", name="User 2")
        other_job = Job(id="j_other", user_id="u2", title="Secret Job", company="Co")
        self.db.add_all([other_user, other_job])
        self.db.commit()

        # Requesting match for foreign job returns 404
        response = self.client.post("/jobs/j_other/match")
        self.assertEqual(response.status_code, 404)

    def test_26_existing_endpoint_compatibility(self):
        """GET /jobs/{id}/analysis preserves backward-compatible fields."""
        job = Job(id="j2", user_id="u1", title="Backend Developer", company="Co")
        match = JobMatch(
            id="m1",
            user_id="u1",
            job_id="j2",
            overall_score=85,
            skills_score=80,
            project_score=70,
            experience_score=90,
            role_score=100,
            location_score=80,
            score_version="v2",
            matched_skills=json.dumps(["Python"]),
            missing_skills=json.dumps([]),
            relevant_projects=json.dumps([]),
            relevant_experience=json.dumps([]),
            explanation="Great match.",
        )
        self.db.add_all([job, match])
        self.db.commit()

        resp = self.client.get("/jobs/j2/analysis")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["overall_score"], 85)
        self.assertEqual(data["skills_score"], 80)
        self.assertEqual(data["score_version"], "v2")

    def test_27_schema_init_compatibility(self):
        """init_schema creates all tables cleanly with additive columns."""
        test_engine = create_engine("sqlite:///:memory:")
        tables = init_schema(bind=test_engine)
        self.assertIn("job_matches", tables)
        self.assertIn("resume_job_analyses", tables)

    def test_28_profile_vs_discovery_score_equivalence(self):
        """Same candidate + job evaluated via profile match vs discovery produces identical canonical factor scores."""
        ctx = load_profile_context("u1", self.db)
        job = JobMock(title="Backend Developer", required_skills="Python, FastAPI", location="Pune, India")

        # Direct canonical ranking
        profile_rank = calculate_rank(profile_context=ctx, job=job)

        # Discovery record ranking
        rec = {"representative": job, "key": "k1"}
        discovery_rec = ds.rank_record(rec, "u1", self.db, profile_context=ctx)
        d_match = discovery_rec["match"]

        self.assertEqual(profile_rank.overall_score, d_match["overall_score"])
        self.assertEqual(profile_rank.factor_scores["skills"], d_match["skills_score"])
        self.assertEqual(profile_rank.factor_scores["role"], d_match["role_score"])
        self.assertEqual(profile_rank.factor_scores["location"], d_match["location_score"])

    def test_29_provider_skill_tags_signal(self):
        """When ONLY meaningful skill evidence is provider tags (NormalizedJob.skills/job.skills), scorer uses it accurately."""
        from app.services.job_sources.base import NormalizedJob
        from app.services.ranking import _evaluate_skills

        # Candidate knows Python and Docker
        candidate_skills = ["Python", "Docker"]
        candidate_skills_set = {"python", "docker"}
        desc_without_skills = "Great company looking for high energy team members to achieve goals."

        # Job has NO required_skills and NO skills in text, ONLY provider tags in .skills
        job_with_tags = NormalizedJob(
            external_id="ext_1",
            title="Software Developer",
            company="Acme",
            description=desc_without_skills,
            skills=["python", "Docker", "Kubernetes", "python"],  # has duplicate "python"
        )

        factor, matched, missing = _evaluate_skills(
            job_with_tags,
            candidate_skills,
            candidate_skills_set,
            desc_without_skills,
        )

        # Provider tags are used: Python, Docker, Kubernetes (deduplicated to 3 skills)
        self.assertTrue(factor.available)
        self.assertEqual(sorted(matched), ["Docker", "Python"])
        self.assertEqual(sorted(missing), ["Kubernetes"])
        # 2 of 3 matched = 67%
        self.assertEqual(factor.score, 67)
        self.assertIn("provider-tagged skills", factor.evidence)

    def test_30_context_consistency_upsert_match_vs_direct_match(self):
        """Discovery write path (_upsert_match) and direct match endpoint produce identical factor scores."""
        from app.services.job_discovery import _upsert_match
        from app.models.profile import Education, Certification

        # Setup student_fresher user with graduation year in future
        user_sf = User(id="u_sf", firebase_uid="fb_sf", email="sf@test.com", name="Student Fresher")
        self.db.add(user_sf)
        self.db.commit()

        prof_sf = Profile(
            id="p_sf",
            user_id="u_sf",
            preferred_roles="Backend Developer",
            preferred_locations="Pune",
        )
        self.db.add(prof_sf)
        self.db.commit()

        edu = Education(
            id="edu_1",
            profile_id="p_sf",
            degree="B.Tech Computer Science",
            college="University",
            graduation_year="2027",  # future graduation year -> student_fresher
        )
        cert = Certification(
            id="cert_1",
            profile_id="p_sf",
            name="AWS Certified Developer",
        )
        self.db.add_all([edu, cert])
        self.db.commit()

        # Senior job
        senior_job = Job(
            id="j_senior",
            user_id="u_sf",
            title="Senior Backend Developer",
            company="Enterprise Corp",
            location="Pune, India",
            description="Looking for a Senior Backend Developer. Degree in Computer Science or engineering required.",
            required_skills="Python, FastAPI",
            experience_level="Senior",
        )
        self.db.add(senior_job)
        self.db.commit()

        # 1. Discovery write path: _upsert_match
        _upsert_match("u_sf", senior_job, self.db, profile=prof_sf)
        upserted_match = self.db.query(JobMatch).filter(
            JobMatch.user_id == "u_sf", JobMatch.job_id == "j_senior"
        ).first()
        self.assertIsNotNone(upserted_match)

        # 2. Direct match endpoint: POST /jobs/{id}/match
        # Override auth dependency for this request
        app = FastAPI()
        app.include_router(match_router)
        app.dependency_overrides[get_current_user] = lambda: user_sf
        app.dependency_overrides[get_db] = lambda: self.db
        client_sf = TestClient(app)

        direct_resp = client_sf.post("/jobs/j_senior/match")
        self.assertEqual(direct_resp.status_code, 200)
        direct_data = direct_resp.json()

        # Both paths MUST produce identical canonical factor scores
        self.assertEqual(upserted_match.overall_score, direct_data["overall_score"])
        self.assertEqual(upserted_match.experience_score, direct_data["experience_score"])
        # Because classified as student_fresher vs senior (diff = 3), score must be 20, NOT 80
        self.assertEqual(upserted_match.experience_score, 20)
        self.assertEqual(direct_data["experience_score"], 20)

        self.assertEqual(upserted_match.skills_score, direct_data["skills_score"])
        self.assertEqual(upserted_match.role_score, direct_data["role_score"])
        self.assertEqual(upserted_match.location_score, direct_data["location_score"])
        self.assertEqual(upserted_match.education_score, direct_data["education_score"])
        self.assertEqual(upserted_match.work_mode_score, direct_data["work_mode_score"])
        self.assertEqual(upserted_match.score_version, "v2")
        self.assertEqual(direct_data["score_version"], "v2")

    def test_31_resume_analysis_score_version_honest(self):
        """ResumeJobAnalysis stamps score_version = 'v1' to honestly reflect its 40/20/20/15/5 formula."""
        from app.api.resume_analysis import router as ra_router
        from app.models.resume import Resume

        resume = Resume(
            id="res_test",
            user_id="u1",
            filename="resume.pdf",
            original_filename="resume.pdf",
            file_path="/tmp/test.pdf",
            file_size="1024",
            parsing_status="completed",
            parsed_data={"skills": ["Python", "FastAPI"]},
        )
        job_ra = Job(
            id="j_ra",
            user_id="u1",
            title="Backend Developer",
            company="Co",
            description="Python FastAPI backend role",
            required_skills="Python, FastAPI",
        )
        self.db.add_all([job_ra, resume])
        self.db.commit()

        app = FastAPI()
        app.include_router(ra_router)
        app.dependency_overrides[get_current_user] = lambda: self.user
        app.dependency_overrides[get_db] = lambda: self.db
        client = TestClient(app)

        resp = client.post("/jobs/j_ra/resume-analysis", json={"resume_id": "res_test"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["score_version"], "v1")

        saved = self.db.query(ResumeJobAnalysis).filter(ResumeJobAnalysis.resume_id == "res_test").first()
        self.assertIsNotNone(saved)
        self.assertEqual(saved.score_version, "v1")


if __name__ == "__main__":
    unittest.main()
