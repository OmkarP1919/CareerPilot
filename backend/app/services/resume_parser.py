"""
Resume Intelligence - Phase 2: PDF parsing + structured extraction.

This module provides deterministic (no LLM) extraction of structured
resume data from PDF files.

Design (Resume Parsing 2.0)
---------------------------
Previously parsing relied mainly on blank-line separation and a fragile
Title-Case heuristic to split entries (projects/experience). Real-world
professionally formatted resumes lose blank lines during PDF text extraction
and use en-dash/em-dash bullets, "|" technology separators, Unicode
punctuation, etc. This rewrite keeps the same safe, non-fabricating philosophy
while adding structural/layout-aware logic:

- Layout-aware PDF extraction (PyMuPDF ``get_text("dict")``) that reconstructs
  meaningful line boundaries from block/line geometry, so entries that are
  visually separated stay separated even when the raw text layer has no blank
  lines. The plain ``get_text("text")`` path is retained as a fallback.
- Robust Unicode bullet detection (``-``, en dash ``–``, em dash ``—``,
  ``•``, ``·``, ``*``) with a guard so date ranges like ``Feb 2026 – Mar 2026``
  are NOT mistaken for bullets.
- A generic line classifier (section_header / entry_title / date / bullet /
  technology / page_number / description).
- Structural entry splitting for projects & experience driven by delimiters
  (entry title + "|" technology separator, date lines, bullet transitions).
- Per-category skills extraction with longest-match multi-word support.
- Generalized certifications/awards recognition (not only vendor names).
- Unicode-safe institution parsing and GPA/CGPA extraction.
- A ``summary`` field, per-project ``dates``, per-education ``gpa``, and a
  ``tools_used`` field on experience (so tool lists do not pollute "company").

Public API compatibility
------------------------
``extract_pdf_text``, ``parse_resume``, ``parse_resume_file``,
``parse_and_store``, ``match_skill``, ``normalize_whitespace``,
``_ScannedPdfError`` and ``SCANNED_PDF_ERROR`` are preserved. The plain-text
path (``parse_resume(text)``) requires no PDF/layout metadata and continues to
support the existing unit tests.

Scanning / OCR
--------------
Text is extracted from text-based PDFs. Scanned/image-only PDFs (little or no
extractable text) are detected and reported as a structured error. OCR is NOT
performed, and nothing is fabricated.
"""

import json
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

SCANNED_PDF_ERROR = (
    "This resume appears to be image-based or scanned. Please upload a text-based PDF."
)

# ---- Section headers commonly found in resumes ------------------------------
# Terms are configured once and used for both whole-line headers and inline
# headers. They are strong, but not exclusive, signals for heading detection.
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
        r"skill\s+set",
    ),
    "experience": (
        r"professional\s+experience", r"work\s+experience",
        r"employment\s+history", r"experience", r"employment",
        r"professional\s+background", r"career\s+history", r"work\s+history",
        r"internship\s+experience", r"internships", r"work",
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
        r"project",
    ),
    "certifications": (
        r"certifications", r"certificates", r"certification", r"licenses",
        r"licenses\s*&\s+certifications", r"courses",
        r"courses\s*&\s+certifications", r"professional\s+certifications",
        r"certificates\s*&\s+licenses", r"training\s*&\s+certifications",
        r"awards\s*&\s*certifications", r"awards\s+and\s+certifications",
        r"certifications\s*&\s*awards", r"certifications\s+and\s+awards",
        r"awards", r"awards\s*&\s+honors", r"awards\s+and\s+honors",
        r"honors", r"honors\s*&\s+awards", r"achievements",
        r"recognitions", r"training", r"certificates\s*&\s+licenses",
        r"honor",
    ),
    "contact": (r"contact", r"contact\s+information", r"links"),
    "languages": (r"languages",),
}

# Trailing separator decoration commonly follows a heading, e.g. "SKILLS ----".
_HEADER_TRAIL_RE = r"[:.]?[\s\-•_|~–—=]*"


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
    summary: Optional[str] = None
    skills: List[str] = field(default_factory=list)
    education: List[Dict[str, Any]] = field(default_factory=list)
    experience: List[Dict[str, Any]] = field(default_factory=list)
    projects: List[Dict[str, Any]] = field(default_factory=list)
    certifications: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["basic_info"] = {k: v for k, v in data["basic_info"].items() if v not in (None, "")}
        if data.get("summary") in (None, ""):
            data["summary"] = None
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
    "CNN", "Convolutional Neural Networks", "Convolutional Neural Network",
    "Image Processing", "Computer Vision",
    # Web / scripting / data formats
    "JSP", "JSP/Servlet", "Servlets", "AJAX", "JSON", "XML", "OAuth2", "JWT",
    "RESTful API", "REST API", "Django REST", "Redux Toolkit", "Swagger",
    # Core CS concepts (commonly listed in skills)
    "Data Structures", "Data Structures and Algorithms", "Algorithms",
    "Object-oriented Programming", "Object Oriented Programming", "OOP",
    "DBMS", "Operating Systems", "Computer Networks", "System Design",
    # Tools / misc (deduped with existing single-word entries)
    "Colab", "Google Colab", "Jupyter Notebook", "IntelliJ", "VS Code",
]

# Normalised lookup: lowercase -> canonical name.
_SKILL_LOOKUP: Dict[str, str] = {}
for _skill in SKILL_VOCABULARY:
    _key = re.sub(r"\s+", " ", _skill.strip()).lower()
    _SKILL_LOOKUP[_key] = _skill
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


# =============================================================================
# Layout-aware line model
# =============================================================================
@dataclass
class Line:
    """A single logical line plus optional layout metadata.

    ``text`` is already whitespace-normalised (a single space between words).
    ``block_break`` is True when a PDF block boundary precedes this line (i.e.
    it starts a new visual group). ``font_size`` and ``y`` are best-effort
    layout hints (None for plain-text input).
    """
    text: str
    block_break: bool = False
    font_size: Optional[float] = None
    y: Optional[float] = None
    page: int = 0


def extract_pdf_layout(file_path: str, min_chars: int = 20) -> List[Line]:
    """Layout-aware text extraction: return a list of :class:`Line`.

    Raises the same error types as :func:`extract_pdf_text` (ValueError,
    RuntimeError, _ScannedPdfError).
    """
    if not str(file_path).lower().endswith(".pdf"):
        raise ValueError("Only PDF files are supported for text extraction")

    import pymupdf  # PyMuPDF (works on Python 3.10+ via abi3 wheels)

    try:
        doc = pymupdf.open(file_path)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Unable to open PDF file: {exc}") from exc

    try:
        lines: List[Line] = []
        for pageno in range(len(doc)):
            lines.extend(_extract_page_lines(doc[pageno], pageno))
    finally:
        doc.close()

    text = "\n".join(l.text for l in lines)
    if len(text.strip()) < min_chars:
        raise _ScannedPdfError(SCANNED_PDF_ERROR)
    return lines


def _extract_page_lines(page, pageno: int) -> List[Line]:
    """Extract lines from a single page using geometry metadata where possible."""
    text_lines: List[Line] = []
    data = None
    try:
        data = page.get_text("dict")
    except Exception:  # noqa: BLE001 - fall back to text API
        data = None

    if not data or not isinstance(data, dict):
        raw = page.get_text("text") or ""
        for ln in raw.splitlines():
            line = _normalise_line(ln)
            if line:
                text_lines.append(Line(text=line, page=pageno))
        return text_lines

    raw_lines: List[Tuple[str, Optional[float], Optional[float]]] = []
    block_start_indices: List[int] = []
    idx = 0
    for block in data.get("blocks", []):
        if block.get("type") != 0:
            continue
        block_start_indices.append(idx)
        for bline in block.get("lines", []):
            spans = bline.get("spans") or []
            txt = "".join(s.get("text", "") for s in spans)
            txt = _normalise_line(txt)
            size = None
            if spans and spans[0].get("size"):
                size = float(spans[0]["size"])
            y = None
            bbox = bline.get("bbox")
            if bbox:
                y = float(bbox[1])
            raw_lines.append((txt, size, y))
            idx += 1

    block_start_set = set(block_start_indices)
    for i, (txt, size, y) in enumerate(raw_lines):
        if not txt:
            continue
        text_lines.append(
            Line(
                text=txt,
                block_break=i in block_start_set,
                font_size=size,
                y=y,
                page=pageno,
            )
        )
    return text_lines


def _normalise_line(text: str) -> str:
    """Collapse runs of whitespace in a single line."""
    return " ".join(text.split())


def extract_pdf_text(file_path: str, min_chars: int = 20) -> str:
    """
    Extract readable text from a PDF file as a single string.

    Raises:
        ValueError: if the file is not a PDF.
        RuntimeError: if the PDF cannot be parsed by the library.
        _ScannedPdfError: if the PDF appears to be image-based/scanned.
    """
    return "\n".join(l.text for l in extract_pdf_layout(file_path, min_chars=min_chars))


class _ScannedPdfError(Exception):
    """Raised when a PDF yields little/no extractable text (scanned/image)."""


def normalize_whitespace(text: str) -> str:
    """Collapse runs of whitespace and normalise newlines."""
    if not text:
        return ""
    return "\n".join(" ".join(line.split()) for line in text.splitlines())


def _lines_from_text(text: str) -> List[Line]:
    """Build a Line list from plain text (used by ``parse_resume``)."""
    return [Line(text=ln) for ln in text.splitlines()]


# =============================================================================
# Line classifier
# =============================================================================
_MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec"

_DATE_TOKEN_RE = re.compile(
    r"(?i)\b(" + _MONTHS + r")(?:[\w.]*)\s*,?\s*(\d{4})|\b(present|current|now)\b"
    r"|\b((?:19|20)\d{2})\b"
)

_FULL_DATE_LINE_RE = re.compile(
    r"(?i)^\s*(?:expected\s+)?(?:\b(?:" + _MONTHS + r")\w*\s*)?(?:\b(?:19|20)\d{2}\b)"
    r"\s*(?:[\u2013\u2014\-–]|to)\s*"
    r"(?:expected\s+|present\s*|current\s*|now\s*)?"
    r"(?:[A-Za-z]{3,9}\s*)?\s?"
    r"(?:(?:19|20)\d{2}\b|present|current|now)\s*$",
    re.IGNORECASE,
)
_YEAR_ONLY_LINE_RE = re.compile(r"^\s*(?:19|20)\d{2}\s*$")
_PAGE_NUMBER_RE = re.compile(r"^\s*\d{1,3}\s*$")

_METADATA_LABEL_RE = re.compile(
    r"(?i)^\s*(?:tools?\s+used|technologies?\s*(?:used)?|tech\s+stack"
    r"|technology\s+stack|environment|skills|stack)\s*[:]\s*(.*)$"
)

_BULLET_RE = re.compile(r"^[\-\u2013\u2014\u2022\u00B7*]\s+\S", re.UNICODE)


class LineType:
    SECTION_HEADER = "section_header"
    ENTRY_TITLE = "entry_title"
    DATE = "date"
    BULLET = "bullet"
    TECHNOLOGY = "technology"
    PAGE_NUMBER = "page_number"
    DESCRIPTION = "description"
    CONTINUATION = "continuation"
    UNKNOWN = "unknown"


def is_bullet_line(text: str) -> bool:
    """Whether a line is a bullet (Unicode-safe), not a date range."""
    s = text.strip()
    if not s:
        return False
    if _FULL_DATE_LINE_RE.match(s) or _YEAR_ONLY_LINE_RE.match(s):
        return False
    return bool(_BULLET_RE.match(s))


def strip_bullet_marker(text: str) -> str:
    """Remove a leading bullet marker and following whitespace."""
    return re.sub(r"^[\-\u2013\u2014\u2022\u00B7*]\s+", "", text.strip()).strip()


def is_page_number(text: str) -> bool:
    """Whether a line is a bare standalone page number."""
    s = text.strip()
    return bool(_PAGE_NUMBER_RE.match(s)) and len(s) <= 3


def looks_like_date_line(text: str) -> bool:
    """Whether the whole line is essentially a date/range (guards bullets &
    entry-title detection against date ranges using en dashes)."""
    s = text.strip()
    if not s:
        return False
    if _FULL_DATE_LINE_RE.match(s) or _YEAR_ONLY_LINE_RE.match(s):
        return True
    if _DATE_TOKEN_RE.search(s) and len(s) <= 40:
        # Ensure content is date-only.
        stripped = _DATE_TOKEN_RE.sub(" ", s)
        stripped = re.sub(r"[\s\-–—/,.()]", " ", stripped).strip()
        allowed = {"expected", "to", "present", "current", "now"}
        tokens = {t.lower() for t in stripped.split() if t}
        return all(t in allowed for t in tokens)
    return False


def looks_like_technology_line(text: str) -> bool:
    """Whether a line is essentially a list of technologies."""
    s = text.strip()
    if not s or len(s) > 220:
        return False
    m = _METADATA_LABEL_RE.match(s)
    if m:
        s = m.group(1).strip()
    if not s:
        return False
    tokens = [t.strip(" ,.;|") for t in re.split(r"[,;|:\s]+", s)]
    tokens = [t for t in tokens if t]
    if not tokens:
        return False
    matched = sum(1 for t in tokens if match_skill(t))
    return matched >= 1 and matched >= len(tokens) - 1


def _looks_like_role(text: str) -> bool:
    lower = text.lower()
    return any(hint in lower for hint in _ROLE_HINTS)


def classify_line(line: Line, is_in_skill_section: bool) -> str:
    """Assign a structural type to a line based on content.

    Generality is intentional: content signals (bullets, dates, page numbers,
    metadata labels) plus optional layout hints drive classification, never any
    project/company/date-specific literal.
    """
    text = line.text.strip()
    if not text:
        return LineType.UNKNOWN
    if is_page_number(text):
        return LineType.PAGE_NUMBER
    # Date-range detection MUST precede bullet detection (date ranges use `–`).
    if looks_like_date_line(text):
        return LineType.DATE
    if is_bullet_line(text):
        return LineType.BULLET
    if _METADATA_LABEL_RE.match(text) and len(text) <= 100:
        return LineType.TECHNOLOGY
    if looks_like_technology_line(text):
        return LineType.TECHNOLOGY
    if is_in_skill_section:
        return LineType.DESCRIPTION
    return LineType.UNKNOWN


# =============================================================================
# Section splitting
# =============================================================================
def _match_section_header(line_text: str) -> Optional[str]:
    if not line_text or len(line_text) > _HEADER_MAX_LEN:
        return None
    for name, pattern in _SECTION_PATTERNS.items():
        if pattern.fullmatch(line_text):
            return name
    return None


def _match_inline_section_header(line_text: str) -> Optional[Tuple[str, str]]:
    """Detect a heading used inline, e.g. ``Skills: Python, FastAPI``."""
    if not line_text or len(line_text) > 120:
        return None
    for name, pattern in _INLINE_HEADER_PATTERNS.items():
        match = pattern.match(line_text)
        if match:
            return name, match.group(2).strip()
    return None


def _split_into_sections(lines: List[Line]) -> Dict[str, List[Line]]:
    """Group lines into named sections. Lines before any heading are captured
    as the implicit prelude (used for summary / contact / name)."""
    sections: Dict[str, List[Line]] = {}
    prelude: List[Line] = []
    current: Optional[str] = None
    buffer: List[Line] = []

    def flush():
        if current:
            sections.setdefault(current, []).extend(buffer)
        buffer.clear()

    for line in lines:
        stripped = line.text.strip()
        header = _match_section_header(stripped)
        if header is not None:
            flush()
            current = header
            continue
        inline = _match_inline_section_header(stripped)
        if inline is not None:
            flush()
            current = inline[0]
            if inline[1]:
                buffer.append(Line(text=inline[1], block_break=line.block_break,
                                   font_size=line.font_size, y=line.y, page=line.page))
            continue
        if current is None:
            prelude.append(line)
        else:
            buffer.append(line)

    flush()
    sections["_prelude"] = prelude
    return sections


# =============================================================================
# Projects & experience chunking (structural)
# =============================================================================
# Words that remain lowercase in an otherwise Title Case heading.
_PROJECT_TITLE_FUNCTION_WORDS = {
    "a", "an", "the", "of", "in", "on", "at", "to", "for", "and", "or",
    "with", "from", "via", "by", "over", "under", "using", "is", "are",
}


def _looks_like_title_line(line: Line) -> bool:
    """Whether a line is a Title-Case project heading (fallback signal used
    when there is no '|' technology separator or following date line)."""
    s = line.text.strip().lstrip("-•* ").strip()
    if not s or len(s) > 90:
        return False
    if is_bullet_line(s) or looks_like_date_line(s) or is_page_number(s):
        return False
    if _find_role(s) or _looks_like_role(s) or _is_tech_only_line(s):
        return False
    if re.search(r"[:;,]$", s):
        return False
    # Project titles are short and Title Case (function words excepted).
    words = [w for w in s.split() if w]
    if not (2 <= len(words) <= 12):
        return False
    for w in words:
        stripped = w.strip(".,;:()·•-_")
        if not stripped:
            continue
        if re.fullmatch(r"[A-Z0-9][A-Za-z0-9_+./&'\-]*", stripped):
            continue
        if w.lower() in _PROJECT_TITLE_FUNCTION_WORDS:
            continue
        return False
    return True


def _split_on_blank_lines(lines: List[Line]) -> List[List[Line]]:
    chunks: List[List[Line]] = []
    current: List[Line] = []
    for line in lines:
        if not line.text.strip():
            if current:
                chunks.append(current)
                current = []
        else:
            current.append(line)
    if current:
        chunks.append(current)
    return chunks


def _is_titlecase_ish(text: str) -> bool:
    words = text.split()
    if not (1 <= len(words) <= 12):
        return False
    for w in words:
        stripped = w.strip(".,;:()·•-_")
        if not stripped:
            continue
        if re.fullmatch(r"[A-Z0-9][A-Za-z0-9_+./&'\-]*", stripped):
            continue
        if w.lower() in _PROJECT_TITLE_FUNCTION_WORDS:
            continue
        return False
    return True


def looks_like_project_title(line: Line, nxt: Optional[Line]) -> bool:
    """Heuristic: does this line begin a project entry?"""
    text = line.text.strip().lstrip("-•* ")
    if not text or len(text) > 90:
        return False
    if is_bullet_line(text) or is_page_number(text) or looks_like_date_line(text):
        return False
    if _looks_like_role(text):
        return False
    if "|" in text:
        left, _, right = text.partition("|")
        left = left.strip()
        right = right.strip()
        if len(left) >= 3:
            return True
    if len(text) > 80:
        return False
    if nxt is not None and looks_like_date_line(nxt.text):
        return _is_titlecase_ish(text)
    # Fallback: a clear Title-Case heading (no separators/dates) still marks a
    # boundary; the caller only treats it as a new entry once an entry is in
    # progress.
    return _looks_like_title_line(line)


def _split_entry_by_titles(lines: List[Line], is_project: bool) -> List[List[Line]]:
    """Split lines into entries where a new entry title (or date, for projects)
    begins."""
    combined = [l for l in lines if l.text.strip()]
    if len(combined) <= 1:
        return [combined] if combined else []
    chunks: List[List[Line]] = []
    current: List[Line] = []

    for i, line in enumerate(combined):
        nxt = combined[i + 1] if i + 1 < len(combined) else None
        is_start = _is_entry_start(line, nxt, is_project)
        if is_start and current:
            chunks.append(current)
            current = []
        current.append(line)
    if current:
        chunks.append(current)
    return chunks


def _is_entry_start(line: Line, nxt: Optional[Line], is_project: bool) -> bool:
    text = line.text.strip()
    if not text:
        return False
    if is_bullet_line(text) or is_page_number(text) or looks_like_date_line(text):
        return False
    if is_project:
        return looks_like_project_title(line, nxt)
    return _looks_like_experience_title(line, nxt)


def _looks_like_experience_title(line: Line, nxt: Optional[Line]) -> bool:
    text = line.text.strip()
    if not text or len(text) > 80:
        return False
    if is_bullet_line(text) or is_page_number(text) or looks_like_date_line(text):
        return False
    if _METADATA_LABEL_RE.match(text):
        return False
    if _looks_like_role(text):
        return True
    return False


def split_entry_chunks(lines: List[Line], is_project: bool) -> List[List[Line]]:
    """Split a section's lines into per-entry chunks, structural-first with the
    blank-line path preserved as a fast/safe route when present."""
    if not lines:
        return []
    blank = _split_on_blank_lines(lines)
    if len(blank) > 1:
        refined: List[List[Line]] = []
        for chunk in blank:
            refined.extend(_split_entry_by_titles(chunk, is_project))
        return [c for c in refined if c] or blank
    out = _split_entry_by_titles(lines, is_project)
    return [c for c in out if c]


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
    if re.search(r"\d{3}[\s.-]?\d{4}", s):
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
        words = s.split()
        if len(words) < 2 or len(words) > 5:
            continue
        if all(re.match(r"^[A-Za-z][A-Za-z'.-]*$", w) for w in words):
            return s
    return None


# =============================================================================
# Summary
# =============================================================================
def _extract_summary(lines: List[Line], prelude: List[Line]) -> Optional[str]:
    source = lines if lines else prelude
    if not source:
        return None
    texts = []
    for line in source:
        t = line.text.strip()
        if not t or is_page_number(t):
            continue
        texts.append(t)
    if not texts:
        return None
    summary = " ".join(texts)
    summary = re.sub(r"\s+", " ", summary).strip()
    return summary[:1200] or None


# =============================================================================
# Skills
# =============================================================================
_SKILL_CATEGORY_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9 &/+\-]*?)\s*:\s*(.+)$")


def _extract_skills(lines: List[Line]) -> List[str]:
    """Extract known skills from a skills section.

    Each category line (``Label: skill, skill``) is processed separately so
    multi-word skills and category interactions do not corrupt each other.
    """
    if not lines:
        return []
    found = set()
    for line in lines:
        text = line.text.strip()
        content = line.text.lstrip("-•* ").strip()
        m = _SKILL_CATEGORY_RE.match(content)
        if m and m.group(2).strip():
            tokens = _split_skill_tokens(m.group(2))
        else:
            tokens = _split_skill_tokens(text)
        for tok in tokens:
            for skill in _match_skills_in_token(tok):
                found.add(skill)
    return _ordered_skills(found)


def _split_skill_tokens(text: str) -> List[str]:
    if not text:
        return []
    parts = re.split(r"\s*[,|;•·]\s*", text)
    return [p.strip() for p in parts if p.strip()]


def _match_skills_in_token(token: str) -> List[str]:
    token = re.sub(r"^[\s\-•*]+|[\s,\.]+$", "", token.strip()).strip()
    if not token:
        return []
    direct = match_skill(token)
    if direct:
        return [direct]
    return _all_skills_in_text(token)


def _all_skills_in_text(text: str) -> List[str]:
    """Canonical skills referenced anywhere in text (longest-match first)."""
    if not text:
        return []
    result: List[str] = []
    seen = set()
    lower_full = " " + text.lower() + " "

    phrases = [
        key for key in _SKILL_LOOKUP
        if " " in key or "-" in key or "#" in key or "." in key or "/" in key or "+" in key
    ]
    phrases.sort(key=len, reverse=True)
    for phrase in phrases:
        pat = re.compile(r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])", re.I)
        if pat.search(lower_full):
            canon = _SKILL_LOOKUP[phrase]
            lk = canon.lower()
            if lk not in seen:
                seen.add(lk)
                result.append(canon)

    for tok in re.findall(r"[A-Za-z0-9+#./-]+", text):
        canon = match_skill(tok)
        if canon and canon.lower() not in seen:
            seen.add(canon.lower())
            result.append(canon)
    return result


def _extract_skills_loose(lines: List[Line]) -> List[str]:
    """Scan a set of lines for known skills (used inside project chunks and as
    a fallback when there is no dedicated skills section). Separator-based so a
    prose sentence that merely mentions a technology does not inflate skills."""
    found = set()
    for line in lines:
        s = line.text.strip().lstrip("-•* ")
        if not s or len(s) > 220:
            continue
        if looks_like_technology_line(s):
            for skill in _all_skills_in_text(s):
                found.add(skill)
            continue
        if len(s) > 60:
            continue  # long prose line, not a skill list
        for sep in [",", "|", "•", "·", "–", ";"]:
            if sep in s:
                for token in s.split(sep):
                    tok = _clean_skill(token)
                    if tok:
                        for skill in _all_skills_in_text(tok):
                            found.add(skill)
                break
    return _ordered_skills(found)


def extract_skills_from_text(text: str) -> List[str]:
    """Convenience: extract known skills from an arbitrary text string."""
    return _ordered_skills(set(_all_skills_in_text(text)))


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
# GPA/CGPA extraction, tolerant of surrounding punctuation like "8.98/10".
_GPA_RE = re.compile(
    r"(?i)\b(?:cgpa|gpa)\s*[:=\-]?\s*(\d{1}\.\d{1,2}(?:[/x]\s*10)?|\d{1,2}\.\d{1,2}(?:/10)?)"
)


def _extract_education(lines: List[Line]) -> List[Dict[str, Any]]:
    if not lines:
        return []
    stext = "\n".join(l.text for l in lines)
    looks_like_education = (
        bool(_find_degree(stext))
        or bool(_find_institution(stext))
        or bool(_YEAR_RE.search(stext))
        or any(tag in stext.lower() for tag in _COLLEGE_TAGS)
    )
    if not looks_like_education:
        return []

    chunks = split_entry_chunks(lines, is_project=False)
    entries: List[Dict[str, Any]] = []
    for chunk in chunks:
        entry = _parse_education_entry(chunk)
        if entry:
            entries.append(entry)
    return entries


def _parse_education_entry(chunk: List[Line]) -> Dict[str, Any]:
    raw = " ".join(l.text.strip() for l in chunk if l.text.strip())
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

    gpa = _find_gpa(text)
    if gpa:
        entry["gpa"] = gpa

    if not entry:
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


_INST_TAG_RE = re.compile(
    r"(?i)(University|College|Institute|Institution|School|Academy)"
)


def _find_institution(text: str) -> Optional[str]:
    # Peek: remove GPA, dates/years/months, degree labels and field of study so
    # the region around the college/university tag contains only the
    # institution's proper-noun name, then walk backward/forward over those
    # proper nouns to capture the full institution without pollution.
    m = _INST_TAG_RE.search(text)
    if not m:
        return None

    work = text
    work = _GPA_RE.sub(" ", work)
    work = _YEAR_RE.sub(" ", work)
    for label in _DEGREE_LABELS:
        work = re.sub(_build_degree_regex(label), " ", work, flags=re.IGNORECASE)
    work = _FIELD_RE.sub(" ", work)
    work = re.sub(r"\b(?:" + _MONTHS + r")\w*\b", " ", work, flags=re.IGNORECASE)
    work = re.sub(r"\s+", " ", work)

    m2 = _INST_TAG_RE.search(work)
    if not m2:
        return None
    tag_start = m2.start()
    tag_end = m2.end()

    tokens = list(re.finditer(r"[A-Za-z'’\.&]+", work))
    tag_idx = None
    for i, t in enumerate(tokens):
        if t.start() <= tag_start < t.end():
            tag_idx = i
            break
    if tag_idx is None:
        return None

    def is_proper(tok: str) -> bool:
        return bool(re.fullmatch(r"[A-Z][A-Za-z'’\-.]*", tok))

    def is_stop(tok: str) -> bool:
        return tok.lower() in {
            "expected", "present", "current", "now", "to",
            "cgpa", "gpa",
        }

    start = tag_idx
    while start - 1 >= 0:
        tok = tokens[start - 1].group()
        if is_stop(tok):
            break
        if is_proper(tok) or tok in {"of", "and", "&"}:
            start -= 1
        else:
            break

    end = tag_idx + 1
    while end < len(tokens):
        tok = tokens[end].group()
        if is_stop(tok):
            break
        if is_proper(tok) or tok in {"of", "and", "&"}:
            end += 1
        else:
            break

    phrase = work[tokens[start].start(): tokens[end - 1].end()]
    phrase = re.sub(r"\s+", " ", phrase).strip(" ,;:.-–\u2013\u2014")
    if not phrase:
        return None
    return _clean_institution(phrase) or None

    # Extend backward from the tag over the institution's proper names.
    bwd = work[:tag_start]
    bw_tokens = [t.strip() for t in re.findall(r"[A-Za-z'’\.&]+", bwd)]
    prefix = ""
    for tok in reversed(bw_tokens):
        if re.fullmatch(r"[A-Z][A-Za-z'’\-.]*|of|and|&", tok):
            prefix = tok + " " + prefix
        else:
            break

    inst = (prefix + work[tag_start:end]).strip()
    inst = re.sub(r"[,\s]+$", "", inst)
    if not inst:
        return None
    return _clean_institution(inst) or None


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
    m = re.search(r"(?i)\b(?:b\.?tech|b\.?e)\s+in\s+([A-Z][A-Za-z &.\-]+)", text)
    if m:
        return m.group(1).strip().rstrip(".,;")
    m = re.search(r"(?i)\b(?:major|speciali[sz]ation|speciali[sz]ing)[:]\s*([A-Z][A-Za-z &.\-]+)\b", text)
    if m:
        return m.group(1).strip().rstrip(".,;")
    return None


def _find_grad_year(text: str) -> Optional[str]:
    years = [y for y in _YEAR_RE.findall(text) if len(y) == 4]
    if not years:
        return None
    return sorted(set(years), key=int)[-1]


def _find_gpa(text: str) -> Optional[str]:
    m = _GPA_RE.search(text)
    if m:
        raw = m.group(1)
        # Normalise "8.98/10" -> "8.98/10"; strip units already captured.
        return raw.strip()
    return None


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


def _has_experience_evidence(lines: List[Line]) -> bool:
    if not lines:
        return False
    return bool(_DATE_TOKEN_RE.search("\n".join(l.text for l in lines))) or any(
        _find_role(l.text) for l in lines[:40]
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


def _split_header_bullets(chunk: List[Line]) -> Tuple[List[Line], List[Line]]:
    """Split a chunk into its header line(s) (role/company/dates/tools) and its
    bullets. Everything after the first bullet belongs to the bullets group,
    including wrapped continuation fragments that lack a bullet marker."""
    header: List[Line] = []
    bullets: List[Line] = []
    seen_bullet = False
    for line in chunk:
        s = line.text.strip()
        if not s:
            continue
        is_b = is_bullet_line(s) or bool(
            re.match(r"^[\u2013\u2014\-•·*]\s", s)
        )
        if seen_bullet:
            bullets.append(line)
        elif is_b:
            seen_bullet = True
            bullets.append(line)
        else:
            header.append(line)
    return header, bullets


def _extract_experience(section_lines: List[Line], all_lines: List[Line]) -> List[Dict[str, Any]]:
    lines = section_lines if section_lines else None
    if lines is None:
        if not _has_experience_evidence(all_lines):
            return []
        lines = all_lines[:60]
    if not lines:
        return []

    chunks = split_entry_chunks(lines, is_project=False)
    entries: List[Dict[str, Any]] = []
    for chunk in chunks:
        header, bullets = _split_header_bullets(chunk)
        header_text = " ".join(h.text.strip() for h in header if h.text.strip())
        entry: Dict[str, Any] = {}

        dates = _extract_dates_from_header(header_text)
        header_without_dates = _strip_dates(header_text)
        header_without_dates = re.sub(r"\s+", " ", header_without_dates).strip(" ,-–")

        role = _find_role(header_without_dates)

        tools_used: List[str] = []
        company_text = header_without_dates
        if role and role in company_text:
            company_text = company_text.replace(role, "", 1)
        # Extract "Tools Used:" / "Technologies:" tail so it does not pollute company.
        company_text, tools_used = _split_tools_from_company(company_text, header)
        company = _find_company(company_text, header)
        company = _clean_company(company, role, tools_used)

        if role:
            entry["job_title"] = role
        if company:
            entry["company"] = company
        if dates:
            entry["dates"] = dates
        if tools_used:
            entry["tools_used"] = tools_used

        desc_bullets = [b.text.strip() for b in bullets if b.text.strip()]
        non_tool_bullets = [
            re.sub(r"^[\u2013\u2014\-•·*]\s+", "", b) for b in desc_bullets
            if not _looks_like_tools_bullet(b)
        ]
        if non_tool_bullets:
            entry["description"] = " ".join(
                strip_bullet_marker(b) for b in non_tool_bullets if b.strip()
            )

        if entry:
            entries.append(entry)
    return entries


def _looks_like_tools_bullet(text: str) -> bool:
    s = strip_bullet_marker(text)
    return bool(_METADATA_LABEL_RE.match(s)) and len(s) <= 100


def _split_tools_from_company(company_text: str, header: List[Line]) -> Tuple[str, List[str]]:
    """Remove a metadata label tail (e.g. 'Tools Used: Python, Excel') from the
    company/role text and return the extracted tool list."""
    tools: List[str] = []
    cleaned = company_text
    for line in header:
        s = line.text.strip()
        m = _METADATA_LABEL_RE.match(s)
        if m and m.group(1).strip():
            tools.extend(_extract_skills_loose([Line(text=m.group(1))]))
            cleaned = cleaned.replace(s, " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,-–|")
    if not tools and company_text:
        # Metadata might be inline within the company_text itself.
        m = re.search(
            r"(?i)(?:tools?\s+used|technologies?\s*(?:used)?|tech\s+stack|technology\s+stack"
            r"|environment)\s*[:]\s*(.+)$",
            company_text,
        )
        if m:
            tools.extend(_extract_skills_loose([Line(text=m.group(1))]))
            cleaned = company_text[:m.start()].strip(" ,-–|")
    return cleaned, tools


def _clean_company(company: Optional[str], role: Optional[str], tools: List[str]) -> Optional[str]:
    if not company:
        return None
    c = company.strip().strip(" ,-–:;|")
    if role and c.lower().startswith(role.lower()):
        c = c[len(role):].strip(" ,-–:;|")
    # Strip location/arrangement hints like "(Remote)", "(On-site)", "(Hybrid)".
    c = re.sub(r"\s*\((?:remote|on[-\s]?site|hybrid|in[-\s]?person|office)\)\s*$", "", c, flags=re.I).strip()
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
        r"ML|Machine\s*Learning|Mobile|AI/ML|UI/UX|QA|Cloud|Security|Product|Web|Systems)?\s*"
        r"(?:Engineer|Developer|Manager|Analyst|Architect|Scientist|Designer|"
        r"Consultant|Lead|Intern|Administrator|Specialist|Coordinator|Director|Head))\b",
        text,
    )
    if match:
        role = match.group(1).strip()
        # Greedily consume a following role-qualifier token (e.g. "Developer
        # Intern", "Engineer Trainee") so the role is not truncated.
        rest = text[match.end():].strip()
        m2 = re.match(
            r"(?i)^(Intern|Trainee|Apprentice|Junior|Senior|Lead|Staff|Principal|"
            r"Head|Coordinator|Associate|Assistant)\b",
            rest,
        )
        if m2:
            role = role + " " + m2.group(1).capitalize()
        return role
    for seg in text.split("|"):
        for hint in _ROLE_HINTS:
            if hint in seg.lower():
                s = seg.strip().rstrip(".,;")
                if len(s) <= 80:
                    return s
    return None


def _find_company(text: str, header: Optional[List[Line]] = None) -> Optional[str]:
    m = re.search(r"(?i)\b(?:at|@)\s+([A-Z][A-Za-z0-9 .&'’-]{2,60})", text)
    if m:
        return m.group(1).strip().rstrip(".,;")
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


# =============================================================================
# Projects
# =============================================================================
def _extract_projects(lines: List[Line]) -> List[Dict[str, Any]]:
    if not lines:
        return []
    chunks = split_entry_chunks(lines, is_project=True)
    if not chunks:
        return []

    entries: List[Dict[str, Any]] = []
    for chunk in chunks:
        entry = _parse_project_chunk(chunk)
        if entry:
            entries.append(entry)
    return entries


def _title_and_tech(s: str) -> Tuple[Optional[str], List[str]]:
    """Split '<Title> | <technologies>' (if a pipe separator is present)."""
    if "|" in s:
        left, _, right = s.partition("|")
        title = left.strip(" ,-–|\u2013\u2014")
        techs = _all_skills_in_text(right)
        return (title or None, techs)
    return (s.strip(" ,-–|\u2013\u2014") or None, [])


def _parse_project_chunk(chunk: List[Line]) -> Dict[str, Any]:
    title: Optional[str] = None
    techs: List[str] = []
    date_lines: List[str] = []
    desc_lines: List[str] = []

    for line in chunk:
        s = line.text.strip()
        if not s or is_page_number(s):
            continue
        if looks_like_date_line(s):
            date_lines.append(s)
            continue
        if is_bullet_line(s):
            desc_lines.append(strip_bullet_marker(s))
            continue
        m = _METADATA_LABEL_RE.match(s)
        if m and len(s) <= 120:
            if m.group(1).strip():
                techs.extend(_all_skills_in_text(m.group(1)))
            continue
        if title is None:
            t, ttech = _title_and_tech(s)
            if t:
                title = t
                techs.extend(ttech)
            elif looks_like_technology_line(s):
                techs.extend(_all_skills_in_text(s))
            continue
        # After a title: a technology-only line contributes tech, else it is a
        # (non-bulleted) description line.
        if looks_like_technology_line(s):
            techs.extend(_all_skills_in_text(s))
        else:
            desc_lines.append(s)

    entry: Dict[str, Any] = {}
    if title:
        entry["name"] = title
    if date_lines:
        dates = _extract_dates_from_text(date_lines)
        if dates:
            entry["dates"] = dates
    uniq_techs = _ordered_skills(set(techs))
    if uniq_techs:
        entry["technologies"] = uniq_techs
    if desc_lines:
        entry["description"] = " ".join(desc_lines)[:1000]
    return entry


def _extract_dates_from_text(lines: List[str]) -> Optional[str]:
    joined = " ".join(lines)
    return _extract_dates_from_header(joined)


def _metadata_tech(chunk: List[Line]) -> List[str]:
    tools: List[str] = []
    for line in chunk:
        s = line.text.strip()
        m = _METADATA_LABEL_RE.match(s)
        if m and m.group(1).strip():
            tools.extend(_extract_skills_loose([Line(text=m.group(1))]))
    return tools


def _find_project_title(chunk: List[Line]) -> Tuple[Optional[str], str]:
    """Return (title, title_line_text). Handles '<Title> | techs' and date tails."""
    if not chunk:
        return None, ""
    for line in chunk[:2]:
        s = line.text.strip().lstrip("-•* ")
        if not s or is_bullet_line(s) or looks_like_date_line(s):
            continue
        if _find_role(s):
            continue
        if "|" in s and len(s) <= 90:
            left = s.partition("|")[0].strip()
            if left and len(left) <= 90:
                return left, s
        if looks_like_project_title(line, chunk[1] if len(chunk) > 1 else None):
            dateful = _strip_dates(s)
            base = dateful.strip(" ,-–|")
            if base and len(base) <= 90:
                return base, s
            return s, s
    return None, ""


def _find_project_description(lines: List[Line], title: Optional[str], techs: List[str]) -> Optional[str]:
    texts = []
    for line in lines:
        s = line.text.strip()
        if not s or is_page_number(s):
            continue
        bullet_s = strip_bullet_marker(s)
        if title and bullet_s.lower() == title.lower():
            continue
        if _METADATA_LABEL_RE.match(s) and len(s) <= 100:
            continue
        if looks_like_date_line(s):
            continue
        if techs:
            clean_re = re.sub(r"^[\s,.;|\-•*\u2013\u2014]+|[\s,.;|\-•*\u2013\u2014]+$", "", s)
            if _is_tech_only_line(clean_re):
                continue
        texts.append(bullet_s)
    if not texts:
        return None
    return " ".join(texts)[:1000]


def _is_tech_only_line(text: str) -> bool:
    if not text or len(text) > 160:
        return False
    tokens = [t.strip(" ,.;") for t in re.split(r"[,;|\s]+", text)]
    tokens = [t for t in tokens if t]
    if not tokens:
        return False
    matched = sum(1 for t in tokens if match_skill(t))
    return matched >= 1 and matched >= len(tokens) - 0


# =============================================================================
# Certifications (generalised)
# =============================================================================
_CERT_PATTERNS = [
    re.compile(r"(?i)\b[A-Za-z ]*AWS\s+Certified\s+[A-Za-z \-/]{2,40}"),
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
    # General: "Certificate in X", "NPTEL - Course", "<issuer>: <title> (<year>)"
    re.compile(r"(?i)\b(?:Certificate|Certification)\s+in\s+[A-Za-z .'&]{3,60}"),
    re.compile(r"(?i)\b[C][A-Za-z0-9 .&'’\-]{2,24}\s*[\u2013\u2014\-–]\s*[A-Za-z][A-Za-z0-9 .'&,()/%-]{3,60}"),
]

# Qualification/program names that appear next to an issuer/provider/score mark
# but are NOT certifications themselves. Used to reject false positives.
_NON_CERT_EXCLUDE = (
    "cgpa", "gpa", "percentage", "score", "scored", "rank", "ranked",
    "roll", "admission", "enrollment",
)


def _extract_certifications(lines: List[Line], all_lines: List[Line]) -> List[str]:
    if lines:
        # A dedicated certifications/awards section: each meaningful bullet line
        # is a certification entry. Clean it (strip score/rank/details after a
        # colon) and capture it directly. This is generic and does not require a
        # vendor name, so NPTEL/HackerRank/other courses are all captured.
        found: List[str] = []
        for ln in lines:
            text = _clean_cert_line(strip_bullet_marker(ln.text.strip()))
            if text and _cert_section_entry_ok(text):
                found.append(_cap_cert(_preserve_acronym_case(text)))
        return _dedupe_certs(found)

    source = all_lines[:80]
    if not source:
        return []
    found: List[str] = []
    for ln in source:
        text = strip_bullet_marker(ln.text.strip())
        if not text:
            continue
        for pat in _CERT_PATTERNS:
            for m in pat.finditer(text):
                cert = m.group(0).strip().rstrip(".,;:").strip()
                cert = re.sub(r"\((?:\d{4}|\d{4}[^)]*)\)\s*$", "", cert).strip(" ,:;")
                if cert and _cert_qualifies(cert):
                    found.append(_cap_cert(cert))
    return _dedupe_certs(found)


def _clean_cert_line(text: str) -> str:
    s = (text or "").strip()
    if not s:
        return ""
    # Drop trailing score/rank/issuer-detail segment after a colon.
    s = re.split(r":\s*", s, maxsplit=1)[0].strip()
    # Remove trailing "ranked ...", "scored ..." residues if any remain.
    s = re.sub(r"\s+(?:ranked|scored|with)\b.*$", "", s, flags=re.I).strip()
    s = re.sub(r"\s+", " ", s)
    return s.strip(" ,;:.-–\u2013\u2014")


def _preserve_acronym_case(text: str) -> str:
    # Re-capitalise common acronym tokens that the generic cleaning may degrade.
    words = text.split()
    out = []
    for w in words:
        u = w.upper()
        if u in {"AWS", "CCNA", "CCNP", "CCIE", "PMP", "C-DAC"} or u == "SQL":
            out.append(w.upper())
        elif u == "Ai":
            out.append("AI")
        else:
            out.append(w)
    return " ".join(out)


def _cert_section_entry_ok(text: str) -> bool:
    if not text or len(text) < 6:
        return False
    if _PAGE_NUMBER_RE.match(text):
        return False
    if re.fullmatch(r"[\d()\-– ]+", text):
        return False
    # Must contain alphabetic content (a real program/course name).
    if not re.search(r"[A-Za-z]{3,}", text):
        return False
    # Skip short all-lowercase continuation fragments (e.g. "nationwide")
    # that are merely the wrapped tail of the previous line.
    if len(text) < 20 and text == text.lower():
        return False
    return True


def _dedupe_certs(found: List[str]) -> List[str]:
    seen = set()
    unique = []
    for cert in found:
        key = cert.lower()
        if key not in seen:
            seen.add(key)
            unique.append(cert)
    return unique


def _cert_qualifies(cert: str) -> bool:
    low = cert.lower()
    if any(w in low for w in _NON_CERT_EXCLUDE):
        return False
    if len(cert) < 8:
        return False
    # A bare date/year line is not a cert.
    if re.fullmatch(r"[\d()\-– ]+", cert):
        return False
    return True


def _cap_cert(cert: str) -> str:
    words = cert.split()
    result = []
    for w in words:
        if w.upper() in {"AWS", "CCNA", "CCNP", "CCIE", "PMP", "PMP."}:
            result.append(w.upper())
        else:
            result.append(w)
    return " ".join(result)


# =============================================================================
# Top-level parsing entry points
# =============================================================================
def _parse_lines(lines: List[Line]) -> ParsedResumeData:
    result = ParsedResumeData()
    text = "\n".join(l.text for l in lines)

    result.basic_info = _extract_basic_info(text, [l.text for l in lines])

    sections = _split_into_sections(lines)
    prelude = sections.get("_prelude", [])

    summary_lines = sections.get("summary", [])
    result.summary = _extract_summary(summary_lines, prelude)

    result.skills = _extract_skills(sections.get("skills", []))
    if not result.skills:
        result.skills = _extract_skills_loose(lines)

    result.education = _extract_education(sections.get("education", []))
    result.experience = _extract_experience(sections.get("experience", []), lines)
    result.projects = _extract_projects(sections.get("projects", []))
    result.certifications = _extract_certifications(
        sections.get("certifications", []), lines
    )
    return result


def parse_resume(text: str) -> ParsedResumeData:
    """Deterministically parse structured resume data from raw text."""
    if not text:
        return ParsedResumeData()
    lines = _lines_from_text(text)
    return _parse_lines(lines)


def parse_resume_lines(lines: List[Line]) -> ParsedResumeData:
    """Parse from layout-aware lines (used by PDF pipeline)."""
    return _parse_lines(lines)


def parse_resume_file(file_path: str) -> Dict[str, Any]:
    """
    Full pipeline: extract text from a PDF (layout-aware), then parse.
    Returns a dict with the parsed structure. Raises on fatal errors; the
    caller is responsible for mapping the error into a parsing_status.
    """
    lines = extract_pdf_layout(file_path)
    parsed = parse_resume_lines(lines)
    return parsed.to_dict()


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
        lines = extract_pdf_layout(resume.file_path, min_chars=min_chars)
        text = "\n".join(l.text for l in lines)
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
        parsed = parse_resume_lines(lines)
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
