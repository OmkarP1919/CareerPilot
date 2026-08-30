"""AI Resume Tailoring service (Phase 3A).

This service produces a controlled, structured, job-specific tailoring of an
existing parsed resume. It is a backend foundation only - no PDF/DOCX
generation and no automatic application happen here.

Grounding / anti-hallucination
-----------------------------
The AI is instructed (and the output is constrained) to only use information
that is supported by the source resume/profile. Job-description keywords may be
incorporated only when the candidate has supporting evidence; otherwise they
are reported as "unsupported" rather than inserted. The deterministic Phase 2
Resume Match analysis is reused as a grounding layer where available.
"""

import logging
from copy import deepcopy
from typing import Any, Dict, List, Optional

from app.schemas.resume_tailoring import (
    TailoredResumeContent,
)
from app.services.ai_provider import (
    AIInvalidResponseError,
    AIProviderConfigurationError,
    AIProviderError,
    AIProviderUnavailableError,
    AIRateLimitError,
    AITimeoutError,
    BaseAIProvider,
    get_provider,
)

logger = logging.getLogger(__name__)

MAX_RESUME_TEXT_CHARS = 40000

# =============================================================================
# System instruction (anti-hallucination)
# =============================================================================
SYSTEM_INSTRUCTION = (
    "You are tailoring an existing resume for a specific job. You must use only "
    "information contained in the supplied resume/profile. Never invent "
    "qualifications, experience, technologies, achievements, metrics, employers, "
    "education, certifications, or responsibilities.\n\n"
    "Rules:\n"
    "1. Every factual claim in the tailored resume must be traceable to the source "
    "resume/profile.\n"
    "2. Job-description information can be used to identify relevant keywords and "
    "priorities.\n"
    "3. A job requirement must NOT be treated as evidence that the candidate "
    "possesses that skill.\n"
    "4. Missing skills must not be presented as existing skills.\n"
    "5. Do not fabricate metrics.\n"
    "6. Do not fabricate years of experience.\n"
    "7. Do not create new projects.\n"
    "8. Do not create new employment history.\n"
    "9. Preserve factual meaning.\n"
    "10. If a job keyword is relevant but unsupported by the resume, place it in "
    "'keywords_not_added' instead of inserting it.\n"
    "11. Do not change company names, degrees, dates, job titles, or certifications "
    "unless the source itself contains the information.\n"
    "12. Keep the tailored resume truthful and ATS-friendly.\n\n"
    "ATS tailoring guidance:\n"
    "- You may use terminology from the job description when supported by the "
    "candidate's actual experience.\n"
    "- Improve grammar, clarity and wording; reorder and prioritise relevant "
    "content; emphasise relevant skills/projects.\n"
    "- Do NOT keyword-stuff, repeat keywords unnaturally, add unsupported "
    "technologies, add fake accomplishments/numbers/business impact, or copy large "
    "portions of the job description.\n"
    "The output must be a professional resume, not a keyword dump, and must stay "
    "factually grounded in the source material."
)


def _trim(text: str, limit: int = MAX_RESUME_TEXT_CHARS) -> str:
    if text and len(text) > limit:
        logger.info("Truncating resume text to %d chars for AI request", limit)
        return text[:limit]
    return text or ""


def _job_context(job: Any) -> str:
    title = getattr(job, "title", "") or ""
    company = getattr(job, "company", "") or ""
    description = getattr(job, "description", "") or ""
    required_skills = getattr(job, "required_skills", "") or ""
    return (
        f"Job title: {title}\n"
        f"Company: {company}\n"
        f"Required skills (as stated by the job source): {required_skills}\n"
        f"Job description:\n{description}"
    )


def _analysis_grounding(analysis: Optional[dict]) -> str:
    """Format the deterministic Phase 2 Resume Match analysis as a grounding
    layer for the AI. Returns '' when no analysis is available."""
    if not analysis:
        return ""
    lines = [
        "Deterministic Resume Match analysis (grounding information):",
        f"- Matched skills: {', '.join(analysis.get('matched_skills') or []) or 'none'}",
        f"- Missing skills: {', '.join(analysis.get('missing_skills') or []) or 'none'}",
        f"- Matched keywords: {', '.join(analysis.get('matched_keywords') or []) or 'none'}",
        f"- Missing keywords: {', '.join(analysis.get('missing_keywords') or []) or 'none'}",
    ]
    relevant_projects = analysis.get("relevant_projects") or []
    if relevant_projects:
        names = ", ".join(p.get("name") or "?" for p in relevant_projects)
        lines.append(f"- Relevant projects: {names}")
    relevant_experience = analysis.get("relevant_experience") or []
    if relevant_experience:
        roles = ", ".join((e.get("job_title") or "?") for e in relevant_experience)
        lines.append(f"- Relevant experience: {roles}")
    suggestions = analysis.get("suggestions") or []
    if suggestions:
        lines.append("- Improvement suggestions (for guidance only):")
        for s in suggestions[:7]:
            lines.append(f"    * {s}")
    lines.append(
        "- IMPORTANT: matched/missing lists describe what the deterministic tool "
        "detected. Missing skills are NOT evidence the candidate has them - never "
        "insert missing skills as if the candidate possesses them."
    )
    return "\n".join(lines)


def _user_prompt(
    resume: dict,
    extracted_text: str,
    job: Any,
    analysis: Optional[dict],
) -> str:
    parts = [
        "Tailor the following resume for the job below. Return ONLY structured JSON "
        "conforming to the provided schema.",
        "",
        "=== JOB ===",
        _job_context(job),
        "",
        "=== SOURCE RESUME (structured) ===",
        str(_redact_basic_info(resume)),
    ]
    if extracted_text:
        parts += [
            "",
            "=== SOURCE RESUME (extracted text, for wording only) ===",
            _trim(extracted_text),
        ]
    grounding = _analysis_grounding(analysis)
    if grounding:
        parts += ["", "=== RESUME MATCH ANALYSIS (grounding) ===", grounding]
    parts += [
        "",
        "=== TASK ===",
        "Rewrite/refine the resume so it is sharper and more ATS-friendly for this "
        "job, using ONLY content supported by the source resume. Keep the result "
        "truthful. Where a job keyword is relevant but you cannot support it from the "
        "resume, put it in 'keywords_not_added'. Return the structured JSON only.",
    ]
    return "\n".join(parts)


def _redact_basic_info(resume: dict) -> dict:
    """Remove personal identifiers/contact details before sending to the AI.

    Basic info (phone, email, address, links) is not needed for tailoring and
    should not be transmitted. We keep name-free role/project content.
    """
    data = deepcopy(resume)
    data.pop("basic_info", None)
    data.pop("extracted_text", None)
    return data


# =============================================================================
# JSON schema generation (strict, OpenAI-compatible)
# =============================================================================
def _str_prop() -> Dict[str, Any]:
    return {"type": "string"}


def _str_list_prop() -> Dict[str, Any]:
    return {"type": "array", "items": _str_prop()}


def _schema_definition() -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "summary": {
                "type": "object",
                "properties": {
                    "original": _str_prop(),
                    "tailored": _str_prop(),
                },
                "required": ["original", "tailored"],
                "additionalProperties": False,
            },
            "skills": {
                "type": "object",
                "properties": {
                    "kept": _str_list_prop(),
                    "emphasized": _str_list_prop(),
                    "removed": _str_list_prop(),
                },
                "required": ["kept", "emphasized", "removed"],
                "additionalProperties": False,
            },
            "experience": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "original_title": _str_prop(),
                        "company": _str_prop(),
                        "original_bullets": _str_list_prop(),
                        "tailored_bullets": _str_list_prop(),
                        "changes": _str_list_prop(),
                    },
                    "required": [
                        "original_title",
                        "company",
                        "original_bullets",
                        "tailored_bullets",
                        "changes",
                    ],
                    "additionalProperties": False,
                },
            },
            "projects": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": _str_prop(),
                        "original_description": _str_prop(),
                        "tailored_description": _str_prop(),
                        "changes": _str_list_prop(),
                    },
                    "required": [
                        "name",
                        "original_description",
                        "tailored_description",
                        "changes",
                    ],
                    "additionalProperties": False,
                },
            },
            "education": _str_list_prop(),
            "certifications": _str_list_prop(),
            "keywords_added": _str_list_prop(),
            "keywords_not_added": _str_list_prop(),
            "overall_changes": _str_list_prop(),
            "warnings": _str_list_prop(),
        },
        "required": [
            "summary",
            "skills",
            "experience",
            "projects",
            "education",
            "certifications",
            "keywords_added",
            "keywords_not_added",
            "overall_changes",
            "warnings",
        ],
        "additionalProperties": False,
    }


def _resolve_schema() -> Dict[str, Any]:
    """Return the JSON schema for the structured output and a sample instance
    so the provider can constrain structured output."""
    return _schema_definition()


# =============================================================================
# Public API
# =============================================================================
class TailoringInput:
    """Everything the service needs to tailor a resume."""

    def __init__(
        self,
        resume: dict,
        extracted_text: str,
        job: Any,
        analysis: Optional[dict] = None,
    ):
        self.resume = resume or {}
        self.extracted_text = extracted_text or ""
        self.job = job
        self.analysis = analysis


def _validate_tailored_content(data: Dict[str, Any]) -> TailoredResumeContent:
    """Validate the AI's structured response with Pydantic.

    Raises AIInvalidResponseError (Pydantic validation failure) if it does not
    conform. The error is controlled and does not expose raw model internals.
    """
    try:
        return TailoredResumeContent.model_validate(data)
    except Exception as exc:
        logger.warning("AI tailored output failed Pydantic validation: %s", type(exc).__name__)
        raise AIInvalidResponseError(
            "The AI returned an invalid tailoring structure."
        ) from exc


def build_provider(settings: Any) -> BaseAIProvider:
    """Build the configured AI provider or raise AIProviderConfigurationError."""
    return get_provider(
        provider_name=getattr(settings, "AI_PROVIDER", ""),
        api_key=getattr(settings, "AI_API_KEY", ""),
        model=getattr(settings, "AI_MODEL", ""),
        base_url=getattr(settings, "AI_BASE_URL", ""),
    )


def call_tailoring(
    provider: BaseAIProvider,
    tailoring_input: TailoringInput,
    timeout_seconds: float,
) -> Dict[str, Any]:
    """Run the grounded tailoring call and return the validated structured dict.

    Raises AIProviderError subclasses on failure; never returns unvalidated data.
    """
    system_prompt = SYSTEM_INSTRUCTION
    user_prompt = _user_prompt(
        tailoring_input.resume,
        tailoring_input.extracted_text,
        tailoring_input.job,
        tailoring_input.analysis,
    )
    schema = _resolve_schema()

    raw = provider.generate_structured(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema=schema,
        timeout_seconds=timeout_seconds,
    )
    if not isinstance(raw, dict):
        raise AIInvalidResponseError("The AI returned a non-object response.")

    validated = _validate_tailored_content(raw)
    return validated.model_dump()


def summarise_for_response(content: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten the validated structured content into the frontend-facing view."""
    return {
        "summary": (content.get("summary") or {}).get("tailored", ""),
        "skills": (content.get("skills") or {}).get("kept", []),
        "emphasized_skills": (content.get("skills") or {}).get("emphasized", []),
        "experience": content.get("experience", []),
        "projects": content.get("projects", []),
        "education": content.get("education", []),
        "certifications": content.get("certifications", []),
    }
