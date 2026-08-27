import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database.base import Base
from app.models.user import User
from app.models.profile import Profile, Skill, UserSkill, Project, Experience, Education
from app.models.job import Job
from app.models.job_match import JobMatch
from app.services.job_sources.base import NormalizedJob
from app.services.personalized_discovery import (
    resolve_country_and_location,
    classify_experience_level,
    infer_roles_from_skills_and_projects,
    PersonalizedQueryBuilder,
    PersonalizedDiscoveryService,
)
from app.services.job_discovery import get_recommended_jobs, discover_jobs


class TestPersonalizedDiscoveryUnit(unittest.TestCase):
    def test_country_resolution(self):
        # Indian cities
        country, locs = resolve_country_and_location("Pune, India", "Bangalore, Remote")
        self.assertEqual(country, "in")
        self.assertIn("Bangalore", locs[0])

        # UK
        country, locs = resolve_country_and_location("London", "UK")
        self.assertEqual(country, "gb")

        # US
        country, locs = resolve_country_and_location("San Francisco, CA", "USA")
        self.assertEqual(country, "us")

        # Remote / No country
        country, locs = resolve_country_and_location("Remote", "Remote")
        self.assertIsNone(country)
        self.assertEqual(locs, ["Remote", "Remote"])

    def test_experience_classification(self):
        # Student / Fresher with current/future grad year
        exp_level = classify_experience_level("2026", [])
        self.assertEqual(exp_level, "student_fresher")

        # Junior with 1 experience
        exp = Experience(company="Acme", role="Junior Dev")
        exp_level = classify_experience_level("2023", [exp])
        self.assertEqual(exp_level, "junior")

        # Mid with 2-3 experiences
        exps = [Experience(company=f"Co{i}", role="Dev") for i in range(3)]
        exp_level = classify_experience_level("2020", exps)
        self.assertEqual(exp_level, "mid")

    def test_role_inference_backend(self):
        skills = ["Python", "FastAPI", "PostgreSQL", "Redis"]
        proj = Project(name="Task Queue", technologies="Python, Redis, Docker")
        inferred = infer_roles_from_skills_and_projects(skills, [proj], [])
        self.assertIn("Backend Developer", inferred)
        self.assertIn("Python Developer", inferred)

    def test_role_inference_frontend(self):
        skills = ["React", "TypeScript", "Tailwind CSS", "Next.js"]
        inferred = infer_roles_from_skills_and_projects(skills, [], [])
        self.assertIn("Frontend Developer", inferred)

    def test_role_inference_fullstack(self):
        skills = ["React", "FastAPI", "TypeScript", "PostgreSQL"]
        inferred = infer_roles_from_skills_and_projects(skills, [], [])
        self.assertIn("Full Stack Developer", inferred)

    def test_role_inference_data_analyst(self):
        skills = ["Python", "SQL", "Pandas", "PowerBI"]
        inferred = infer_roles_from_skills_and_projects(skills, [], [])
        self.assertIn("Data Analyst", inferred)

    def test_preferred_roles_priority(self):
        profile = Profile(preferred_roles="Backend Developer, Python Engineer", preferred_locations="Pune")
        skills = ["Python", "FastAPI", "SQL"]
        queries = PersonalizedQueryBuilder.build_queries(profile, skills, [], [], [])

        # Preferred roles must appear in generated queries
        self.assertIn("Backend Developer", queries)
        self.assertIn("Python Engineer", queries)
        self.assertLessEqual(len(queries), 6)

    def test_skill_based_fallback_when_no_preferred_roles(self):
        profile = Profile(preferred_roles=None, preferred_locations="Remote")
        skills = ["Python", "FastAPI"]
        queries = PersonalizedQueryBuilder.build_queries(profile, skills, [], [], [])

        self.assertTrue(len(queries) >= 1)
        self.assertTrue(any("Python" in q for q in queries))

    def test_incomplete_profile_safe_fallback(self):
        profile = Profile(preferred_roles=None, preferred_locations=None)
        queries = PersonalizedQueryBuilder.build_queries(profile, [], [], [], [])
        self.assertEqual(queries, [])

    def test_query_deduplication_and_normalization(self):
        profile = Profile(preferred_roles="Python Developer, python developer, Developer Python", preferred_locations=None)
        skills = ["Python"]
        queries = PersonalizedQueryBuilder.build_queries(profile, skills, [], [], [])

        # Must not have duplicates
        lower_queries = [q.lower() for q in queries]
        self.assertEqual(len(lower_queries), len(set(lower_queries)))
        self.assertNotIn("job", lower_queries)
        self.assertNotIn("developer", lower_queries)

    def test_experience_modifiers(self):
        profile = Profile(preferred_roles="Python Developer", preferred_locations="Pune")
        edu = [Education(degree="B.Tech", college="College", graduation_year="2026")]
        queries = PersonalizedQueryBuilder.build_queries(profile, ["Python"], [], [], edu)

        # Must generate 1-2 junior modified queries
        self.assertTrue(any("Junior Python Developer" in q for q in queries))

    @patch("app.services.personalized_discovery.AdzunaSource")
    @patch("app.services.personalized_discovery.JobicySource")
    def test_source_failure_resilience(self, MockJobicy, MockAdzuna):
        mock_adzuna = MagicMock()
        mock_adzuna.fetch.side_effect = Exception("Adzuna API timeout")
        MockAdzuna.return_value = mock_adzuna

        mock_jobicy = MagicMock()
        mock_jobicy.fetch.return_value = []
        MockJobicy.return_value = mock_jobicy

        db = MagicMock()
        mock_profile = Profile(user_id="user_123", preferred_roles="Python Developer", preferred_locations="Pune")
        db.query.return_value.filter.return_value.first.return_value = mock_profile
        db.query.return_value.filter.return_value.all.return_value = []

        result = PersonalizedDiscoveryService.discover("user_123", db)

        # Should record error and continue without crash
        self.assertEqual(result["sources"]["Jobicy"], 0)
        self.assertTrue(len(result["errors"]) > 0)
        self.assertIn("Adzuna API timeout", result["errors"][0])


class TestMultiUserIntegrationAndRanking(unittest.TestCase):
    def setUp(self):
        # Create in-memory SQLite database for full integration testing
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        # Seed User A (Python / Backend Developer with projects & experience)
        self.user_a = User(id="user_a", firebase_uid="fb_uid_a", email="user_a@test.com", name="User A")
        self.profile_a = Profile(id="prof_a", user_id="user_a", preferred_roles="Backend Developer", preferred_locations="Pune")
        self.skill_py = Skill(id="skill_1", name="Python")
        self.skill_fa = Skill(id="skill_2", name="FastAPI")
        self.user_skill_a1 = UserSkill(id="us_a1", profile_id="prof_a", skill_id="skill_1", category="Programming Languages", skill=self.skill_py)
        self.user_skill_a2 = UserSkill(id="us_a2", profile_id="prof_a", skill_id="skill_2", category="Frameworks/Libraries", skill=self.skill_fa)
        self.proj_a = Project(id="proj_a1", profile_id="prof_a", name="FastAPI Microservices", technologies="Python, FastAPI, Redis")
        self.exp_a = Experience(id="exp_a1", profile_id="prof_a", company="Tech Corp", role="Backend Engineer", technologies="Python, FastAPI")

        # Seed User B (React / Frontend Developer)
        self.user_b = User(id="user_b", firebase_uid="fb_uid_b", email="user_b@test.com", name="User B")
        self.profile_b = Profile(id="prof_b", user_id="user_b", preferred_roles="Frontend Developer", preferred_locations="Pune")
        self.skill_react = Skill(id="skill_3", name="React")
        self.skill_ts = Skill(id="skill_4", name="TypeScript")
        self.user_skill_b1 = UserSkill(id="us_b1", profile_id="prof_b", skill_id="skill_3", category="Frameworks/Libraries", skill=self.skill_react)
        self.user_skill_b2 = UserSkill(id="us_b2", profile_id="prof_b", skill_id="skill_4", category="Programming Languages", skill=self.skill_ts)

        self.db.add_all([
            self.user_a, self.profile_a, self.skill_py, self.skill_fa, self.user_skill_a1, self.user_skill_a2, self.proj_a, self.exp_a,
            self.user_b, self.profile_b, self.skill_react, self.skill_ts, self.user_skill_b1, self.user_skill_b2,
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    @patch("app.services.personalized_discovery.AdzunaSource")
    @patch("app.services.personalized_discovery.JobicySource")
    def test_multi_user_discovery_global_deduplication_and_score_isolation(self, MockJobicy, MockAdzuna):
        """
        Critical Test Case:
        1. User A runs discovery -> discovers Job X (Python Backend role).
        2. User B runs discovery -> discovers the same Job X.
        3. Verify only 1 global Job row exists.
        4. Verify User A and User B each have independent JobMatch records.
        5. Verify User A has a high score for Python role, while User B has a lower score.
        6. Verify User A's match was not overwritten.
        """
        sample_job_x = NormalizedJob(
            external_id="ext_999",
            title="Senior Python Backend Developer",
            company="Stripe Inc",
            location="Pune, India",
            description="Looking for Senior Python Backend Developer proficient in Python and FastAPI.",
            employment_type="Full-time",
            experience_level="Mid",
            application_url="https://stripe.com/jobs/999",
            source="Adzuna",
            posted_at="2026-08-20T10:00:00Z",
        )

        mock_adzuna = MagicMock()
        mock_adzuna.fetch.return_value = [sample_job_x]
        MockAdzuna.return_value = mock_adzuna

        mock_jobicy = MagicMock()
        mock_jobicy.fetch.return_value = []
        MockJobicy.return_value = mock_jobicy

        # 1. User A runs personalized discovery
        res_a = PersonalizedDiscoveryService.discover("user_a", self.db)
        self.assertEqual(res_a["new_jobs"], 1)
        self.assertEqual(res_a["existing_jobs"], 0)
        self.assertEqual(res_a["matches_created"], 1)

        # Check Job in DB
        jobs_in_db = self.db.query(Job).all()
        self.assertEqual(len(jobs_in_db), 1)
        job_x = jobs_in_db[0]
        self.assertEqual(job_x.external_id, "ext_999")

        # Check User A's match
        match_a = self.db.query(JobMatch).filter(JobMatch.user_id == "user_a", JobMatch.job_id == job_x.id).first()
        self.assertIsNotNone(match_a)
        score_a_initial = match_a.overall_score
        self.assertGreater(score_a_initial, 50)  # Python dev matches Python job well

        # 2. User B runs personalized discovery (receives same Job X)
        res_b = PersonalizedDiscoveryService.discover("user_b", self.db)
        self.assertEqual(res_b["new_jobs"], 0)
        self.assertEqual(res_b["existing_jobs"], 1)  # Recognized as existing!
        self.assertEqual(res_b["matches_created"], 1)  # Created match for User B!

        # 3. Verify only 1 global Job row exists
        jobs_in_db_after_b = self.db.query(Job).all()
        self.assertEqual(len(jobs_in_db_after_b), 1)

        # 4. Verify User B has their own independent JobMatch
        match_b = self.db.query(JobMatch).filter(JobMatch.user_id == "user_b", JobMatch.job_id == job_x.id).first()
        self.assertIsNotNone(match_b)
        self.assertNotEqual(match_a.id, match_b.id)

        # 5. Verify User A's match score was NOT overwritten or altered
        match_a_after = self.db.query(JobMatch).filter(JobMatch.user_id == "user_a", JobMatch.job_id == job_x.id).first()
        self.assertEqual(match_a_after.overall_score, score_a_initial)

        # 6. Verify User B has different score calculated from User B's profile
        # User B has React/TypeScript skills and Frontend preferred role, so match score should be lower than User A
        self.assertLess(match_b.overall_score, match_a_after.overall_score)

    def test_get_recommended_jobs_isolation_and_multi_tier_ranking(self):
        """
        Verify that GET /jobs/recommended:
        1. Returns ONLY the requesting user's matches (zero data leakage).
        2. Ranks primarily by match score (overall_score desc).
        3. Ranks secondarily by role alignment (role_score desc).
        4. Ranks tertiarily by freshness (posted_at desc).
        """
        now = datetime.now(timezone.utc)
        earlier = now - timedelta(days=5)

        job_1 = Job(id="j1", user_id="user_a", title="Python Dev", company="A", posted_at=earlier, created_at=earlier)
        job_2 = Job(id="j2", user_id="user_a", title="Backend Dev", company="B", posted_at=now, created_at=now)
        job_3 = Job(id="j3", user_id="user_a", title="Staff Engineer", company="C", posted_at=now, created_at=now)

        # User A matches:
        # job_1: score 85, role 80, earlier
        # job_2: score 85, role 100, now  (should rank higher than job_1 due to role alignment)
        # job_3: score 95, role 50, now   (should rank #1 overall due to overall_score 95)
        m_a1 = JobMatch(id="ma1", user_id="user_a", job_id="j1", overall_score=85, role_score=80)
        m_a2 = JobMatch(id="ma2", user_id="user_a", job_id="j2", overall_score=85, role_score=100)
        m_a3 = JobMatch(id="ma3", user_id="user_a", job_id="j3", overall_score=95, role_score=50)

        # User B match:
        m_b1 = JobMatch(id="mb1", user_id="user_b", job_id="j1", overall_score=40, role_score=30)

        self.db.add_all([job_1, job_2, job_3, m_a1, m_a2, m_a3, m_b1])
        self.db.commit()

        # Query recommendations for User A
        recs_a = get_recommended_jobs("user_a", self.db)
        self.assertEqual(len(recs_a), 3)
        # Rank 1: job_3 (overall_score 95)
        self.assertEqual(recs_a[0]["job"].id, "j3")
        self.assertEqual(recs_a[0]["match_score"], 95)
        # Rank 2: job_2 (overall_score 85, role_score 100)
        self.assertEqual(recs_a[1]["job"].id, "j2")
        self.assertEqual(recs_a[1]["match_score"], 85)
        # Rank 3: job_1 (overall_score 85, role_score 80)
        self.assertEqual(recs_a[2]["job"].id, "j1")
        self.assertEqual(recs_a[2]["match_score"], 85)

        # Query recommendations for User B
        recs_b = get_recommended_jobs("user_b", self.db)
        self.assertEqual(len(recs_b), 1)
        self.assertEqual(recs_b[0]["job"].id, "j1")
        self.assertEqual(recs_b[0]["match_score"], 40)

    @patch("app.services.job_discovery.AdzunaSource")
    @patch("app.services.job_discovery.JobicySource")
    def test_discover_jobs_execution(self, MockJobicy, MockAdzuna):
        sample_job = NormalizedJob(
            external_id="legacy_123",
            title="Backend Engineer",
            company="Acme Corp",
            location="Pune, India",
            description="Python FastAPI engineer needed",
            employment_type="Full-time",
            source="Adzuna",
        )
        mock_adzuna = MagicMock()
        mock_adzuna.fetch.return_value = [sample_job]
        MockAdzuna.return_value = mock_adzuna

        mock_jobicy = MagicMock()
        mock_jobicy.fetch.return_value = []
        MockJobicy.return_value = mock_jobicy

        result = discover_jobs("user_a", self.db)
        self.assertEqual(result["new_jobs"], 1)
        self.assertEqual(result["recommendations_updated"], 1)
        self.assertEqual(result["errors"], [])


if __name__ == "__main__":
    unittest.main()

