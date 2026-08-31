"""
Resume Intelligence - Phase 1: PDF parsing + structured extraction.

This module provides deterministic (no LLM) extraction of structured
resume data from PDF files. It is intentionally simple and safe:

- Text is extracted from text-based PDFs using PyMuPDF.
- Scanned/image-only PDFs (little or no extractable text) are detected
  and reported as a structured error. OCR is NOT performed.
- Structured fields are only populated when they can be reasonably
  identified from the resume text. Nothing is fabricated.
"""

import json
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

SCANNED_PDF_ERROR = (
    "This resume appears to be image-based or scanned. Please upload a text-based PDF."
)

# ---- Section headers commonly found in resumes ------------------------------
# Terms are configured once and used to build both whole-line headers
# ("EXPERIENCE") and inline headers ("Skills: Python, FastAPI").
_SECTION_TERMS = {
    "summary": (
        r"professional\s+summary", r"summary", r"profile", r"about\s+me",
        r"career\s+objective", r"objective", r"professional\s+profile",
        r"executive\s+summary",
    ),
    "skills": (
        r"technical\s+skills", r"skills\s*&\s*technologies",
        r"skills\s*&\s*tools", r"technical\s+expertise",
        r"technical\s+proficiencies", r"core\s+skills", r"skills",
        r"core\s+competencies", r"technologies", r"technologies\s*&\s*tools",
        r"professional\s+skills", r"areas\s+of\s+expertise",
        r"competencies", r"skills\s*&\s+abilities", r"tech\s+stack",
    ),
    "experience": (
        r"professional\s+experience", r"work\s+experience",
        r"employment\s+history", r"experience", r"employment",
        r"professional\s+background", r"career\s+history", r"work\s+history",
        r"internship\s+experience", r"internships",
    ),
    "education": (
        r"education", r"academic\s+background", r"academic\s+qualification",
        r"academic\s+qualifications", r"educational\s+background",
        r"educational\s+qualifications", r"academics", r"qualifications",
        r"schooling",
    ),
    "projects": (
        r"projects", r"personal\s+projects", r"academic\s+projects",
        r"key\s+projects", r"major\s+projects", r"notable\s+projects",
        r"featured\s+projects", r"capstone\s+projects",
        r"project\s+experience", r"side\s+projects", r"personal\s+work",
        r"academic\s+work", r"development\s+projects", r"practical\s+projects",
    ),
    "certifications": (
        r"certifications", r"certificates", r"certification", r"licenses",
        r"licenses\s*&\s+certifications", r"courses",
        r"courses\s*&\s+certifications", r"professional\s+certifications",
        r"certificates\s*&\s+licenses", r"training\s*&\s+certifications",
    ),
    "contact": (r"contact", r"contact\s+information", r"links"),
    "languages": (r"languages",),
}

# Trailing separator decoration commonly follows a heading, e.g. "SKILLS ----".
_HEADER_TRAIL_RE = r"[:.]?[\s\-•_|~]*"


def _header_regex(terms: tuple) -> re.Pattern:
    inner = "|".join(terms)
    return re.compile(r"(?i)^(" + inner + r")\s*" + _HEADER_TRAIL_RE + r"$")


def _inline_header_regex(terms: tuple) -> re.Pattern:
    inner = "|".join(terms)
    return re.compile(r"(?i)^(" + inner + r")\s*[:.]\s*(\S.*)$")


_SECTION_PATTERNS = {name: _header_regex(terms) for name, terms in _SECTION_TERMS.items()}
_INLINE_HEADER_PATTERNS = {
    name: _inline_header_regex(terms) for name, terms in _SECTION_TERMS.items()
}

# Section headers must appear as a standalone-ish line (short, mostly letters).
_HEADER_MAX_LEN = 48


@dataclass
class BasicInfo:
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None


@dataclass
class ParsedResumeData:
    basic_info: BasicInfo = field(default_factory=BasicInfo)
    skills: List[str] = field(default_factory=list)
    education: List[Dict[str, Any]] = field(default_factory=list)
    experience: List[Dict[str, Any]] = field(default_factory=list)
    projects: List[Dict[str, Any]] = field(default_factory=list)
    certifications: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["basic_info"] = {k: v for k, v in data["basic_info"].items() if v not in (None, "")}
        # Prune empty objects within lists.
        data["education"] = [e for e in data["education"] if any(e.values())]
        data["experience"] = [e for e in data["experience"] if any(e.values())]
        data["projects"] = [p for p in data["projects"] if any(p.values())]
        data["certifications"] = [c for c in data["certifications"]]
        data["skills"] = [s for s in data["skills"]]
        return data


# =============================================================================
# Skill vocabulary (deterministic, case-insensitive matching)
# =============================================================================
SKILL_VOCABULARY = [
    # Programming languages
    "Python", "JavaScript", "TypeScript", "Java", "C",
    "C++", "C#", "Go", "Golang", "Rust", "Ruby", "PHP", "Kotlin",
    "Swift", "Scala", "R", "MATLAB", "Perl", "Shell", "Bash", "PowerShell",
    "SQL", "GraphQL", "HTML", "CSS", "Sass", "SCSS", "Objective-C", "Dart",
    "Elixir", "Haskell", "Solidity", "Assembly", "COBOL", "Fortran", "Lua",
    # Frontend frameworks / libraries
    "React", "React Native", "Next.js", "Vue.js", "Vue", "Angular", "Svelte",
    "Redux", "jQuery", "Bootstrap", "Tailwind CSS", "Tailwind", "Material UI",
    "MUI", "Chakra UI", "Ember.js", "Backbone.js", "Lit", "NativeScript",
    "Flutter", "Storybook", "Webpack", "Vite", "Gatsby", "Remix", "Nuxt",
    "Three.js", "D3.js", "Chart.js", "Framer Motion",
    # Backend / frameworks
    "FastAPI", "Flask", "Django", "Express", "Express.js", "Spring Boot",
    "Spring", "Node.js", "Node", "Ruby on Rails", "Rails", "Laravel", "ASP.NET",
    ".NET", "Ktor", "Play Framework", "Gin", "Echo", "Fiber", "Hapi",
    "NestJS", "GraphQL Apollo", "Celery", "Phoenix", "Gunicorn", "Uvicorn",
    "REST API", "RESTful", "SOAP", "gRPC", "WebSockets", "Microservices",
    # Databases
    "PostgreSQL", "Postgres", "MySQL", "SQLite", "MongoDB", "Redis", "Cassandra",
    "DynamoDB", "Oracle", "SQL Server", "MSSQL", "Mariadb", "Elasticsearch",
    "Neo4j", "CouchDB", "Firebase Firestore", "Firebase", "Supabase", "Prisma",
    "SQLAlchemy", "Hibernate", "Knex", "Sequelize", "Drizzle",
    # DevOps / cloud / infra
    "Docker", "Kubernetes", "AWS", "Amazon Web Services", "Azure",
    "Google Cloud Platform", "GCP", "Terraform", "Ansible", "Jenkins",
    "GitHub Actions", "CI/CD", "Grafana", "Prometheus", "Datadog",
    "New Relic", "Nginx", "Apache", "Linux", "Git", "GitHub", "GitLab",
    "Bitbucket", "Helm", "ArgoCD", "OpenShift", "Nix", "Vagrant",
    "Serverless", "Lambda", "S3", "EC2", "ECS", "Fargate", "CloudFormation",
    # Testing
    "Pytest", "Jest", "Mocha", "Chai", "Cypress", "Playwright", "Selenium",
    "TestNG", "JUnit", "Mockito", "qTest", "Lighthouse", "K6",
    # Data / ML / AI
    "Pandas", "NumPy", "SciPy", "Scikit-learn", "Scikit Learn", "TensorFlow",
    "PyTorch", "Keras", "Hugging Face", "Transformers", "NLTK", "OpenCV",
    "Matplotlib", "Seaborn", "Plotly", "Jupyter", "Apache Spark", "Spark",
    "Hadoop", "Airflow", "Kafka", "PowerBI", "Power BI", "Tableau",
    "Looker", "Excel", "Apache Beam", "MLOps", "RAG", "LangChain",
    "Feature Engineering", "Deep Learning", "Machine Learning", "Natural Language",
    # Tools / misc
    "JIRA", "Confluence", "Figma", "Sketch", "Adobe XD", "Agile", "Scrum",
    "Kanban", "Trello", "Notion", "Slack", "Postman", "Swagger", "OpenAPI",
    "Gradle", "Maven", "npm", "yarn", "pnpm", "Bun", "VS Code", "IntelliJ",
    "zsh", "Cron", "Linux CLI",
]

# Normalised lookup: lowercase -> canonical name.
_SKILL_LOOKUP: Dict[str, str] = {}
for _skill in SKILL_VOCABULARY:
    _key = re.sub(r"\s+", " ", _skill.strip()).lower()
    _SKILL_LOOKUP[_key] = _skill
    # Also index without spaces/punctuation so "firebase" matches "Firebase".
    _compact = re.sub(r"[^a-z0-9]", "", _key)
    if _compact != _key:
        _SKILL_LOOKUP.setdefault(_compact, _skill)


_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(
    r"(?<!\w)(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)?\d{3}[\s.-]?\d{4}(?!\w)"
)
_URL_RE = re.compile(r"(?i)\bhttps?://[^\s]+|(?:\bwww\.)[^\s]+")
_LINKEDIN_RE = re.compile(r"(?i)\b(?:https?://)?(?:www\.)?linkedin\.com/[^\s,;\"]+")
_GITHUB_RE = re.compile(r"(?i)\b(?:https?://)?(?:www\.)?github\.com/[^\s,;\"]+")
_PORTFOLIO_RE = re.compile(r"(?i)\b(?:https?://)?(?:www\.)?([\w-]+\.(?:dev|me|io|app|site|github\.io))[^\s]*")


def extract_pdf_text(file_path: str, min_chars: int = 20) -> str:
    """
    Extract readable text from a PDF file.

    Raises:
        ValueError: if the file is not a PDF.
        RuntimeError: if the PDF cannot be parsed by the library.
        _ScannedPdfError: if the PDF appears to be image-based/scanned
            (too little extractable text).
    """
    if not str(file_path).lower().endswith(".pdf"):
        raise ValueError("Only PDF files are supported for text extraction")

    import pymupdf  # PyMuPDF (works on Python 3.10+ via abi3 wheels)

    try:
        doc = pymupdf.open(file_path)
    except Exception as exc:
        raise RuntimeError(f"Unable to open PDF file: {exc}") from exc

    try:
        text_parts = []
        for page in doc:
            text_parts.append(page.get_text("text") or "")
    finally:
        doc.close()

    text = "\n".join(text_parts)
    text = normalize_whitespace(text)

    if len(text.strip()) < min_chars:
        raise _ScannedPdfError(SCANNED_PDF_ERROR)

    return text


class _ScannedPdfError(Exception):
    """Raised when a PDF yields little/no extractable text (scanned/image)."""


def normalize_whitespace(text: str) -> str:
    """Collapse runs of whitespace and normalise newlines."""
    if not text:
        return ""
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        line = " ".join(line.split())
        cleaned.append(line)
    return "\n".join(cleaned)


def parse_resume(text: str) -> ParsedResumeData:
    """Deterministically parse structured resume data from raw text."""
    if not text:
        return ParsedResumeData()

    lines = text.splitlines()
    result = ParsedResumeData()

    result.basic_info = _extract_basic_info(text, lines)

    sections = _split_into_sections(lines)
    result.skills = _extract_skills(sections.get("skills", []))
    # Also hoist skills that appear as standalone lines in the summary/contact
    # areas if they were not captured by a dedicated skills section.
    if not result.skills:
        result.skills = _extract_skills_loose(lines)

    result.education = _extract_education(sections.get("education", []))
    result.experience = _extract_experience(sections.get("experience", []), lines)
    result.projects = _extract_projects(sections.get("projects", []))
    result.certifications = _extract_certifications(
        sections.get("certifications", []), lines
    )

    return result


def parse_resume_file(file_path: str) -> Dict[str, Any]:
    """
    Full pipeline: extract text from a PDF, then parse structured data.

    Returns a dict with the parsed structure. Raises on fatal errors; the
    caller is responsible for mapping the error into a parsing_status.
    """
    text = extract_pdf_text(file_path)
    parsed = parse_resume(text)
    return parsed.to_dict()


# =============================================================================
# Basic info extraction
# =============================================================================
def _extract_basic_info(text: str, lines: List[str]) -> BasicInfo:
    info = BasicInfo()

    emails = _EMAIL_RE.findall(text)
    if emails:
        info.email = emails[0].strip(".")

    phones = _PHONE_RE.findall(text)
    if phones:
        info.phone = phones[0].strip()

    linkedin = _LINKEDIN_RE.findall(text)
    if linkedin:
        info.linkedin = linkedin[0].rstrip(".,;")

    github = _GITHUB_RE.findall(text)
    if github:
        info.github = github[0].rstrip(".,;")

    # Portfolio: a standalone project/profile-style URL that is not LinkedIn/GitHub.
    for match in _URL_RE.findall(text):
        clean = match.rstrip(".,;)")
        low = clean.lower()
        if "linkedin" in low or "github" in low:
            continue
        if _PORTFOLIO_RE.search(clean):
            info.portfolio = clean
            break

    location = _find_location(lines)
    if location:
        info.location = location

    info.name = _guess_name(lines, emails, phones)
    return info


def _find_location(lines: List[str]) -> Optional[str]:
    # Look for "City, ST" or "City, ST, Country" or "City, Country" in the
    # first few lines. Handles pipe-delimited header lines by checking each
    # pipe-separated segment.
    for line in lines[:25]:
        candidates = [seg.strip() for seg in line.split("|")]
        for s in candidates:
            loc = _location_from_segment(s)
            if loc:
                return loc
    return None


def _location_from_segment(s: str) -> Optional[str]:
    if not s or len(s) > 60 or "," not in s:
        return None
    if "@" in s or "linkedin" in s.lower() or "github" in s.lower():
        return None
    if re.search(r"\b(?:https?|www\.)", s, re.I):
        return None
    if re.search(r"\d{3}[\s.-]?\d{4}", s):  # looks like a phone number
        return None
    parts = [p.strip() for p in s.split(",") if p.strip()]
    if not (2 <= len(parts) <= 4):
        return None
    if any(not re.match(r"^[A-Z][A-Za-z .'-]{1,40}$", p) for p in parts):
        return None
    if all(p[0].isupper() for p in parts):
        return s
    return None


def _guess_name(lines: List[str], emails: List[str], phones: List[str]) -> Optional[str]:
    """Heuristic: name is usually the first non-empty line without punctuation
    that isn't an email, phone, URL, or a known section header."""
    if not lines:
        return None

    blocked = set()
    if emails:
        blocked.add(emails[0].lower())
    for p in phones:
        blocked.add("".join(ch for ch in p if ch.isdigit()))

    for line in lines[:12]:
        s = line.strip()
        if not s or len(s) > 40:
            continue
        if re.search(r"[@:]", s) or re.search(r"\d", s):
            continue
        if _PORTFOLIO_RE.search(s) or "linkedin" in s.lower() or "github" in s.lower():
            continue
        if s.lower() in blocked:
            continue
        # Keep only names made of letters/spaces/hyphens/apostrophes.
        words = s.split()
        if len(words) < 2 or len(words) > 5:
            continue
        if all(re.match(r"^[A-Za-z][A-Za-z'.-]*$", w) for w in words):
            return s
    return None


# =============================================================================
# Section splitting
# =============================================================================
def _split_into_sections(lines: List[str]) -> Dict[str, List[str]]:
    sections: Dict[str, List[str]] = {}
    current: Optional[str] = None
    buffer: List[str] = []

    def flush():
        if current:
            sections.setdefault(current, []).extend(buffer)
        buffer.clear()

    for line in lines:
        stripped = line.strip()
        header = _match_section_header(stripped)
        if header is not None:
            flush()
            current = header
            continue
        # Condensed/two-column layouts sometimes use "Skills: Python, FastAPI".
        inline = _match_inline_section_header(stripped)
        if inline is not None:
            flush()
            current = inline[0]
            buffer.append(inline[1])
            continue
        buffer.append(line)

    flush()
    return sections


def _match_section_header(line: str) -> Optional[str]:
    if not line or len(line) > _HEADER_MAX_LEN:
        return None
    for name, pattern in _SECTION_PATTERNS.items():
        if pattern.fullmatch(line):
            return name
    return None


def _match_inline_section_header(line: str) -> Optional[tuple[str, str]]:
    """Detect a heading used inline, e.g. `Skills: Python, FastAPI`.

    Returns (section_name, content) when the line begins with a known heading
    followed by a colon/dot and real content. Used to support condensed and
    two-column layouts where the heading shares a line with its content.
    """
    if not line or len(line) > 120:
        return None
    for name, pattern in _INLINE_HEADER_PATTERNS.items():
        match = pattern.match(line)
        if match:
            return name, match.group(2).strip()
    return None


# =============================================================================
# Skills
# =============================================================================
def _extract_skills(lines: List[str]) -> List[str]:
    """Extract known skills from a skills section. Handles both bulleted and
    comma/pipe separated layouts."""
    if not lines:
        return []
    joined = " ".join(l.lstrip("-•*").strip() for l in lines)
    for sep in [",", "|", "•", "·", "–", "-"]:
        if sep in joined:
            candidates = [_clean_skill(t) for t in joined.split(sep)]
            break
    else:
        candidates = [_clean_skill(l.lstrip("-•*").strip()) for l in lines]

    found = set()
    for cand in candidates:
        skill = match_skill(cand)
        if skill:
            found.add(skill)
        else:
            # Multi-word candidate may itself contain a known skill.
            for token in re.split(r"\s+", cand):
                s = match_skill(token)
                if s:
                    found.add(s)
    return _ordered_skills(found)


def _extract_skills_loose(lines: List[str]) -> List[str]:
    """Scan the whole document for known skills on short standalone lines and
    within comma/pipe separated lists."""
    found = set()
    for line in lines:
        s = line.strip().lstrip("-•* ")
        if not s:
            continue
        if len(s) > 60:
            continue
        # Try the whole line first, then split on common separators.
        skill = match_skill(s)
        if skill:
            found.add(skill)
            continue
        for sep in [",", "|", "•", "·", "–", ";"]:
            if sep in s:
                for token in s.split(sep):
                    cand = _clean_skill(token)
                    if cand and len(cand) <= 40:
                        m = match_skill(cand)
                        if m:
                            found.add(m)
                break
    return _ordered_skills(found)


def _ordered_skills(skills: set) -> List[str]:
    order = {s: i for i, s in enumerate(SKILL_VOCABULARY)}
    return sorted(skills, key=lambda s: order.get(s, 10**6))


def _clean_skill(token: str) -> str:
    return re.sub(r"^[\s\-•*]+|[\s,\.]+$", "", token.strip()).strip()


def match_skill(token: str) -> Optional[str]:
    """Case-insensitive canonical skill match against the vocabulary."""
    t = re.sub(r"\s+", " ", token.strip()).lower()
    if not t:
        return None
    if t in _SKILL_LOOKUP:
        return _SKILL_LOOKUP[t]
    compact = re.sub(r"[^a-z0-9]", "", t)
    if compact in _SKILL_LOOKUP:
        return _SKILL_LOOKUP[compact]
    return None


# =============================================================================
# Education
# =============================================================================
_DEGREE_LABELS = [
    "B.Tech", "Bachelor of Technology", "B.E.", "Bachelor of Engineering",
    "M.Tech", "Master of Technology", "M.E.", "Master of Engineering",
    "MBA", "Master of Business Administration",
    "Master of Science", "M.Sc.", "B.Sc.", "Bachelor of Science",
    "Bachelor of Arts", "BA", "PhD", "Doctorate",
    "BCA", "MCA", "BBA", "BCom", "MCom", "High School", "Diploma",
    "Bachelor", "Bachelors", "Master", "Masters",
]

_COLLEGE_TAGS = ["university", "college", "institute", "institution", "school", "academy"]
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")


def _extract_education(lines: List[str]) -> List[Dict[str, Any]]:
    if not lines:
        return []
    try:
        entries = _try_chunk_education(lines)
    except Exception:  # noqa: BLE001
        entries = []
    if entries:
        return entries
    return []


def _try_chunk_education(lines: List[str]) -> List[Dict[str, Any]]:
    """Parse education entries. Handles both blank-line separated entries and
    single-line entries such as 'B.Tech in Computer Science, XYZ University, 2020'."""
    text = "\n".join(lines)
    # If the section does not look like education at all, return nothing.
    looks_like_education = (
        bool(_find_degree(text))
        or bool(_find_institution(text))
        or bool(_YEAR_RE.search(text))
        or any(tag in text.lower() for tag in _COLLEGE_TAGS)
    )
    if not looks_like_education:
        return []

    chunks: List[List[str]] = []
    current: List[str] = []
    for line in lines:
        if not line.strip():
            if current:
                chunks.append(current)
                current = []
        else:
            current.append(line)
    if current:
        chunks.append(current)

    # If no blank-line separation and the block is long, split on degree markers.
    if len(chunks) <= 1:
        combined = [l.strip() for l in lines if l.strip()]
        if len(combined) > 1:
            degree_line_idx = [
                i for i, l in enumerate(combined) if _find_degree(l)
            ]
            if len(degree_line_idx) > 1:
                chunks = []
                start = 0
                for idx in degree_line_idx[1:]:
                    chunks.append(combined[start:idx])
                    start = idx
                chunks.append(combined[start:])

    entries = []
    for chunk in chunks:
        entry = _parse_education_entry(chunk)
        if entry:
            entries.append(entry)
    return entries


def _parse_education_entry(chunk: List[str]) -> Dict[str, Any]:
    raw = " ".join(l.strip() for l in chunk if l.strip())
    text = " ".join(raw.split())
    entry: Dict[str, Any] = {}

    degree = _find_degree(text)
    if degree:
        entry["degree"] = degree

    institution = _find_institution(text)
    if institution:
        entry["institution"] = institution

    field = _find_field_of_study(text)
    if field:
        entry["field_of_study"] = field

    year = _find_grad_year(text)
    if year:
        entry["graduation_year"] = year

    if not entry:
        # Fallback: pick the longest meaningful token as institution if available.
        inst = _find_institution(text)
        if inst:
            entry["institution"] = inst
        return entry
    return entry


def _find_degree(text: str) -> Optional[str]:
    for label in _DEGREE_LABELS:
        if re.search(_build_degree_regex(label), text):
            return _normalise_degree(label)
    return None


def _build_degree_regex(label: str) -> str:
    parts = []
    for ch in label:
        if ch == ".":
            parts.append(r"\.?")
        elif ch == " ":
            parts.append(r"\s+")
        else:
            parts.append(re.escape(ch))
    return r"(?i)\b" + "".join(parts) + r"\b"


def _normalise_degree(label: str) -> str:
    compact = re.sub(r"\s+\.", ".", label).replace(" .", ".").strip()
    return re.sub(r"\s+", " ", compact)


def _find_institution(text: str) -> Optional[str]:
    # Look for a "college/university ..." style token followed by a proper noun.
    match = re.search(
        r"(?i)\b((?:[A-Z][\w .'&-]*)?(?:University|College|Institute|Institution|"
        r"School|Academy)[A-Za-z0-9 .'&-]*)\b",
        text,
    )
    if match:
        return _clean_institution(match.group(1))
    return None


def _clean_institution(inst: str) -> str:
    inst = re.sub(r"[,;:]+$", "", inst).strip()
    for word in ("the ", "a "):
        if inst.lower().startswith(word) and len(inst) > len(word) + 3:
            inst = inst[len(word):].strip()
    return inst


_FIELDS = [
    "Computer Science and Engineering",
    "Computer Science",
    "Computer Engineering",
    "Information Technology",
    "Electronics and Communication Engineering",
    "Electronics and Telecommunication",
    "Electronics and Communication",
    "Electronics",
    "Data Science",
    "Artificial Intelligence and Machine Learning",
    "Artificial Intelligence",
    "Machine Learning",
    "Cyber Security",
    "Software Engineering",
    "Computer Applications",
    "Business Administration",
    "Mechanical Engineering",
    "Electrical and Electronics Engineering",
    "Electrical Engineering",
    "Civil Engineering",
    "Aerospace Engineering",
    "Biotechnology",
    "Commerce",
    "Physics",
    "Mathematics",
    "Statistics",
    "Economics",
    "Chemistry",
]

_FIELD_RE = re.compile(r"(?i)\b(" + "|".join(re.escape(f) for f in _FIELDS) + r")\b")


def _find_field_of_study(text: str) -> Optional[str]:
    m = _FIELD_RE.search(text)
    if m:
        return m.group(1).strip()
    m = re.search(r"(?i)\b(?:b\.?tech|b\.?e)\s+in\s+([A-Z][A-Za-z &.-]+)", text)
    if m:
        return m.group(1).strip().rstrip(".,;")
    m = re.search(r"(?i)\b(?:major|speciali[sz]ation|speciali[sz]ing)[:]\s*([A-Z][A-Za-z &.-]+)\b", text)
    if m:
        return m.group(1).strip().rstrip(".,;")
    return None


def _find_grad_year(text: str) -> Optional[str]:
    years = [y for y in _YEAR_RE.findall(text) if len(y) == 4]
    if not years:
        return None
    years = sorted(set(years), key=int)
    return years[-1]


# =============================================================================
# Experience
# =============================================================================
_ROLE_HINTS = [
    "engineer", "developer", "manager", "analyst", "architect", "scientist",
    "designer", "consultant", "lead", "intern", "internship", "administrator",
    "specialist", "coordinator", "director", "head", "owner", "founder",
    "officer", "researcher", "assistant", "associate", "product", "principal",
    "senior", "junior", "trainee", "freelancer", "contractor",
]


def _extract_experience(section_lines: List[str], all_lines: List[str]) -> List[Dict[str, Any]]:
    lines = section_lines if section_lines else None

    if lines is None:
        # Only fall back to scanning the document if there is evidence of work
        # experience (role hints or date ranges); otherwise never fabricate.
        if not _has_experience_evidence(all_lines):
            return []
        lines = all_lines[:60]
    if not lines:
        return []

    chunks = _split_experience_chunks(lines)
    entries = []
    for chunk in chunks:
        header, bullets = _split_header_bullets(chunk)
        header_text = " ".join(header).strip()
        entry: Dict[str, Any] = {}

        dates = _extract_dates_from_header(header_text)
        header_without_dates = _strip_dates(header_text)
        header_without_dates = re.sub(r"\s+", " ", header_without_dates).strip(" ,-–")

        role = _find_role(header_without_dates)

        company_text = header_without_dates
        if role:
            company_text = company_text.replace(role, "", 1)
        company = _find_company(company_text, header)
        company = _clean_company(company, role)

        if role:
            entry["job_title"] = role
        if company:
            entry["company"] = company
        if dates:
            entry["dates"] = dates

        if bullets:
            entry["description"] = " ".join(
                b.lstrip("-•* ").strip() for b in bullets if b.strip()
            )

        if entry:
            entries.append(entry)
    return entries


def _has_experience_evidence(lines: List[str]) -> bool:
    if not lines:
        return False
    return bool(_DATE_TOKEN_RE.search("\n".join(lines))) or any(
        _find_role(line) for line in lines[:40]
    )


_MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec"
_DATE_TOKEN_RE = re.compile(
    r"(?i)\b(" + _MONTHS + r")(?:[\w.]*)\s*,?\s*(\d{4})|\b(present|current|now)\b|\b((?:19|20)\d{2})\b"
)


def _extract_dates_from_header(text: str) -> Optional[str]:
    matches = _DATE_TOKEN_RE.findall(text)
    if not matches:
        return None
    tokens = []
    for month, year, present, four in matches:
        if present:
            tokens.append("Present")
        elif four:
            tokens.append(four)
        elif month and year:
            tokens.append(f"{month.capitalize()} {year}")
    # Deduplicate preserving order.
    seen = set()
    unique = []
    for t in tokens:
        if t.lower() not in seen:
            seen.add(t.lower())
            unique.append(t)
    if not unique:
        return None
    return " - ".join(unique)


def _strip_dates(text: str) -> str:
    return _DATE_TOKEN_RE.sub(" ", text)


def _split_on_blank_lines(lines: List[str]) -> List[List[str]]:
    """Split lines into chunks separated by blank/empty lines."""
    chunks: List[List[str]] = []
    current: List[str] = []
    for line in lines:
        if not line.strip():
            if current:
                chunks.append(current)
                current = []
        else:
            current.append(line)
    if current:
        chunks.append(current)
    return chunks


def _split_experience_chunks(lines: List[str]) -> List[List[str]]:
    chunks = _split_on_blank_lines(lines)

    if len(chunks) > 1:
        return chunks

    # No blank-line separation: split where a new role/company header begins
    # (a line containing a role hint or a year, before the bullet lines).
    combined = [l for l in lines if l.strip()]
    if len(combined) <= 1:
        return [[l for l in lines if l.strip()]] if combined else []

    new_chunks: List[List[str]] = []
    current = []
    for line in combined:
        is_bullet = bool(re.match(r"^[-•*]\s", line.strip()))
        starts_header = (
            not is_bullet
            and (_find_role(line) or bool(_DATE_TOKEN_RE.search(line)))
            and current
            and any(re.match(r"^[-•*]\s", c.strip()) for c in current)
        )
        if starts_header:
            new_chunks.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        new_chunks.append(current)
    return new_chunks if new_chunks else [combined]


# Words that remain lowercase in an otherwise Title Case heading.
_PROJECT_TITLE_FUNCTION_WORDS = {
    "a", "an", "the", "of", "in", "on", "at", "to", "for", "and", "or",
    "with", "from", "via", "by", "over", "under",
}


def _looks_like_title_line(line: str) -> bool:
    """Whether a non-blank line is a heading for a new project entry.

    A project title is a short line written in Title Case that is not a
    bullet, not a technology-only list, and not an experience header.
    """
    s = line.strip().lstrip("-•* ").strip()
    if not s or len(s) > 70:
        return False
    if re.match(r"^[-•*]\s", line.strip()):
        return False
    if _find_role(s) or _DATE_TOKEN_RE.search(s) or _looks_like_role(s):
        return False
    if _is_tech_only_line(s):
        return False
    # Description lines usually end with sentence punctuation.
    if s.endswith((".", ",", ";", ":")):
        return False
    words = s.split()
    if not (2 <= len(words) <= 12):
        return False
    for w in words:
        if re.fullmatch(r"[A-Z0-9][A-Za-z0-9_+./&'-]*", w):
            continue
        if w.lower() in _PROJECT_TITLE_FUNCTION_WORDS:
            continue
        return False
    return True


def _split_project_chunks(lines: List[str]) -> List[List[str]]:
    """Split a projects section into per-project entries.

    Uses blank-line grouping first, then falls back to Title Case headings
    for condensed/layout-shifted PDFs where blank lines were lost during
    text extraction.
    """
    chunks = _split_on_blank_lines(lines)
    if len(chunks) > 1:
        return chunks

    combined = [l for l in lines if l.strip()]
    if len(combined) <= 1:
        return [combined] if combined else []

    new_chunks: List[List[str]] = []
    current: List[str] = []
    for line in combined:
        if _looks_like_title_line(line) and current:
            new_chunks.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        new_chunks.append(current)
    return new_chunks if new_chunks else [combined]


def _split_header_bullets(chunk: List[str]) -> tuple[List[str], List[str]]:
    header: List[str] = []
    bullets: List[str] = []
    for line in chunk:
        if re.match(r"^[-•*]\s", line.strip()):
            bullets.append(line)
        else:
            header.append(line)
    return header, bullets


def _clean_company(company: Optional[str], role: Optional[str]) -> Optional[str]:
    if not company:
        return None
    c = company.strip().strip(" ,-–:;")
    if role and c.lower().startswith(role.lower()):
        c = c[len(role):].strip(" ,-–:;")
    if not c or len(c) > 80:
        return None
    if re.match(r"^[-–—|,]+$", c):
        return None
    return c


def _find_role(text: str) -> Optional[str]:
    match = re.search(
        r"(?i)\b((?:Senior|Junior|Lead|Principal|Staff|Associate|Assistant|"
        r"Head|Chief|Founding|Entry\s*Level)?\s*(?:Software\s*)?"
        r"(?:Backend|Back[- ]End|Frontend|Front[- ]End|Full[- ]?[Ss]tack|Data|DevOps|"
        r"ML|Machine\s*Learning|Mobile|UI/UX|QA|Cloud|Security|Product|Web|Systems)?\s*"
        r"(?:Engineer|Developer|Manager|Analyst|Architect|Scientist|Designer|"
        r"Consultant|Lead|Intern|Administrator|Specialist|Coordinator|Director|Head))\b",
        text,
    )
    if match:
        return match.group(1).strip()
    # Fallback: any line containing a role hint.
    for line in text.split("|"):
        for hint in _ROLE_HINTS:
            if hint in line.lower():
                s = line.strip().rstrip(".,;")
                if len(s) <= 80:
                    return s
    return None


def _find_company(text: str, header: Optional[List[str]] = None) -> Optional[str]:
    # Technique 1: "at <Company>" or "<Company> @ role".
    m = re.search(r"(?i)\b(?:at|@)\s+([A-Z][A-Za-z0-9 .&'-]{2,60})", text)
    if m:
        return m.group(1).strip().rstrip(".,;")
    # Technique 2: split the (role/date cleaned) header on separators and take
    # the first capitalized, non-role phrase as the company.
    cleaned = re.sub(r"^[\s,;|—–,\-]+", "", text).strip()
    for part in re.split(r"[|—–]|,|;\s*|\bat\s+", cleaned):
        part = part.strip().strip(" -–,;")
        if not part or len(part) < 2:
            continue
        if _looks_like_role(part):
            continue
        if re.match(r"[A-Z]", part) and len(part) <= 60:
            candidate = re.sub(r"[\s,;]+$", "", part).rstrip(".,;").strip()
            if candidate and not _looks_like_role(candidate):
                return candidate
    return None


def _looks_like_role(text: str) -> bool:
    lower = text.lower()
    return any(hint in lower for hint in _ROLE_HINTS)


# =============================================================================
# Projects
# =============================================================================
def _extract_projects(lines: List[str]) -> List[Dict[str, Any]]:
    if not lines:
        return []
    chunks = _split_project_chunks(lines)
    if not chunks:
        return []

    entries = []
    for chunk in chunks:
        text = " ".join(c for c in chunk if c.strip()).strip()
        title = _find_project_title(chunk, text)
        techs = _extract_skills_loose(chunk)
        entry: Dict[str, Any] = {}
        if title:
            entry["name"] = title
        if techs:
            entry["technologies"] = techs
        desc = _find_project_description(chunk, title, techs)
        if desc:
            entry["description"] = desc
        if entry:
            entries.append(entry)
    return entries


def _find_project_title(lines: List[str], text: str) -> Optional[str]:
    if not lines:
        return None
    first = lines[0].strip().lstrip("-•* ")
    if len(first) > 5 and len(first) <= 90:
        if re.search(r"[\d.]{3,}", first):
            return first
    return first if first and len(first) <= 90 else None


def _find_project_description(lines: List[str], title: Optional[str], techs: List[str]) -> Optional[str]:
    texts = []
    for line in lines:
        s = line.strip().lstrip("-•* ")
        if not s:
            continue
        if title and s.lower() == title.lower():
            continue
        # Skip lines that are pure technology lists.
        if techs:
            clean = re.sub(r"^[\s,.;|\-•*]+|[\s,.;|\-•*]+$", "", s)
            if _is_tech_only_line(clean):
                continue
        texts.append(s)
    if not texts:
        return None
    return " ".join(texts)[:1000]


def _is_tech_only_line(text: str) -> bool:
    if not text or len(text) > 120:
        return False
    # Almost all tokens resolve to known skills.
    tokens = [t.strip(" ,.;") for t in re.split(r"[,;|\s]+", text)]
    tokens = [t for t in tokens if t]
    if not tokens:
        return False
    matched = sum(1 for t in tokens if match_skill(t))
    return matched >= 1 and matched >= len(tokens) - 0


# =============================================================================
# Certifications
# =============================================================================
_CERT_PATTERNS = [
    re.compile(r"(?i)\b[A-Za-z ]*AWS\s+Certified\s+[A-Za-z \-/]{2,40}", re.I),
    re.compile(r"(?i)\b[A-Za-z ]*Azure\s+Certified\s+[A-Za-z \-/]{2,40}"),
    re.compile(r"(?i)\bGoogle\s+Cloud\s+(?:Certified\s+)?[A-Za-z \-/]{2,40}"),
    re.compile(r"(?i)\bCisco\s+(?:Certified\s+)?(?:CCNA|CCNP|CCIE)[A-Za-z \-/]{0,20}"),
    re.compile(r"(?i)\bCompTIA\s+[A-Za-z\+]{2,12}"),
    re.compile(r"(?i)\bPMP\b|Project\s+Management\s+Professional"),
    re.compile(r"(?i)\bCertified\s+(?:Kubernetes|Scrum\s+Product\s+Owner|Data\s+Engineer|"
               r"Machine\s+Learning|Information\s+Systems\s+Security\s+Professional)\b"),
    re.compile(r"(?i)\bProfessional\s+Scrum\s+(?:Master|Product\s+Owner|Developer)\b"),
    re.compile(r"(?i)\bMicrosoft\s+Certified\s+[A-Za-z \-/]{2,40}"),
    re.compile(r"(?i)\bOracle\s+Certified\s+[A-Za-z \-/]{2,40}"),
    re.compile(r"(?i)\bRed\s+Hat\s+Certified\s+[A-Za-z \-/]{2,40}"),
    re.compile(r"(?i)\bCertified\s+Scrum\s+Master\b"),
]


def _extract_certifications(lines: List[str], all_lines: List[str]) -> List[str]:
    source = lines if lines else all_lines[:80]
    if not source:
        return []
    text = " ".join(source)
    found: List[str] = []
    for pat in _CERT_PATTERNS:
        for m in pat.finditer(text):
            cert = m.group(0).strip().rstrip(".,;").strip()
            if cert:
                found.append(_cap_cert(cert))
    # Deduplicate preserving order.
    seen = set()
    unique = []
    for cert in found:
        key = cert.lower()
        if key not in seen:
            seen.add(key)
            unique.append(cert)
    return unique


def _cap_cert(cert: str) -> str:
    # Title-case common leading words while keeping known acronyms uppercase.
    words = cert.split()
    result = []
    for w in words:
        if w.upper() in {"AWS", "CCNA", "CCNP", "CCIE", "PMP", "PMP."}:
            result.append(w.upper())
        else:
            result.append(w)
    return " ".join(result)


# =============================================================================
# JSON-friendly helpers
# =============================================================================
def serialise(parsed: ParsedResumeData) -> Dict[str, Any]:
    return parsed.to_dict()


def dumps(parsed: ParsedResumeData) -> str:
    return json.dumps(parsed.to_dict(), default=str)


# =============================================================================
# Persistence orchestration
# =============================================================================
def parse_and_store(db, resume, min_chars: int = 20) -> None:
    """
    Run the full parsing pipeline against an existing Resume record and persist
    the results (extracted text, structured data, status). Never deletes the
    original resume. Called synchronously by the API.

    On success: sets parsing_status="completed", stores extracted text and
    parsed_data, clears parsing_error.
    On scanned/empty PDF: sets parsing_status="completed" with an empty parse
    result and a user-facing parsing_error describing the scanned-PDF issue.
    On any other failure: sets parsing_status="failed" and stores the error.
    The record and the uploaded file always remain intact.
    """
    try:
        text = extract_pdf_text(resume.file_path, min_chars=min_chars)
    except _ScannedPdfError as exc:
        resume.parsing_status = "completed"
        resume.extracted_text = ""
        resume.parsed_data = None
        resume.parsing_error = str(exc)
        resume.parsed_at = _utcnow()
        db.commit()
        return
    except ValueError as exc:
        resume.parsing_status = "failed"
        resume.parsing_error = str(exc)
        resume.parsed_at = _utcnow()
        db.commit()
        return
    except Exception as exc:  # noqa: BLE001 - never crash the API
        resume.parsing_status = "failed"
        resume.parsing_error = f"Resume parsing failed: {exc}"
        resume.parsed_at = _utcnow()
        db.commit()
        return

    try:
        parsed = parse_resume(text)
        resume.parsing_status = "completed"
        resume.extracted_text = text
        resume.parsed_data = parsed.to_dict()
        resume.parsing_error = None
    except Exception as exc:  # noqa: BLE001
        resume.parsing_status = "failed"
        resume.extracted_text = text
        resume.parsed_data = None
        resume.parsing_error = f"Resume parsing failed: {exc}"
    resume.parsed_at = _utcnow()
    db.commit()


def _utcnow():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)
