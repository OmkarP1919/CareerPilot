"""Phase 5B discovery normalization & filtering tests.

Covers:
A. SearchCriteria field survival / new additive fields.
B. Normalization of every dimension (title, company, location, city, country,
   work mode (remote/hybrid/onsite), employment type, internship, experience,
   salary/currency, skills, category, posted_at/updated_at/fetched_at).
C. Missing / malformed data handling.
D. Filtering (location, work mode, employment type, internship, experience,
   posted_after, salary min/max, category, skills ANY/ALL).
E. Missing-data semantics (unknown values must not pass explicit filters).
F. Sorting (newest, oldest, salary, deterministic ties, missing values).
G. Radius is NOT implemented (no coordinates) - verify no false claims.
H. Provider regression - providers feed the common pipeline cleanly.
I. Orchestrator - full SearchCriteria reaches provider; pipeline runs after
   provider results; one bad job does not destroy unrelated results.
"""
import unittest
from datetime import datetime, timezone

from app.services.job_sources.base import (
    NormalizedJob,
    ProviderCapabilities,
    SearchCriteria,
    SourceResult,
    SourceStatus,
    SourceUnavailableError,
)
from app.services.job_sources.orchestrator import DiscoveryOrchestrator
from app.services.job_sources.pipeline import (
    CATEGORY_ALIASES,
    EMPLOYMENT_TYPES,
    EXPERIENCE_LEVELS,
    WORK_MODES,
    apply_filters,
    apply_sort,
    classify_internship,
    derive_country_code,
    normalize_category,
    normalize_company,
    normalize_employment_type,
    normalize_experience_level,
    normalize_job,
    normalize_jobs,
    normalize_skills,
    normalize_salary,
    normalize_title,
    normalize_work_mode,
    parse_iso_datetime,
    run_pipeline,
)


def make_job(external_id, title="Backend Developer", company="Acme Corp",
             location=None, **kw):
    base = dict(
        external_id=external_id,
        title=title,
        company=company,
        location=location,
    )
    base.update(kw)
    return NormalizedJob(**base)


def pc(**kw):
    p = ProviderCapabilities()
    for k, v in kw.items():
        setattr(p, k, v)
    return p


class TestSearchCriteria(unittest.TestCase):
    """A. SearchCriteria contract fields survive and new fields are additive."""

    def test_new_fields_default_safely(self):
        c = SearchCriteria(queries=["Python"])
        self.assertEqual(c.skills_match, "any")
        self.assertIsNone(c.internship_only)
        self.assertIsNone(c.posted_after)
        self.assertIsNone(c.radius)

    def test_all_fields_survive_roundtrip(self):
        c = SearchCriteria(
            queries=["Python Developer"],
            locations=["Pune"],
            country="in",
            radius="20km",
            remote=True,
            employment_type="full-time",
            experience_level="senior",
            internship_only=True,
            posted_after="2024-01-01T00:00:00+00:00",
            salary_min=500000,
            salary_max=900000,
            page=2,
            page_size=25,
            sort="newest",
            categories=["software-engineering"],
            skills=["python", "fastapi"],
            skills_match="all",
        )
        self.assertEqual(c.skills_match, "all")
        self.assertIs(c.internship_only, True)
        self.assertEqual(c.country, "in")
        self.assertEqual(c.categories, ["software-engineering"])
        self.assertEqual(c.skills, ["python", "fastapi"])


class TestNormalization(unittest.TestCase):
    """B. Normalization of every dimension."""

    def test_title_whitespace(self):
        self.assertEqual(normalize_title("  Software Engineer   "), "Software Engineer")
        self.assertEqual(normalize_title("Senior   Python Developer"), "Senior Python Developer")
        self.assertEqual(normalize_title(None), "")

    def test_company_whitespace(self):
        self.assertEqual(normalize_company("  Acme   Corp  "), "Acme Corp")
        self.assertEqual(normalize_company(None), "")

    def test_location_city_country(self):
        j = make_job("1", location="Pune, Maharashtra, India")
        normalize_job(j)
        self.assertEqual(j.city, "Pune")
        self.assertEqual(j.country, "in")

    def test_location_no_city_for_remote(self):
        j = make_job("1", location="Remote")
        normalize_job(j)
        self.assertIsNone(j.city)
        self.assertIsNone(j.country)

    def test_derive_country_deterministic(self):
        self.assertEqual(derive_country_code(["Pune"]), "in")
        self.assertEqual(derive_country_code(["London, UK"]), "gb")
        self.assertEqual(derive_country_code(["New York, NY, USA"]), "us")
        self.assertIsNone(derive_country_code(["Remote"]))
        self.assertIsNone(derive_country_code([None]))

    def test_country_structured_field_kept(self):
        j = make_job("1", location="Somewhere", country="de")
        normalize_job(j)
        self.assertEqual(j.country, "de")

    def test_work_mode_remote(self):
        for loc in ["Remote", "Work from home", "WFH", "Fully remote"]:
            j = make_job("1", location=loc, description="")
            normalize_work_mode(j)
            self.assertEqual(j.work_mode, "remote", loc)

    def test_work_mode_hybrid(self):
        for loc in ["Hybrid", "Hybrid - Remote", "Partially remote"]:
            j = make_job("1", location=loc, description="")
            normalize_work_mode(j)
            self.assertEqual(j.work_mode, "hybrid", loc)

    def test_work_mode_onsite(self):
        for loc in ["On-site", "In office", "Onsite"]:
            j = make_job("1", location=loc, description="")
            normalize_work_mode(j)
            self.assertEqual(j.work_mode, "onsite", loc)

    def test_work_mode_unspecified_when_unclear(self):
        j = make_job("1", location="Pune, India")
        normalize_work_mode(j)
        self.assertEqual(j.work_mode, "unspecified")

    def test_work_mode_respects_source_remote_flag(self):
        j = make_job("1", location="Pune, India", remote=True)
        normalize_work_mode(j)
        self.assertEqual(j.work_mode, "remote")

        j2 = make_job("1", location="Pune, India", remote=False)
        normalize_work_mode(j2)
        self.assertEqual(j2.work_mode, "onsite")

    def test_employment_type_canonicalized(self):
        for raw, expected in [
            ("Full Time", "full-time"),
            ("FULL-TIME", "full-time"),
            ("fulltime", "full-time"),
            ("Permanent", "full-time"),
            ("Part-time", "part-time"),
            ("Contract", "contract"),
            ("Internship", "internship"),
            ("Freelance", "freelance"),
            (None, "unspecified"),
            ("Weird Type", "unspecified"),
        ]:
            j = make_job("1", employment_type=raw)
            normalize_employment_type(j)
            self.assertEqual(j.employment_type, expected, raw)

    def test_employment_types_vocabulary(self):
        self.assertTrue({"full-time", "part-time", "contract", "internship",
                         "temporary", "freelance", "volunteer", "other",
                         "unspecified"} <= EMPLOYMENT_TYPES)

    def test_internship_classification(self):
        self.assertTrue(classify_internship(make_job("1", employment_type="internship")))
        self.assertTrue(classify_internship(make_job("1", title="Summer Intern Java", company="X")))
        self.assertTrue(classify_internship(
            make_job("1", title="React Trainee", company="X")))
        # A job that merely mentions internships in the description is NOT an
        # internship role.
        self.assertFalse(classify_internship(make_job(
            "1", title="Backend Developer", company="X",
            description="Mentor interns and lead the team.")))

    def test_experience_level_normalized(self):
        for raw, expected in [
            ("Junior", "junior"),
            ("Sr", "senior"),
            ("Senior", "senior"),
            ("Entry Level", "entry"),
            ("Mid-level", "mid"),
            ("Lead", "lead"),
            ("Intern", "internship"),
            ("Unknown", "unspecified"),
            (None, "unspecified"),
            ("2-4 years", "unspecified"),
        ]:
            j = make_job("1", experience_level=raw)
            normalize_experience_level(j)
            self.assertEqual(j.experience_level, expected, raw)

    def test_experience_vocabulary(self):
        self.assertTrue({"internship", "entry", "junior", "mid", "senior", "lead",
                         "manager", "director", "executive", "unspecified"} <= EXPERIENCE_LEVELS)

    def test_salary_coerced_and_invalid_cleared(self):
        j = make_job("1", salary_min="100000", salary_max="200000")
        normalize_salary(j)
        self.assertEqual(j.salary_min, 100000)
        self.assertEqual(j.salary_max, 200000)

        j2 = make_job("1", salary_min="abc", salary_max=-5)
        normalize_salary(j2)
        self.assertIsNone(j2.salary_min)
        self.assertIsNone(j2.salary_max)

    def test_salary_never_mixes_pay_periods(self):
        # normalize_salary only validates/coerces numeric fields; it never
        # converts a monthly figure to annual. Verify it leaves existing
        # numeric values statistically untouched.
        j = make_job("1", salary_min=50000, salary_max=50000, salary_currency="INR")
        normalize_salary(j)
        self.assertEqual(j.salary_min, 50000)
        self.assertEqual(j.salary_max, 50000)
        self.assertEqual(j.salary_currency, "INR")

    def test_skills_normalized_deterministic(self):
        self.assertEqual(
            normalize_skills(["Python", "python", "PYTHON", " FastAPI ", "", "fastapi"]),
            ["Python", "FastAPI"],
        )

    def test_category_normalized_conservatively(self):
        j = make_job("1", category="Software Development")
        normalize_category(j)
        self.assertEqual(j.category, "software-engineering")

        j2 = make_job("1", category="Some Unmapped Sector")
        normalize_category(j2)
        self.assertEqual(j2.category, "some unmapped sector")

        j3 = make_job("1", category=None)
        normalize_category(j3)
        self.assertIsNone(j3.category)

    def test_category_aliases_not_empty(self):
        self.assertIn("software development", CATEGORY_ALIASES)

    def test_dates_parsed(self):
        dt = parse_iso_datetime("2024-01-15T10:00:00Z")
        self.assertIsNotNone(dt)
        self.assertIsNotNone(dt.tzinfo)

    def test_invalid_dates_nullified(self):
        j = make_job("1", posted_at="not-a-date", updated_at="also-bad")
        normalize_job(j)
        self.assertIsNone(j.posted_at)
        self.assertIsNone(j.updated_at)

    def test_work_mode_attribute_is_additive(self):
        # NormalizedJob.work_mode is additive and defaults to None (absent),
        # preserving the legacy `remote` bool.
        j = NormalizedJob(external_id="1", title="T", company="C", remote=True)
        self.assertTrue(j.remote)
        self.assertIsNone(j.work_mode)


class TestMissingAndMalformed(unittest.TestCase):
    """C. Missing / malformed data is handled without crashing."""

    def test_missing_fields_tolerated(self):
        jobs = normalize_jobs([
            make_job("1"),
            NormalizedJob(external_id="2", title="", company=""),
            "not-a-job-object",  # malformed entry is skipped defensively
        ])
        self.assertEqual(len(jobs), 2)

    def test_malformed_salary_and_dates(self):
        j = make_job("1", salary_min="NaN", salary_max=10, posted_at="junk",
                     employment_type=123, experience_level=456)
        normalize_job(j)
        self.assertIsNone(j.salary_min)
        self.assertIsNone(j.posted_at)


class TestFiltering(unittest.TestCase):
    """D. Filtering engine with documented missing-data semantics."""

    def test_location_match(self):
        jobs = [
            make_job("1", location="Pune, Maharashtra, India"),
            make_job("2", location="Mumbai, Maharashtra, India"),
        ]
        c = SearchCriteria(queries=["x"], locations=["Pune"])
        kept = apply_filters(jobs, c)
        self.assertEqual([j.external_id for j in kept], ["1"])

    def test_location_mismatch_not_matched_by_region(self):
        # Search Pune must NOT match Mumbai merely because both are in
        # Maharashtra.
        jobs = [make_job("1", location="Mumbai, Maharashtra, India")]
        c = SearchCriteria(queries=["x"], locations=["Pune"])
        self.assertEqual(apply_filters(jobs, c), [])

    def test_missing_location_fails_explicit_location_filter(self):
        jobs = [make_job("1", location=None)]
        c = SearchCriteria(queries=["x"], locations=["Pune"])
        self.assertEqual(apply_filters(jobs, c), [])

    def test_remote_filter(self):
        jobs = [
            make_job("1", location="Remote"),
            make_job("2", location="Hybrid"),
            make_job("3", location="On-site"),
            make_job("4", location="Pune, India"),
        ]
        normalized = normalize_jobs(jobs)
        c_remote = SearchCriteria(queries=["x"], remote=True)
        # remote=True keeps remote + hybrid (both allow remote work)
        self.assertEqual(
            sorted(j.external_id for j in apply_filters(normalized, c_remote)),
            ["1", "2"],
        )
        c_onsite = SearchCriteria(queries=["x"], remote=False)
        self.assertEqual(
            sorted(j.external_id for j in apply_filters(normalized, c_onsite)),
            ["2", "3"],
        )

    def test_employment_type_filter(self):
        jobs = normalize_jobs([
            make_job("1", employment_type="Full Time"),
            make_job("2", employment_type="Contract"),
        ])
        c = SearchCriteria(queries=["x"], employment_type="full-time")
        self.assertEqual([j.external_id for j in apply_filters(jobs, c)], ["1"])

    def test_unspecified_employment_type_fails_explicit_filter(self):
        jobs = normalize_jobs([make_job("1", employment_type="Weird")])
        c = SearchCriteria(queries=["x"], employment_type="full-time")
        self.assertEqual(apply_filters(jobs, c), [])

    def test_internship_filter(self):
        jobs = [
            make_job("1", title="Software Engineer", company="X"),
            make_job("2", title="Summer Intern", company="X"),
        ]
        c_keep = SearchCriteria(queries=["x"], internship_only=True)
        self.assertEqual([j.external_id for j in apply_filters(jobs, c_keep)], ["2"])
        c_exclude = SearchCriteria(queries=["x"], internship_only=False)
        self.assertEqual([j.external_id for j in apply_filters(jobs, c_exclude)], ["1"])

    def test_experience_filter(self):
        jobs = normalize_jobs([
            make_job("1", experience_level="Senior"),
            make_job("2", experience_level="Junior"),
        ])
        c = SearchCriteria(queries=["x"], experience_level="senior")
        self.assertEqual([j.external_id for j in apply_filters(jobs, c)], ["1"])

    def test_posted_after_filter(self):
        jobs = normalize_jobs([
            make_job("1", posted_at="2023-01-01T00:00:00Z"),
            make_job("2", posted_at="2024-06-01T00:00:00Z"),
            make_job("3", posted_at=None),
        ])
        c = SearchCriteria(queries=["x"], posted_after="2024-01-01T00:00:00Z")
        kept = apply_filters(jobs, c)
        self.assertEqual([j.external_id for j in kept], ["2"])

    def test_salary_min_filter(self):
        jobs = [
            make_job("1", salary_min=100, salary_max=200),
            make_job("2", salary_min=300, salary_max=400),
        ]
        c = SearchCriteria(queries=["x"], salary_min=250)
        self.assertEqual([j.external_id for j in apply_filters(jobs, c)], ["2"])

    def test_salary_max_filter(self):
        jobs = [
            make_job("1", salary_min=100, salary_max=200),
            make_job("2", salary_min=300, salary_max=400),
        ]
        c = SearchCriteria(queries=["x"], salary_max=250)
        self.assertEqual([j.external_id for j in apply_filters(jobs, c)], ["1"])

    def test_missing_salary_fails_explicit_salary_filter(self):
        jobs = [make_job("1", salary_min=None, salary_max=None)]
        c = SearchCriteria(queries=["x"], salary_min=100)
        self.assertEqual(apply_filters(jobs, c), [])

    def test_category_filter(self):
        jobs = normalize_jobs([
            make_job("1", category="Software Development"),
            make_job("2", category="Marketing"),
        ])
        c = SearchCriteria(queries=["x"], categories=["software-engineering"])
        self.assertEqual([j.external_id for j in apply_filters(jobs, c)], ["1"])

    def test_skills_any(self):
        jobs = [
            make_job("1", skills=["Python"]),
            make_job("2", skills=["Java"]),
            make_job("3", skills=["Python", "Java"]),
        ]
        c = SearchCriteria(queries=["x"], skills=["python", "java"])
        kept = apply_filters(jobs, c)
        self.assertEqual({j.external_id for j in kept}, {"1", "2", "3"})

    def test_skills_all(self):
        jobs = [
            make_job("1", skills=["Python"]),
            make_job("2", skills=["Python", "FastAPI"]),
            make_job("3", skills=["Java"]),
        ]
        c = SearchCriteria(queries=["x"], skills=["python", "fastapi"], skills_match="all")
        self.assertEqual([j.external_id for j in apply_filters(jobs, c)], ["2"])

    def test_skills_missing_fails_explicit_filter(self):
        jobs = [make_job("1", skills=None)]
        c = SearchCriteria(queries=["x"], skills=["python"])
        self.assertEqual(apply_filters(jobs, c), [])


class TestMissingDataSemantics(unittest.TestCase):
    """E. Dedicated tests for unknown-value semantics."""

    def test_all_filters_reject_unknown(self):
        cases = [
            ("location", SearchCriteria(queries=["x"], locations=["Pune"]),
             make_job("1", location=None)),
            ("remote", SearchCriteria(queries=["x"], remote=True),
             make_job("1", location="Pune, India")),
            ("employment", SearchCriteria(queries=["x"], employment_type="full-time"),
             make_job("1", employment_type=None)),
            ("experience", SearchCriteria(queries=["x"], experience_level="senior"),
             make_job("1", experience_level=None)),
            ("posted_after", SearchCriteria(queries=["x"], posted_after="2024-01-01"),
             make_job("1", posted_at=None)),
            ("salary", SearchCriteria(queries=["x"], salary_min=100),
             make_job("1", salary_min=None, salary_max=None)),
        ]
        for name, c, job in cases:
            with self.subTest(name=name):
                # Unknown value must NOT satisfy an explicit constraint.
                self.assertEqual(apply_filters([job], c), [], name)


class TestSorting(unittest.TestCase):
    """F. Deterministic sorting, ties, and missing values."""

    def test_newest(self):
        jobs = [
            make_job("a", posted_at="2023-01-01T00:00:00Z"),
            make_job("b", posted_at="2024-06-01T00:00:00Z"),
            make_job("c", posted_at="2022-01-01T00:00:00Z"),
            make_job("d", posted_at=None),
        ]
        out = apply_sort(jobs, "newest")
        self.assertEqual([j.external_id for j in out], ["b", "a", "c", "d"])

    def test_oldest(self):
        jobs = [
            make_job("a", posted_at="2023-01-01T00:00:00Z"),
            make_job("b", posted_at="2022-06-01T00:00:00Z"),
            make_job("c", posted_at=None),
        ]
        out = apply_sort(jobs, "oldest")
        self.assertEqual([j.external_id for j in out], ["b", "a", "c"])

    def test_salary_desc(self):
        jobs = [
            make_job("low", salary_min=10, salary_max=20, salary_currency="USD"),
            make_job("high", salary_min=90, salary_max=100, salary_currency="USD"),
            make_job("unknown", salary_min=None, salary_max=None),
        ]
        out = apply_sort(jobs, "salary")
        self.assertEqual([j.external_id for j in out], ["high", "low", "unknown"])

    def test_relevance_keeps_order(self):
        jobs = [make_job("1"), make_job("2"), make_job("3")]
        out = apply_sort(jobs, "relevance")
        self.assertEqual([j.external_id for j in out], ["1", "2", "3"])

    def test_deterministic_tie_break(self):
        jobs = [
            make_job("x2", posted_at="2024-01-01T00:00:00Z", company="B"),
            make_job("x1", posted_at="2024-01-01T00:00:00Z", company="A"),
        ]
        out1 = apply_sort(jobs, "newest")
        out2 = apply_sort(jobs, "newest")
        self.assertEqual([j.external_id for j in out1], [j.external_id for j in out2])

    def test_unknown_sort_uses_relevance(self):
        jobs = [make_job("1"), make_job("2")]
        self.assertEqual([j.external_id for j in apply_sort(jobs, "bogus")], ["1", "2"])


class TestRadiusNotImplemented(unittest.TestCase):
    """G. Radius must NOT be falsely implemented without coordinates."""

    def test_radius_is_noop_and_documented(self):
        jobs = [make_job("1", location="Pune, India"), make_job("2", location="Mumbai, India")]
        # criteria.radius exists but there are no coordinates; filtering must
        # not pretend to compute distance.
        c = SearchCriteria(queries=["x"], locations=["Pune"], radius="20km")
        # Location still matches normally; radius does not alter results.
        kept = apply_filters(jobs, c)
        self.assertEqual([j.external_id for j in kept], ["1"])
        # The pipeline's filters_applied never claims radius.
        out = run_pipeline(jobs, c)
        self.assertNotIn("radius", out["filters_applied"])


class TestPipelineAndOrchestrator(unittest.TestCase):
    """H & I. Full pipeline + orchestrator wiring."""

    def test_pipeline_normalize_filter_sort_paginate(self):
        jobs = [
            make_job("1", title="  Senior Python Dev ", location="Pune, India",
                     employment_type="Full Time", posted_at="2024-01-01T00:00:00Z"),
            make_job("2", title="Junior Java Dev", location="Mumbai, India",
                     employment_type="Contract"),
        ]
        out = run_pipeline(
            jobs,
            SearchCriteria(queries=["x"], locations=["Pune"], employment_type="full-time"),
            sort="newest",
            page=1,
            page_size=5,
        )
        self.assertEqual([j.external_id for j in out["jobs"]], ["1"])
        self.assertEqual(out["total"], 1)
        self.assertIn("location", out["filters_applied"])
        self.assertIn("employment_type", out["filters_applied"])
        self.assertEqual(out["jobs"][0].title, "Senior Python Dev")

    def test_pipeline_pagination_over_global_result(self):
        jobs = [
            make_job(f"j{i}", title=f"Job {i}", company="C",
                     posted_at=f"2024-0{(i%9)+1}-0{(i%7)+1}-01T00:00:00Z")
            for i in range(10)
        ]
        out = run_pipeline(jobs, SearchCriteria(queries=["x"]), sort="newest",
                           page=1, page_size=3)
        self.assertEqual(len(out["jobs"]), 3)
        self.assertEqual(out["total"], 10)
        # Page 2 continues the same global ordering.
        out2 = run_pipeline(jobs, SearchCriteria(queries=["x"]), sort="newest",
                            page=2, page_size=3)
        first_page_ids = {j.external_id for j in out["jobs"]}
        second_page_ids = {j.external_id for j in out2["jobs"]}
        self.assertTrue(first_page_ids.isdisjoint(second_page_ids))

    def test_orchestrator_search_filtered_applies_pipeline(self):
        from app.services.job_sources.pipeline import normalize_jobs

        class Prov:
            name = "P"

            def __init__(self, result):
                self.result = result

            @property
            def is_enabled(self):
                return True

            def fetch(self, criteria):
                return self.result

        jobs = [
            make_job("1", title="  Python Dev  ", location="Pune, India", employment_type="Full Time"),
            make_job("2", title="Java Dev", location="Mumbai, India", employment_type="Contract"),
        ]
        orch = DiscoveryOrchestrator([Prov(jobs)])
        criteria = SearchCriteria(queries=["Python"], locations=["Pune"])
        out = orch.search_filtered(criteria)
        self.assertEqual(len(out["raw_jobs"]), 2)
        self.assertEqual([j.external_id for j in out["jobs"]], ["1"])
        self.assertIn("location", out["filters_applied"])

    def test_search_remains_unchanged(self):
        # The existing search() must NOT apply pipeline filtering (backward
        # compat for personalized discovery persistence).
        class Prov:
            name = "P"

            @property
            def is_enabled(self):
                return True

            def fetch(self, criteria):
                return [make_job("1", title="  Python Dev  ", location="Pune")]

        out = DiscoveryOrchestrator([Prov()]).search(
            SearchCriteria(queries=["Python"], locations=["Mumbai"])
        )
        # Raw search returns all raw jobs regardless of location.
        self.assertEqual(len(out["jobs"]), 1)

    def test_one_bad_job_does_not_destroy_others(self):
        jobs = [
            make_job("1", title="Good Job", location="Pune"),
            NormalizedJob(external_id="bad", title=None, company=None,
                          employment_type=999, posted_at={"nested": "bad"}),
        ]
        normalized = normalize_jobs(jobs)
        # Both jobs are retained and coerce defensively; the malformed one does
        # not crash or destroy the good one.
        self.assertEqual(len(normalized), 2)
        self.assertEqual(normalized[0].external_id, "1")
        self.assertIsNone(normalized[1].posted_at)


class TestSalaryPeriodAndCurrency(unittest.TestCase):
    """5B.1: salaries are never converted and only compared when compatible."""

    def test_salary_period_normalized_to_canonical(self):
        j = make_job("1", salary_min=5000, salary_max=6000, salary_period=None)
        normalize_salary(j)
        self.assertEqual(j.salary_period, "unknown")

        j2 = make_job("2", salary_min=50000, salary_max=60000, salary_period="per month")
        normalize_salary(j2)
        self.assertEqual(j2.salary_period, "unknown")  # not in canonical vocab

        j3 = make_job("3", salary_min=50000, salary_max=60000, salary_period="monthly")
        normalize_salary(j3)
        self.assertEqual(j3.salary_period, "monthly")

    def test_request_period_known_requires_same_job_period(self):
        jobs = [
            make_job("annual", salary_min=60000, salary_max=70000, salary_period="annual"),
            make_job("monthly", salary_min=5000, salary_max=6000, salary_period="monthly"),
            make_job("unknown", salary_min=5000, salary_max=6000, salary_period=None),
        ]
        # Request pins an annual figure -> only the annual job is comparable;
        # the monthly figure (different period) and the unknown are refused,
        # never converted.
        c = SearchCriteria(queries=["x"], salary_min=55000, salary_period="annual")
        self.assertEqual([j.external_id for j in apply_filters(jobs, c)], ["annual"])

    def test_request_period_matches_job_period(self):
        jobs = [
            make_job("a", salary_min=4000, salary_max=5000, salary_period="monthly"),
            make_job("b", salary_min=6000, salary_max=7000, salary_period="monthly"),
        ]
        c = SearchCriteria(queries=["x"], salary_min=5500, salary_period="monthly")
        self.assertEqual([j.external_id for j in apply_filters(jobs, c)], ["b"])

    def test_incompatible_periods_not_numerically_compared(self):
        # A monthly salary of 5000 must NOT be compared against an annual min
        # of 10000 as if it were annual; the job is simply not comparable.
        jobs = [make_job("m", salary_min=5000, salary_max=5000, salary_period="monthly")]
        c = SearchCriteria(queries=["x"], salary_min=10000, salary_period="annual")
        self.assertEqual(apply_filters(jobs, c), [])

    def test_unknown_job_period_fails_known_request_period(self):
        jobs = [make_job("u", salary_min=5000, salary_max=5000, salary_period=None)]
        c = SearchCriteria(queries=["x"], salary_min=1000, salary_period="monthly")
        self.assertEqual(apply_filters(jobs, c), [])

    def test_currency_gate_only_when_request_pins_currency(self):
        jobs = [
            make_job("usd", salary_min=50000, salary_max=60000, salary_currency="USD"),
            make_job("inr", salary_min=50000, salary_max=60000, salary_currency="INR"),
        ]
        c_inr = SearchCriteria(queries=["x"], salary_min=40000, salary_currency="INR")
        self.assertEqual([j.external_id for j in apply_filters(jobs, c_inr)], ["inr"])

    def test_no_currency_request_uses_legacy_numeric_compare(self):
        # When the request pins no currency, the legacy numeric fallback
        # applies (nothing to gate against) -> the JPY job passes on amount.
        jobs = [make_job("jpy", salary_min=50000, salary_max=60000, salary_currency="JPY")]
        c = SearchCriteria(queries=["x"], salary_min=40000)
        self.assertEqual([j.external_id for j in apply_filters(jobs, c)], ["jpy"])

    def test_min_only_salary_filter(self):
        # A job exposing only salary_min is compared by that lower bound.
        jobs = [make_job("min-only", salary_min=50000, salary_max=None, salary_period="annual")]
        c = SearchCriteria(queries=["x"], salary_min=40000, salary_period="annual")
        self.assertEqual([j.external_id for j in apply_filters(jobs, c)], ["min-only"])
        c_excl = SearchCriteria(queries=["x"], salary_min=60000, salary_period="annual")
        self.assertEqual(apply_filters(jobs, c_excl), [])

    def test_min_only_salary_sort_not_missing(self):
        # min-only is NOT "missing": it sorts by salary_min.
        jobs = [
            make_job("m1", salary_min=50000, salary_max=None, salary_period="annual"),
            make_job("m2", salary_min=90000, salary_max=None, salary_period="annual"),
            make_job("none", salary_min=None, salary_max=None, salary_period="annual"),
        ]
        out = apply_sort(jobs, "salary")
        self.assertEqual([j.external_id for j in out], ["m2", "m1", "none"])

    def test_mixed_period_salary_sort_groups_by_period(self):
        # Annual jobs sort before monthly (deterministic grouping), each
        # descending within its period; missing remains last.
        jobs = [
            make_job("monthly-low", salary_min=1000, salary_max=2000, salary_period="monthly"),
            make_job("annual-high", salary_min=80000, salary_max=90000, salary_period="annual"),
            make_job("annual-low", salary_min=60000, salary_max=70000, salary_period="annual"),
            make_job("none", salary_min=None, salary_max=None, salary_period=None),
        ]
        out = apply_sort(jobs, "salary")
        self.assertEqual([j.external_id for j in out],
                         ["annual-high", "annual-low", "monthly-low", "none"])


class TestWorkModeContradiction(unittest.TestCase):
    """5B.1: work-mode classification hardening."""

    def test_remote_flag_with_contradictory_onsite_location_is_unspecified(self):
        # Source flags `remote` but location text strongly says onsite: a
        # contradiction -> unspecified, not blindly remote.
        j = make_job("1", location="Bangalore - Onsite", remote=True)
        normalize_work_mode(j)
        self.assertEqual(j.work_mode, "unspecified")

    def test_remote_flag_confirmed_by_text_is_remote(self):
        j = make_job("1", location="Pune, India", description="This is a fully remote role.", remote=True)
        normalize_work_mode(j)
        self.assertEqual(j.work_mode, "remote")

    def test_onsite_flag_with_remote_location_is_unspecified(self):
        j = make_job("1", location="Remote", remote=False)
        normalize_work_mode(j)
        self.assertEqual(j.work_mode, "unspecified")

    def test_description_office_does_not_force_onsite(self):
        # Bare 'office' inside a body of text is weak evidence and must not
        # misclassify a field role as onsite.
        j = make_job("1", location="Bengaluru, India",
                     description="Field engineer. Reports to the office quarterly for reviews.")
        normalize_work_mode(j)
        self.assertEqual(j.work_mode, "unspecified")

    def test_description_remote_is_remote(self):
        j = make_job("1", location="Bengaluru, India", description="Work from home full time.", remote=None)
        normalize_work_mode(j)
        self.assertEqual(j.work_mode, "remote")


class TestCategoryAndSkillHardening(unittest.TestCase):
    """5B.1: category alias and single-char skill matching hardening."""

    def test_bare_engineering_not_mapped_to_software(self):
        # Bare 'engineering' is too broad to claim software engineering.
        self.assertNotIn("engineering", CATEGORY_ALIASES)
        self.assertIn("software engineering", CATEGORY_ALIASES)
        j = make_job("1", category="Engineering")
        normalize_category(j)
        self.assertEqual(j.category, "engineering")  # preserved, not remapped

    def test_software_engineering_mapped(self):
        j = make_job("1", category="Software Engineering")
        normalize_category(j)
        self.assertEqual(j.category, "software-engineering")

    def test_single_char_skill_only_matches_structured(self):
        # 'c' as a skill must NOT false-positive on free text (the 'c' in
        # "acquisitions"); it only matches authoritative structured skills.
        jobs = [
            make_job("1", title="Accountant", description="Handles acquisitions and ledgers."),
            make_job("2", title="C Developer", skills=["C"]),
        ]
        c = SearchCriteria(queries=["x"], skills=["c"])
        kept = [j.external_id for j in apply_filters(jobs, c)]
        self.assertNotIn("1", kept)
        self.assertIn("2", kept)

    def test_cpp_distinct_from_c(self):
        # C++ is a distinct skill and must not be matched by a request for 'c'.
        jobs = [make_job("1", title="C++ engineer", skills=["C++"])]
        c = SearchCriteria(queries=["x"], skills=["c"])
        self.assertEqual(apply_filters(jobs, c), [])
        cpp = SearchCriteria(queries=["x"], skills=["c++"])
        self.assertEqual([j.external_id for j in apply_filters(jobs, cpp)], ["1"])


if __name__ == "__main__":
    unittest.main()
