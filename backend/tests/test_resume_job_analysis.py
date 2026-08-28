import os
import tempfile
import shutil
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base, get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.resume import Resume
from app.models.job import Job
from app.models.resume_job_analysis import ResumeJobAnalysis
from app.services.resume_job_analysis import (
    analyze_resume_against_job,
    extract_keywords,
    WEIGHTS,
)
from app.services import matching
from app.api.resume_analysis import router as resume_analysis_router

RESUME = {
    "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "React"],
    "projects": [
        {
            "name": "E-commerce Platform",
            "technologies": ["Python", "FastAPI", "PostgreSQL"],
            "description": "Built REST APIs and a payment integration backend.",
        },
        {
            "name": "Mobile App",
            "technologies": ["React", "JavaScript"],
            "description": "Built a responsive mobile web interface.",
        },
    ],
    "experience": [
        {
            "job_title": "Backend Developer",
            "company": "Acme Corp",
            "dates": "2020 - Present",
            "description": "Built REST APIs with Python, FastAPI and PostgreSQL.",
        }
    ],
    "education": [
        {
            "degree": "B.Tech",
            "institution": "Example University",
            "field_of_study": "Computer Science",
            "graduation_year": "2020",
        }
    ],
    "certifications": ["AWS Certified Solutions Architect"],
}


class JobStub:
    def __init__(self, title="Backend Developer", description=None, required_skills=None,
                 experience_level=None):
        self.title = title
        self.company = "Test Corp"
        self.description = description
        self.required_skills = required_skills
        self.experience_level = experience_level


BACKEND_JOB = JobStub(
    title="Senior Backend Developer",
    description=(
        "We are looking for a Senior Backend Developer to build scalable REST APIs. "
        "Required: Python, FastAPI, PostgreSQL. Docker experience is preferred. "
        "Degree in Computer Science preferred."
    ),
    required_skills="Python, FastAPI, PostgreSQL, Docker",
    experience_level="Senior",
)


class TestSkillMatching(unittest.TestCase):
    def test_matched_and_missing_skills(self):
        result = analyze_resume_against_job(RESUME, BACKEND_JOB)
        self.assertIn("Python", result["matched_skills"])
        self.assertIn("FastAPI", result["matched_skills"])
        self.assertIn("PostgreSQL", result["matched_skills"])
        # Docker is in RESUME, so it should be matched, not missing.
        self.assertIn("Docker", result["matched_skills"])
        self.assertNotIn("Docker", result["missing_skills"])

    def test_missing_required_skill_detected(self):
        # Resume without Docker -> Docker and Kubernetes should both be missing.
        resume = {"skills": ["Python", "FastAPI", "PostgreSQL"]}
        job = JobStub(title="Role", description="Python Docker required",
                     required_skills="Python, FastAPI, PostgreSQL, Docker, Kubernetes")
        result = analyze_resume_against_job(resume, job)
        self.assertIn("Kubernetes", result["missing_skills"])
        self.assertIn("Docker", result["missing_skills"])
        self.assertIn("Python", result["matched_skills"])

    def test_case_insensitive_matching(self):
        resume = {"skills": ["python", "FASTAPI"]}
        job = JobStub(title="Role", required_skills="Python, fastAPI, POSTGRESQL")
        result = analyze_resume_against_job(resume, job)
        # Skills are matched case-insensitively; missing reported in canonical form.
        self.assertIn("Python", result["matched_skills"])
        self.assertIn("FastAPI", result["matched_skills"])
        self.assertIn("PostgreSQL", result["missing_skills"])

    def test_skill_alias_normalization(self):
        # PostgreSQL is present in resume (as 'Postgres'); should count as match.
        resume = {"skills": ["Postgres"]}
        job = JobStub(title="Role", required_skills="PostgreSQL")
        result = analyze_resume_against_job(resume, job)
        self.assertIn("PostgreSQL", result["matched_skills"])
        self.assertNotIn("PostgreSQL", result["missing_skills"])

    def test_no_false_equivalence(self):
        # React in resume must NOT satisfy an Angular requirement.
        resume = {"skills": ["React"]}
        job = JobStub(title="Role", required_skills="Angular")
        result = analyze_resume_against_job(resume, job)
        self.assertIn("Angular", result["missing_skills"])
        self.assertNotIn("Angular", result["matched_skills"])

    def test_additional_relevant_skills(self):
        result = analyze_resume_against_job(RESUME, BACKEND_JOB)
        # React is in the resume but not required by the job -> additional.
        self.assertIn("React", result["additional_relevant_skills"])


class TestKeywordAnalysis(unittest.TestCase):
    def test_keyword_extraction_avoids_stop_words(self):
        kws = extract_keywords("We are looking for a senior software developer with Python.")
        self.assertNotIn("we", kws)
        self.assertNotIn("the", kws)
        self.assertNotIn("looking", kws)
        self.assertTrue(any(k.lower() == "python" for k in kws))

    def test_keyword_matching(self):
        job = JobStub(
            title="Backend",
            description="Python FastAPI PostgreSQL microservices REST API",
        )
        result = analyze_resume_against_job(RESUME, job)
        matched_lower = [k.lower() for k in result["matched_keywords"]]
        self.assertIn("python", matched_lower)
        self.assertIn("fastapi", matched_lower)
        self.assertIn("postgresql", matched_lower)
        self.assertIn("rest", matched_lower)
        self.assertIn("api", matched_lower)
        # 'microservices' appears in the job but not in RESUME -> missing.
        missing_lower = [k.lower() for k in result["missing_keywords"]]
        self.assertTrue(any("microservices" in k for k in missing_lower))

    def test_missing_keyword_detected(self):
        job = JobStub(
            title="Backend",
            description="We heavily use Kubernetes and Kafka for event streaming.",
        )
        result = analyze_resume_against_job(RESUME, job)
        missing_lower = [k.lower() for k in result["missing_keywords"]]
        self.assertTrue(any("kubernetes" in k for k in missing_lower))

    def test_keyword_extraction_deduplicates(self):
        kws = extract_keywords("Python Python Python FastAPI FastAPI")
        lower = [k.lower() for k in kws]
        self.assertEqual(len(lower), len(set(lower)))


class TestExperienceAndProjectRelevance(unittest.TestCase):
    def test_relevant_experience_detected(self):
        result = analyze_resume_against_job(RESUME, BACKEND_JOB)
        self.assertTrue(result["relevant_experience"])
        self.assertIn("Backend Developer", result["relevant_experience"][0]["job_title"])

    def test_relevant_projects_detected_with_score(self):
        result = analyze_resume_against_job(RESUME, BACKEND_JOB)
        projs = result["relevant_projects"]
        self.assertTrue(projs)
        ecommerce = [p for p in projs if p["name"] == "E-commerce Platform"]
        self.assertTrue(ecommerce)
        self.assertGreaterEqual(ecommerce[0]["relevance_score"], 0)
        self.assertIn("FastAPI", ecommerce[0]["matched_technologies"])

    def test_no_fabrication_of_experience(self):
        # Empty resume must produce no relevant experience/projects.
        result = analyze_resume_against_job({}, BACKEND_JOB)
        self.assertEqual(result["relevant_experience"], [])
        self.assertEqual(result["relevant_projects"], [])


class TestFairness(unittest.TestCase):
    def test_no_required_skills_infers_from_description(self):
        job = JobStub(title="Backend", description="We use Python and FastAPI.")
        result = analyze_resume_against_job(RESUME, job)
        self.assertTrue(result["scores"]["skills"] is not None)
        self.assertGreaterEqual(result["scores"]["skills"], 0)
        self.assertIn("Python", result["matched_skills"])

    def test_education_unavailable_is_fair(self):
        # Job with no education requirement -> education factor unavailable,
        # overall must still be computed purely from available factors.
        job = JobStub(title="Backend", description="Python FastAPI", required_skills="Python, FastAPI")
        result = analyze_resume_against_job(RESUME, job)
        self.assertIsNone(result["scores"]["education"])
        self.assertIsNotNone(result["overall_score"])

    def test_edu_requirement_present_and_matched(self):
        job = JobStub(
            title="Data Scientist",
            description="Requires a degree in Computer Science or Data Science.",
            required_skills="Python",
        )
        result = analyze_resume_against_job(RESUME, job)
        self.assertIsNotNone(result["scores"]["education"])

    def test_empty_job_returns_low_score_with_note(self):
        # No description, no required skills, no title signal -> analysis unavailable.
        job = JobStub(title="", description=None, required_skills=None)
        result = analyze_resume_against_job(RESUME, job)
        self.assertEqual(result["overall_score"], 10)
        self.assertIsNotNone(result["note"])

    def test_job_with_only_title_is_signal(self):
        # A bare job title is enough to judge experience relevance fairly.
        job = JobStub(title="Backend Developer", description=None, required_skills=None)
        result = analyze_resume_against_job(RESUME, job)
        self.assertIsNotNone(result["scores"]["experience"])
        self.assertIsNotNone(result["overall_score"])

    def test_weights_total_100(self):
        self.assertAlmostEqual(sum(WEIGHTS.values()), 1.0, places=6)
        self.assertEqual(list(WEIGHTS.keys()), ["skills", "keywords", "experience", "projects", "education"])


class TestScoreCalculation(unittest.TestCase):
    def test_perfect_overlap_scores_100(self):
        resume = {
            "skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
            "projects": [
                {"name": "P", "technologies": ["Python", "FastAPI", "PostgreSQL", "Docker"],
                 "description": "Built scalable REST APIs with microservices."}
            ],
            "experience": [
                {"job_title": "Backend Developer", "company": "C",
                 "description": "Built REST APIs with Python FastAPI PostgreSQL Docker microservices."}
            ],
            "education": [{"degree": "B.Tech", "field_of_study": "Computer Science"}],
        }
        job = JobStub(
            title="Backend Developer",
            description=(
                "Backend Developer. Python FastAPI PostgreSQL Docker REST APIs microservices. "
                "Degree in Computer Science."
            ),
            required_skills="Python, FastAPI, PostgreSQL, Docker",
        )
        result = analyze_resume_against_job(resume, job)
        # Near-perfect overlap across all available factors.
        self.assertGreaterEqual(result["overall_score"], 90)
        self.assertEqual(result["scores"]["skills"], 100)
        self.assertEqual(result["scores"]["keywords"], 100)
        self.assertEqual(result["scores"]["experience"], 100)
        self.assertEqual(result["scores"]["education"], 100)

    def test_score_stays_between_0_and_100(self):
        for resume in [RESUME, {}, {"skills": []}]:
            result = analyze_resume_against_job(resume, BACKEND_JOB)
            self.assertGreaterEqual(result["overall_score"], 0)
            self.assertLessEqual(result["overall_score"], 100)
            for key, value in result["scores"].items():
                if value is not None:
                    self.assertGreaterEqual(value, 0)
                    self.assertLessEqual(value, 100)

    def test_suggestions_are_evidence_based(self):
        job = JobStub(title="Backend", description="Python Docker", required_skills="Python, Docker, Kubernetes")
        result = analyze_resume_against_job(RESUME, job)
        self.assertTrue(3 <= len(result["suggestions"]) <= 7)
        self.assertTrue(any("Kubernetes" in s for s in result["suggestions"]))
        self.assertTrue(any("Docker" in s for s in result["suggestions"]))


class TestExistingMatchingUnchanged(unittest.TestCase):
    def test_matching_module_signature_unchanged(self):
        # Verify the original matching engine still exposes its public API.
        self.assertTrue(hasattr(matching, "calculate_match"))
        self.assertTrue(hasattr(matching, "parse_skills"))
        self.assertTrue(hasattr(matching, "normalize"))


class TestResumeOwnershipIsolationAndPersistence(unittest.TestCase):
    USER_A = {"id": "user_a", "firebase_uid": "fb_a"}
    USER_B = {"id": "user_b", "firebase_uid": "fb_b"}

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "analysis.db")
        self.engine = create_engine(
            f"sqlite:///{self.db_path}", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        db = self.Session()
        db.add_all([
            User(id=self.USER_A["id"], firebase_uid=self.USER_A["firebase_uid"], email="a@test.com", name="A"),
            User(id=self.USER_B["id"], firebase_uid=self.USER_B["firebase_uid"], email="b@test.com", name="B"),
        ])
        self.job = Job(id="job_1", user_id=self.USER_A["id"], title="Backend Developer",
                       company="Acme", description="Python FastAPI",
                       required_skills="Python, FastAPI")
        self.resume_a = Resume(
            id="res_a", user_id=self.USER_A["id"], filename="a.pdf",
            original_filename="a.pdf", file_path="/tmp/a.pdf", file_size="1",
            parsing_status="completed", parsed_data={"skills": ["Python", "FastAPI"]},
        )
        self.resume_b = Resume(
            id="res_b", user_id=self.USER_B["id"], filename="b.pdf",
            original_filename="b.pdf", file_path="/tmp/b.pdf", file_size="1",
            parsing_status="completed", parsed_data={"skills": ["React"]},
        )
        db.add_all([self.job, self.resume_a, self.resume_b])
        db.commit()
        db.close()

        self.app = FastAPI()
        self.app.include_router(resume_analysis_router)

        def override_get_db():
            session = self.Session()
            try:
                yield session
            finally:
                session.close()

        self.current_user_id = self.USER_A["id"]

        def override_get_current_user():
            session = self.Session()
            try:
                return session.query(User).filter(User.id == self.current_user_id).first()
            finally:
                session.close()

        self.app.dependency_overrides[get_db] = override_get_db
        self.app.dependency_overrides[get_current_user] = override_get_current_user
        self.client = TestClient(self.app)

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_analysis_persisted_and_retrievable(self):
        resp = self.client.post("/jobs/job_1/resume-analysis", json={"resume_id": "res_a"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["job_id"], "job_1")
        self.assertEqual(body["resume_id"], "res_a")
        self.assertIn("Python", body["matched_skills"])
        self.assertNotIn("Python", body["missing_skills"])

        # Retrieval by GET works and matches.
        got = self.client.get("/jobs/job_1/resume-analysis/res_a")
        self.assertEqual(got.status_code, 200)
        self.assertEqual(got.json()["overall_score"], body["overall_score"])

    def test_cannot_analyze_another_users_resume(self):
        resp = self.client.post("/jobs/job_1/resume-analysis", json={"resume_id": "res_b"})
        self.assertEqual(resp.status_code, 404)

    def test_analyzing_own_resume_then_other_user_is_isolated(self):
        self.client.post("/jobs/job_1/resume-analysis", json={"resume_id": "res_a"})
        self.current_user_id = self.USER_B["id"]
        got = self.client.get("/jobs/job_1/resume-analysis/res_a")
        self.assertEqual(got.status_code, 404)

    def test_nonexistent_resume_404(self):
        resp = self.client.post("/jobs/job_1/resume-analysis", json={"resume_id": "nope"})
        self.assertEqual(resp.status_code, 404)

    def test_nonexistent_job_404(self):
        resp = self.client.post("/jobs/nope/resume-analysis", json={"resume_id": "res_a"})
        self.assertEqual(resp.status_code, 404)


class TestParsingStateHandling(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "state.db")
        self.engine = create_engine(
            f"sqlite:///{self.db_path}", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        db = self.Session()
        self.user = User(id="user", firebase_uid="fb", email="u@t.com", name="U")
        db.add(self.user)
        self.job = Job(id="job", user_id="user", title="Backend", company="C",
                       description="Python", required_skills="Python")
        db.add(self.job)
        db.commit()
        db.close()

        self.app = FastAPI()
        self.app.include_router(resume_analysis_router)

        def override_get_db():
            session = self.Session()
            try:
                yield session
            finally:
                session.close()

        def override_get_current_user():
            session = self.Session()
            try:
                return session.query(User).filter(User.id == "user").first()
            finally:
                session.close()

        self.app.dependency_overrides[get_db] = override_get_db
        self.app.dependency_overrides[get_current_user] = override_get_current_user
        self.client = TestClient(self.app)

    def _make_resume(self, rid, status, parsed_data=None, error=None, text=None):
        db = self.Session()
        r = Resume(
            id=rid, user_id="user", filename=f"{rid}.pdf", original_filename=f"{rid}.pdf",
            file_path="/tmp/x.pdf", file_size="1", parsing_status=status,
            parsed_data=parsed_data, parsing_error=error, extracted_text=text,
        )
        db.add(r)
        db.commit()
        db.close()

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_pending_resume_409(self):
        self._make_resume("r_pending", "pending")
        resp = self.client.post("/jobs/job/resume-analysis", json={"resume_id": "r_pending"})
        self.assertEqual(resp.status_code, 409)

    def test_failed_resume_422(self):
        self._make_resume("r_failed", "failed", error="parse error")
        resp = self.client.post("/jobs/job/resume-analysis", json={"resume_id": "r_failed"})
        self.assertEqual(resp.status_code, 422)

    def test_empty_resume_422(self):
        self._make_resume("r_empty", "completed", parsed_data={})
        resp = self.client.post("/jobs/job/resume-analysis", json={"resume_id": "r_empty"})
        self.assertEqual(resp.status_code, 422)
        self.assertIn("No usable resume data", resp.json()["detail"])

    def test_valid_resume_succeeds(self):
        self._make_resume("r_ok", "completed", parsed_data={"skills": ["Python"]})
        resp = self.client.post("/jobs/job/resume-analysis", json={"resume_id": "r_ok"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Python", resp.json()["matched_skills"])


if __name__ == "__main__":
    unittest.main()
