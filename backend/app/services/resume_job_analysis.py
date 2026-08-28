"""
Resume vs Job Analysis — RESUME MATCH (deterministic, no LLM).

This service compares an uploaded, successfully-parsed resume against a job
and produces a structured, explainable analysis. It is conceptually separate
from the CareerPilot profile-to-job matching engine (``matching.py``), which
produces the PROFILE MATCH score.

Scoring weights (total = 100%):
    - Required Skill Coverage    40%
    - Keyword Relevance           20%
    - Experience Relevance        20%
    - Project Relevance           15%
    - Education / Certification    5%

Fairness of unavailable factors
-------------------------------
A job source does not always provide complete structured information. To
avoid unfairly penalising a resume for information the job simply does not
offer, only *active* factors (those for which the job description / metadata
contains enough evidence) contribute to the overall score. The overall score
is the weighted average of the active factors' scores, normalised by the
sum of the active factors' weights. Unavailable factors neither lower nor
raise the score. If no factor is active at all, a neutral low overall score
with a clear user-facing note is returned.

Nothing in this module fabricates information. Years of experience are never
invented; project/experience relevance is based only on detected overlap.
"""

import re
from typing import Any, Dict, List, Optional

from app.services.resume_parser import match_skill

# =============================================================================
# Weights (documented, total 100%)
# =============================================================================
WEIGHTS = {
    "skills": 0.40,
    "keywords": 0.20,
    "experience": 0.20,
    "projects": 0.15,
    "education": 0.05,
}

# =============================================================================
# Keyword extraction
# =============================================================================
# Curated role / methodology / platform / qualification concepts that are
# meaningful in job descriptions and worth reporting. Kept deliberately small
# and maintainable; the bulk of keyword extraction comes from the resume skill
# vocabulary.
_CONCEPT_KEYWORDS = [
    "backend", "frontend", "full stack", "fullstack", "devops", "cloud",
    "microservices", "micro service", "micro-service", "rest", "restful", "graphql",
    "agile", "scrum", "kanban", "ci/cd", "cicd", "automation", "container", "kubernetes",
    "serverless", "api", "database", "architecture", "scalable", "distributed",
    "machine learning", "deep learning", "data pipeline", "data engineering",
    "etl", "analytics", "monitoring", "observability", "security", "testing",
    "unit testing", "integration testing", "leadership", "mentoring",
    "collaboration", "remote", "relational", "nosql", "streaming",
]

_STOP_WORDS = {
    "the", "and", "for", "with", "you", "will", "our", "able", "are", "your",
    "this", "that", "have", "from", "they", "has", "all", "any", "who", "what",
    "when", "where", "which", "their", "there", "about", "into", "over", "than",
    "then", "them", "these", "those", "also", "well", "though", "should", "would",
    "could", "may", "might", "must", "need", "needs", "required", "requirements",
    "experience", "years", "year", "work", "role", "job", "position", "team",
    "company", "plus", "good", "great", "strong", "using", "use", "used",
    "building", "build", "develop", "development", "developing", "working",
    "including", "includes", "preferred", "knowledge", "understanding",
    "familiarity", "ability", "written", "verbal", "communication", "skills",
    "join", "looking", "someone", "within", "across", "such", "various",
    "related", "areas", "relevant", "experience", "etc", "e", "g", "i", "a",
    "an", "of", "in", "on", "at", "to", "as", "by", "or", "is", "be", "it",
}

# Multi-word concepts matched on the whole text (word-boundary aware).
_CONCEPT_MULTI = sorted(
    [c for c in _CONCEPT_KEYWORDS if " " in c or "/" in c or "-" in c],
    key=len,
    reverse=True,
)
# Single-word concepts matched as tokens.
_CONCEPT_SINGLE = {c.lower() for c in _CONCEPT_KEYWORDS if " " not in c and "/" not in c and "-" not in c}

# Additional meaningful single-word signal terms (role/domain/methodology).
_SIGNAL_SINGLE = {
    "engineer", "developer", "analyst", "architect", "scientist", "designer",
    "manager", "infrastructure", "platform", "automation", "api", "service",
    "sql", "database", "relational", "nosql", "streaming", "pipeline",
    "monitoring", "observability", "security", "scalable", "distributed",
    "machine", "learning", "automation",
}


def _tokenize(text: str) -> List[str]:
    if not text:
        return []
    return [
        w.strip(".") for w in re.findall(r"[a-zA-Z0-9+#./-]+", text.lower())
        if len(w.strip(".")) >= 2
    ]


def extract_keywords(description: str) -> List[str]:
    """Deterministic, meaningful keyword extraction from a job description.

    Returns a deduplicated, ordered list of canonical keywords drawn from:
    - known skills present in the text (via the resume skill vocabulary)
    - curated role/methodology/platform concepts present in the text
    - a small set of curated signal words (domain/role terms)

    Generic filler words are deliberately excluded so the keyword score is not
    diluted by noise. This is deterministic term extraction, not AI semantics.
    """
    if not description:
        return []

    text = description.lower()
    found: List[str] = []
    seen = set()

    def add(keyword: str):
        norm = re.sub(r"\s+", " ", keyword.strip().lower()).strip(".")
        if not norm or norm in seen:
            return
        seen.add(norm)
        found.append(keyword.strip())

    # 1. Skills from the vocabulary that appear in the description.
    for skill in _skills_in_text(description):
        add(skill)

    # 2. Multi-word concepts.
    for concept in _CONCEPT_MULTI:
        if concept in text:
            add(concept)
            text = text.replace(concept, " ")

    # 3. Single-word concepts and curated signal words.
    tokens = _tokenize(text)
    for tok in tokens:
        if tok in _STOP_WORDS:
            continue
        if tok in _CONCEPT_SINGLE or tok in _SIGNAL_SINGLE:
            add(tok)

    # Move known skills to the front (most meaningful) while preserving order.
    skills = [k for k in found if match_skill(k)]
    others = [k for k in found if not match_skill(k)]
    return skills + others


_EDUCATION_REQUIREMENT_RE = re.compile(
    r"(?i)\b(?:degree|bachelor|master|phd|doctorate|mba|b\.?tech|m\.?tech|"
    r"b\.?sc|m\.?sc|bachelor's|master's|certification|certified|license|"
    r"qualification|graduate|postgraduate)\b"
)
_CERT_REQUIREMENT_RE = re.compile(
    r"(?i)\b(?:certification|certified|license|licensure|professional\s+"
    r"(?:certificate|certification))\b"
)


def _job_has_education_requirement(description: str) -> bool:
    return bool(description and _EDUCATION_REQUIREMENT_RE.search(description))


# =============================================================================
# Skill helpers
# =============================================================================
# Safe, maintainable skill aliases. Only unambiguous equivalences are included;
# genuinely different technologies are never treated as equivalent.
_SAFE_ALIASES = {
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "js": "JavaScript",
    "javascript": "JavaScript",
    "ts": "TypeScript",
    "typescript": "TypeScript",
    "node": "Node.js",
    "nodejs": "Node.js",
    "reactjs": "React",
    "react.js": "React",
    "mariadb": "MariaDB",
    "expressjs": "Express",
}


def _normalize_alias(skill: str) -> str:
    """Normalise a skill to a stable canonical form using the resume vocabulary
    plus a small safe-alias table."""
    canonical = match_skill(skill)
    if canonical:
        compact = re.sub(r"[^a-z0-9]", "", canonical.lower())
        return _SAFE_ALIASES.get(compact, canonical)
    compact = re.sub(r"[^a-z0-9]", "", skill.lower())
    return _SAFE_ALIASES.get(compact) or _SAFE_ALIASES.get(skill.strip().lower()) or skill


def _skills_in_text(text: str) -> List[str]:
    """Return the ordered set of canonical skills referenced in text.

    Scans single tokens and two-word n-grams so both 'FastAPI' and
    'Machine Learning' are detected, independent of section layout.
    """
    if not text:
        return []
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9+#.]*", text)
    found = []
    seen = set()

    def add(skill_token: str):
        canonical = match_skill(skill_token)
        if canonical and canonical.lower() not in seen:
            seen.add(canonical.lower())
            found.append(canonical)

    for i in range(len(tokens)):
        add(tokens[i])
        if i + 1 < len(tokens):
            add(f"{tokens[i]} {tokens[i + 1]}")
    return found


def _required_skills_from_job(job: Any) -> List[str]:
    """Best-effort required skills: use job.required_skills if present, else
    infer reliable skills from the description."""
    raw = getattr(job, "required_skills", None)
    if raw:
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        skills = []
        seen = set()
        for p in parts:
            canonical = _normalize_alias(p)
            if canonical and canonical.lower() not in seen:
                seen.add(canonical.lower())
                skills.append(canonical)
        if skills:
            return skills
    return _skills_in_text(getattr(job, "description", "") or "")


def _resume_has_skill(test: str, resume_skills: List[str], resume_text: str) -> bool:
    if not resume_skills and not resume_text:
        return False
    canonical = _normalize_alias(test)
    needle = canonical.lower() if canonical else test.lower()
    for s in resume_skills:
        resume_canonical = _normalize_alias(s)
        if resume_canonical and resume_canonical.lower() == needle:
            return True
        if s.lower() == needle:
            return True
    if resume_text and needle and needle in resume_text.lower():
        return True
    return False


# =============================================================================
# Skill analysis
# =============================================================================
def _analyze_skills(job: Any, resume: dict, resume_text: str) -> dict:
    required = _required_skills_from_job(job)
    resume_skills = [s for s in (resume.get("skills") or []) if s]

    matched = []
    missing = []
    for req in required:
        if _resume_has_skill(req, resume_skills, resume_text):
            matched.append(req)
        else:
            missing.append(req)

    # Additional relevant skills: resume skills that are real tech skills but
    # were not listed among the job's required skills.
    additional = []
    seen = set(m.lower() for m in matched)
    for s in resume_skills:
        canonical = _normalize_alias(s)
        if canonical and canonical.lower() not in seen and canonical not in missing:
            seen.add(canonical.lower())
            additional.append(canonical)

    return {
        "score": _coverage_score(len(matched), len(required)) if required else None,
        "available": bool(required),
        "matched_skills": matched,
        "missing_skills": missing,
        "additional_relevant_skills": additional,
    }


def _coverage_score(matched: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((matched / total) * 100, 1)


# =============================================================================
# Keyword analysis
# =============================================================================
def _resume_full_text(resume: dict, resume_text: str) -> str:
    parts = [resume_text or ""]
    for proj in resume.get("projects") or []:
        parts.append(proj.get("name") or "")
        parts.append(proj.get("description") or "")
        parts.extend(proj.get("technologies") or [])
    for exp in resume.get("experience") or []:
        parts.append(exp.get("job_title") or "")
        parts.append(exp.get("description") or "")
    parts.extend(resume.get("skills") or [])
    parts.extend(resume.get("certifications") or [])
    return " ".join(p for p in parts if p)


def _analyze_keywords(job: Any, resume: dict, resume_text: str) -> dict:
    job_description = getattr(job, "description", "") or ""
    keywords = extract_keywords(job_description)
    if not keywords:
        return {
            "score": None,
            "available": False,
            "matched_keywords": [],
            "missing_keywords": [],
        }
    full_text = _resume_full_text(resume, resume_text).lower()

    matched = []
    missing = []
    for kw in keywords:
        needle = kw.lower()
        if needle in full_text:
            matched.append(kw)
        else:
            missing.append(kw)

    # Score: fraction of meaningful keywords that appear in the resume.
    score = 0.0
    if keywords:
        score = round((len(matched) / len(keywords)) * 100, 1)
    return {
        "score": score,
        "available": True,
        "matched_keywords": matched,
        "missing_keywords": missing,
    }


# =============================================================================
# Experience relevance
# =============================================================================
def _analyze_experience(job: Any, resume: dict, resume_text: str) -> dict:
    experience = [e for e in (resume.get("experience") or []) if e]
    job_description = getattr(job, "description", "") or ""
    title = (job.title or "").lower()
    description = job_description.lower()
    skills_keywords = set(
        (_required_skills_from_job(job) + extract_keywords(job_description))
    )
    expected_level = (getattr(job, "experience_level", "") or "").lower()

    # Is there enough job-side signal to judge experience relevance?
    has_signal = bool(title or description or expected_level)
    if not has_signal:
        return {"score": None, "available": False, "relevant_experience": []}

    title_keywords = _extract_title_keywords(title)

    relevant = []
    scores = []
    for exp in experience:
        role = (exp.get("job_title") or "").lower()
        exp_desc = (exp.get("description") or "").lower()
        exp_text = f"{role} {exp_desc}"
        overlap = 0
        reasons = []

        if role and title_keywords:
            hits = sum(1 for tk in title_keywords if tk in role)
            if hits:
                overlap += hits
                reasons.append(f"role title matches '{exp.get('job_title')}'")

        tech_hits = sum(1 for s in skills_keywords if s and s in exp_text)
        if tech_hits:
            overlap += tech_hits
            reasons.append(f"{tech_hits} required skill(s)/keyword(s) found")

        if overlap:
            score = round(min(100, overlap * 25), 1)
            scores.append(score)
            company = exp.get("company")
            relevant.append({
                "job_title": exp.get("job_title"),
                "company": company,
                "dates": exp.get("dates"),
                "relevance_score": score,
                "reason": "; ".join(reasons),
            })

    if scores:
        avg = round(sum(scores) / len(scores), 1)
    else:
        avg = 0.0
    return {
        "score": avg,
        "available": True,
        "relevant_experience": relevant,
    }


def _extract_title_keywords(title: str) -> set:
    tokens = {t for t in _tokenize(title) if len(t) >= 3 and t not in _STOP_WORDS}
    return set(t for t in tokens)


# =============================================================================
# Project relevance
# =============================================================================
def _analyze_projects(job: Any, resume: dict, resume_text: str) -> dict:
    projects = [p for p in (resume.get("projects") or []) if p]
    required = _required_skills_from_job(job)
    job_description = getattr(job, "description", "") or ""
    keywords = extract_keywords(job_description)
    title_keywords = _extract_title_keywords((job.title or "").lower())

    has_signal = bool(required or keywords or job_description.strip())
    if not has_signal:
        return {"score": None, "available": False, "relevant_projects": []}

    relevant = []
    for proj in projects:
        techs = [t for t in (proj.get("technologies") or []) if t]
        desc = (proj.get("description") or "").lower()
        name = (proj.get("name") or "").lower()
        text = f"{name} {desc}"

        matched_techs = []
        for tech in techs:
            canonical = _normalize_alias(tech)
            if any(
                (match_skill(r) or r).lower() == canonical.lower() for r in required
            ):
                matched_techs.append(canonical if canonical != tech else tech)
            elif canonical.lower() in [k.lower() for k in keywords]:
                matched_techs.append(canonical if canonical != tech else tech)

        keyword_hits = sum(1 for k in keywords if k.lower() in text)
        title_hits = sum(1 for tk in title_keywords if tk in text)

        score = 0
        reasons = []
        if matched_techs:
            score += min(60, len(matched_techs) * 25)
            reasons.append(f"overlaps with {len(matched_techs)} required technologies")
        if keyword_hits:
            score += min(30, keyword_hits * 8)
            reasons.append(f"matches {keyword_hits} job keywords")
        if title_hits:
            score += 15
            reasons.append("relates to the role title")

        if score > 0:
            relevant.append({
                "name": proj.get("name"),
                "relevance_score": round(min(100, score), 1),
                "matched_technologies": matched_techs,
                "reason": "; ".join(reasons),
            })

    if relevant:
        avg = round(sum(r["relevance_score"] for r in relevant) / len(relevant), 1)
    else:
        avg = 0.0
    return {
        "score": avg,
        "available": True,
        "relevant_projects": relevant,
    }


# =============================================================================
# Education / certification relevance
# =============================================================================
def _normalize_degree(label: str) -> str:
    return re.sub(r"\s+", " ", label.strip())


def _analyze_education(job: Any, resume: dict, resume_text: str) -> dict:
    description = getattr(job, "description", "") or ""
    education = [e for e in (resume.get("education") or []) if e]
    certifications = [c for c in (resume.get("certifications") or []) if c]

    # Only active when the job clearly references a degree/certification.
    has_degree_req = _job_has_education_requirement(description)
    has_cert_req = bool(_CERT_REQUIREMENT_RE.search(description))
    if not has_degree_req and not has_cert_req:
        return {
            "score": None,
            "available": False,
            "reason": "No specific education or certification requirement detected.",
        }

    reasons = []
    evidence = 0

    # Degree matching against job description.
    if has_degree_req:
        degree_terms = [t for t in _tokenize(description) if t in {
            "bachelor", "master", "phd", "doctorate", "mba", "btech", "mtech", "bsc", "msc",
        }]
        for edu in education:
            edu_text = " ".join(
                str(v) for v in edu.values() if v
            ).lower()
            matched_field = False
            if any(field.lower() in edu_text for field in _FIELDS_OF_STUDY):
                # Only claim overlap if the same field appears in the description.
                for field in _FIELDS_OF_STUDY:
                    if field.lower() in edu_text and field.lower() in description.lower():
                        matched_field = True
                        reasons.append(f"degree in {field} aligns with the role")
                        break
            if matched_field:
                evidence += 1
            elif degree_terms:
                # A degree is present on the resume and the job wants a degree.
                if any(t in edu_text for t in degree_terms):
                    evidence += 1
                    reasons.append("degree level matches the stated requirement")

    if has_cert_req:
        cert_terms = _extract_cert_terms(description)
        for cert in certifications:
            cl = cert.lower()
            hit = any(ct in cl for ct in cert_terms)
            if hit:
                evidence += 1
                reasons.append(f"certification '{cert}' matches the stated requirement")

    if evidence > 0:
        score = 100.0
    else:
        score = 30.0
        reasons.append("Role mentions education/certification the resume does not clearly show")
    if not reasons:
        reasons.append("Education could not be matched due to limited information")

    return {
        "score": score,
        "available": True,
        "reason": "; ".join(reasons),
    }


_FIELDS_OF_STUDY = [
    "computer science", "software engineering", "data science", "information technology",
    "computer engineering", "machine learning", "artificial intelligence",
    "mechanical engineering", "electrical engineering", "mathematics", "statistics",
    "business administration", "commerce",
]


def _extract_cert_terms(description: str) -> list:
    known = {"aws", "azure", "gcp", "google cloud", "kubernetes", "pmp", "ccna", "ccnp", "scrum", "cisco", "comptia"}
    hits = []
    for k in known:
        if k in description.lower():
            hits.append(k)
    return hits


# =============================================================================
# Improvement suggestions
# =============================================================================
def _build_suggestions(
    skill_analysis: dict,
    keyword_analysis: dict,
    project_analysis: dict,
    education_analysis: dict,
    job: Any,
) -> List[str]:
    suggestions = []

    missing_skills = skill_analysis.get("missing_skills") or []
    missing_keywords = keyword_analysis.get("missing_keywords") or []
    matched_skills = skill_analysis.get("matched_skills") or []
    additional = skill_analysis.get("additional_relevant_skills") or []

    # Missing high-signal skills.
    for ms in missing_skills[:3]:
        suggestions.append(
            f"'{ms}' appears in the job requirements but was not detected in your resume."
        )

    # Emphasise matched skills.
    if matched_skills:
        suggestions.append(
            "Your resume already covers: " + ", ".join(matched_skills[:4])
            + ". Consider highlighting these prominently at the top of your resume."
        )

    # Additional relevant skills worth surfacing.
    if additional:
        suggestions.append(
            "You also list relevant technology not explicitly required ("
            + ", ".join(additional[:4])
            + "). Mention these if they apply to the role."
        )

    # Missing keywords.
    for kw in missing_keywords[:3]:
        if not match_skill(kw):
            suggestions.append(
                f"The job description repeatedly references '{kw}'; consider including "
                "it in your summary or experience bullets where it is genuinely true."
            )

    # Strong projects to emphasise.
    strong_projects = [
        p for p in (project_analysis.get("relevant_projects") or [])
        if p.get("relevance_score", 0) >= 60
    ]
    for proj in strong_projects[:2]:
        reasons = proj.get("matched_technologies") or []
        tech_phrase = ", ".join(reasons[:4]) if reasons else "several required technologies"
        suggestions.append(
            f"Your project '{proj.get('name')}' has strong overlap ({tech_phrase}). "
            "Consider emphasizing it in your application."
        )

    # Education if relevant.
    if education_analysis.get("available") and (education_analysis.get("score") or 0) < 60:
        suggestions.append(
            "This role mentions an education or certification requirement. Make sure your "
            "education and any relevant certifications are clearly visible on your resume."
        )

    if not suggestions:
        suggestions.append(
            "No specific improvements detected. Your resume aligns well with this role's "
            "structured requirements."
        )

    return suggestions[:7]


# =============================================================================
# Public API
# =============================================================================
def analyze_resume_against_job(
    resume_parsed_data: Dict[str, Any],
    job: Any,
    user_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run the deterministic Resume vs Job analysis.

    Args:
        resume_parsed_data: the parsed resume dict (``Resume.parsed_data``).
        job: a Job ORM instance (or object exposing title/company/description/
            required_skills/experience_level).
        user_context: optional, reserved for future human-readable context.

    Returns:
        A structured analysis dict suitable for the API response.
    """
    resume = resume_parsed_data or {}
    resume_text = resume.get("extracted_text") or ""

    skill_analysis = _analyze_skills(job, resume, resume_text)
    keyword_analysis = _analyze_keywords(job, resume, resume_text)
    experience_analysis = _analyze_experience(job, resume, resume_text)
    project_analysis = _analyze_projects(job, resume, resume_text)
    education_analysis = _analyze_education(job, resume, resume_text)

    factor_specs = [
        ("skills", skill_analysis),
        ("keywords", keyword_analysis),
        ("experience", experience_analysis),
        ("projects", project_analysis),
        ("education", education_analysis),
    ]

    # --- Fair overall scoring over active factors only -----------------------
    active = [(name, spec) for name, spec in factor_specs if spec.get("available")]
    active_weight_sum = sum(WEIGHTS[name] for name, _ in active)

    if not active or active_weight_sum <= 0:
        overall_score = 10
        note = (
            "Not enough job information is available to calculate a Resume Match "
            "score. Add more detail to the job (e.g. description or required skills)."
        )
    else:
        weighted = sum(
            (spec.get("score") or 0) * WEIGHTS[name] for name, spec in active
        )
        overall_score = round((weighted / active_weight_sum))
        note = None

    suggestions = _build_suggestions(
        skill_analysis, keyword_analysis, project_analysis, education_analysis, job
    )

    return {
        "overall_score": overall_score,
        "note": note,
        "scores": {
            "skills": _int_or_none(skill_analysis.get("score")),
            "keywords": _int_or_none(keyword_analysis.get("score")),
            "experience": _int_or_none(experience_analysis.get("score")),
            "projects": _int_or_none(project_analysis.get("score")),
            "education": _int_or_none(education_analysis.get("score")),
        },
        "skill_analysis": skill_analysis,
        "keyword_analysis": keyword_analysis,
        "experience_analysis": experience_analysis,
        "project_analysis": project_analysis,
        "education_certification_relevance": education_analysis,
        "matched_skills": skill_analysis.get("matched_skills") or [],
        "missing_skills": skill_analysis.get("missing_skills") or [],
        "additional_relevant_skills": skill_analysis.get("additional_relevant_skills") or [],
        "matched_keywords": keyword_analysis.get("matched_keywords") or [],
        "missing_keywords": keyword_analysis.get("missing_keywords") or [],
        "relevant_projects": project_analysis.get("relevant_projects") or [],
        "relevant_experience": experience_analysis.get("relevant_experience") or [],
        "suggestions": suggestions,
    }


def _int_or_none(value) -> Optional[int]:
    if value is None:
        return None
    return int(round(value))
