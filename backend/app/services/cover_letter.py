"""AI Cover Letter generation service (Phase 4A).

Produces a structured, grounded, job-specific cover letter for an existing
parsed resume and job. Backend foundation only - no frontend yet.

Grounding / anti-hallucination
------------------------------
The AI is instructed (and the output is constrained) to only use information
supported by the candidate's resume/profile. Job requirements are contextual
information only; a requirement is NEVER treated as evidence the candidate
possesses that attribute. Unsupported requirements are reported separately and
must not be represented as candidate facts. The deterministic Phase 2 Resume
Match analysis is reused as a grounding layer where available.

Privacy
-------
No unnecessary PII (email, phone, address, personal links) is sent to the
provider. We strip contact/identifying fields before building the prompt, and
we never log resume text, cover letter contents or prompts containing candidate
data.
"""

import logging
from copy import deepcopy
from typing import Any, Dict, List, Optional

from app.schemas.cover_letter import CoverLetterContent
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

# Fields that are personal identifiers / contact info and are never needed to
# write a cover letter. They are stripped from the resume before building the
# prompt so nothing sensitive is transmitted.
_CONTACT_KEYS = (
    "email",
    "phone",
    "mobile",
    "address",
    "linkedin",
    "github",
    "website",
    "url",
    "name",
)

# =============================================================================
# System instruction (anti-hallucination)
# =============================================================================
SYSTEM_INSTRUCTION = (
    "You are writing a professional cover letter for a specific job, on behalf "
    "of a candidate. You must use ONLY the candidate evidence supplied in the "
    "prompt. You must never invent, assume or infer qualifications.\n\n"
    "Hard rules:\n"
    "1. Only use supplied candidate evidence. Never invent experience, skills, "
    "education, achievements, companies, projects, certifications, metrics, "
    "dates or qualifications.\n"
    "2. Never convert a job requirement into candidate experience. A job "
    "requirement is NOT evidence that the candidate possesses that attribute.\n"
    "3. Never claim the candidate has a technology simply because the job asks "
    "for it.\n"
    "4. Never invent metrics, achievements, employment history, projects, "
    "education, certifications or years of experience.\n"
    "5. Never claim professional experience from a personal project. Never claim "
    "a project was used professionally unless the source explicitly says so.\n"
    "6. A job requirement that the candidate evidence does not support must be "
    "listed in 'unsupported_requirements' and must NOT appear as a candidate "
    "fact in the letter's body, opening, or supported points.\n"
    "7. If a requirement is unsupported, omit it rather than pretending the "
    "candidate has it.\n"
    "8. Keep the letter concise and professional (roughly 250-450 words). Do "
    "not force a specific word count if that makes the content unnatural.\n"
    "9. Use no invented numbers, percentages or impact claims.\n\n"
    "Structure the output using the provided JSON schema: greeting, opening, "
    "body_paragraphs (1-3 paragraphs), closing, signature, supported_points, "
    "unsupported_requirements and warnings."
)


def _trim(text: str, limit: int = MAX_RESUME_TEXT_CHARS) -> str:
    if text and len(text) > limit:
        logger.info("Truncating resume text to %d chars for AI request", limit)
        return text[:limit]
    return text or ""


def _scrub_candidate_text(text: str) -> str:
    """Remove email/phone/link-shaped tokens from free text before transmit."""
    if not text:
        return text
    import re

    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "[contact removed]", text)
    text = re.sub(r"\+?\d[\d\s().-]{7,}", "[phone removed]", text)
    text = re.sub(r"https?://\S+|www\.\S+", "[link removed]", text)
    return text


def _redact_resume(resume: dict) -> dict:
    """Return a copy of the resume with personal identifiers removed."""
    data = deepcopy(resume)
    data.pop("basic_info", None)
    data.pop("extracted_text", None)

    def scrub_mapping(item: Any) -> Any:
        if not isinstance(item, dict):
            return item
        cleaned = {}
        for key, value in item.items():
            if str(key).lower() in _CONTACT_KEYS:
                continue
            cleaned[key] = scrub_value(value)
        return cleaned

    def scrub_value(value: Any) -> Any:
        if isinstance(value, dict):
            return scrub_mapping(value)
        if isinstance(value, list):
            return [_scrub_candidate_text(str(v)) if isinstance(v, str) else scrub_value(v) for v in value]
        if isinstance(value, str):
            return _scrub_candidate_text(value)
        return value

    return scrub_value(data)


def _profile_context(profile: Optional[dict]) -> str:
    """Format candidate CareerPilot profile data as grounded evidence."""
    if not profile:
        return ""
    parts = []
    skills = [s for s in (profile.get("skills") or []) if s]
    if skills:
        parts.append(f"Profile skills: {', '.join(skills)}")
    projects = profile.get("projects") or []
    if projects:
        parts.append("Profile projects:")
        for p in projects:
            parts.append(f"- {p.get('name') or '?'}: {(p.get('description') or '')[:300]}")
    experiences = profile.get("experiences") or []
    if experiences:
        parts.append("Profile experience:")
        for e in experiences:
            parts.append(
                f"- {e.get('role') or '?'} at {e.get('company') or '?'} "
                f"({e.get('start_date') or ''} - {e.get('end_date') or ''})"
            )
    certifications = [c for c in (profile.get("certifications") or []) if c]
    if certifications:
        names = [c.get("name") or c if isinstance(c, dict) else str(c) for c in certifications]
        parts.append(f"Profile certifications: {', '.join(names)}")
    education = profile.get("education") or []
    if education:
        parts.append("Profile education:")
        for e in education:
            parts.append(f"- {e.get('degree') or '?'} at {e.get('college') or '?'}")
    return "\n".join(parts)


def _job_context(job: Any) -> str:
    title = getattr(job, "title", "") or ""
    company = getattr(job, "company", "") or ""
    description = getattr(job, "description", "") or ""
    required_skills = getattr(job, "required_skills", "") or ""
    return (
        "Job title: " + str(title) + "\n"
        "Company: " + str(company) + "\n"
        "Required skills (as stated by the job source): " + str(required_skills) + "\n"
        "Job description:\n" + str(description)
    )


def _analysis_grounding(analysis: Optional[dict]) -> str:
    """Format the deterministic Phase 2 Resume Match analysis as grounding."""
    if not analysis:
        return ""
    lines = [
        "Deterministic Resume Match analysis (grounding information):",
        "- Matched skills: " + (", ".join(analysis.get("matched_skills") or []) or "none"),
        "- Missing skills: " + (", ".join(analysis.get("missing_skills") or []) or "none"),
        "- Matched keywords: " + (", ".join(analysis.get("matched_keywords") or []) or "none"),
        "- Missing keywords: " + (", ".join(analysis.get("missing_keywords") or []) or "none"),
    ]
    relevant_projects = analysis.get("relevant_projects") or []
    if relevant_projects:
        names = ", ".join(p.get("name") or "?" for p in relevant_projects)
        lines.append("- Relevant projects: " + names)
    relevant_experience = analysis.get("relevant_experience") or []
    if relevant_experience:
        roles = ", ".join((e.get("job_title") or "?") for e in relevant_experience)
        lines.append("- Relevant experience: " + roles)
    lines.append(
        "- IMPORTANT: matched/missing lists describe what the deterministic tool "
        "detected. Missing skills are NOT evidence the candidate has them - never "
        "present missing skills as candidate facts."
    )
    return "\n".join(lines)


def _user_prompt(
    resume: dict,
    extracted_text: str,
    profile: Optional[dict],
    job: Any,
    analysis: Optional[dict],
) -> str:
    parts = [
        "Write a professional cover letter for the job below using ONLY the "
        "candidate evidence supplied. Return ONLY structured JSON conforming to "
        "the provided schema.",
        "",
        "=== JOB INFORMATION ===",
        _job_context(job),
        "",
        "=== CANDIDATE PROFILE (CareerPilot) ===",
        _profile_context(profile) or "(no additional profile data provided)",
        "",
        "=== CANDIDATE RESUME EVIDENCE (structured) ===",
        str(_redact_resume(resume)),
    ]
    if extracted_text:
        parts += [
            "",
            "=== CANDIDATE RESUME EVIDENCE (extracted text) ===",
            _trim(_scrub_candidate_text(extracted_text)),
        ]
    grounding = _analysis_grounding(analysis)
    if grounding:
        parts += ["", "=== RESUME-JOB MATCH EVIDENCE (grounding) ===", grounding]
    parts += [
        "",
        "=== TASK ===",
        "Write a concise, professional cover letter for this candidate. Highlight "
        "only the candidate facts supported by the supplied evidence. Where a job "
        "requirement is not supported by the candidate evidence, place it in "
        "'unsupported_requirements' and do NOT mention it as a candidate "
        "qualification anywhere in the letter. Keep it approximately 250-450 "
        "words. Return the structured JSON only.",
    ]
    return "\n".join(parts)


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
            "greeting": _str_prop(),
            "opening": _str_prop(),
            "body_paragraphs": _str_list_prop(),
            "closing": _str_prop(),
            "signature": _str_prop(),
            "supported_points": _str_list_prop(),
            "unsupported_requirements": _str_list_prop(),
            "warnings": _str_list_prop(),
        },
        "required": [
            "greeting",
            "opening",
            "body_paragraphs",
            "closing",
            "signature",
            "supported_points",
            "unsupported_requirements",
            "warnings",
        ],
        "additionalProperties": False,
    }


def _resolve_schema() -> Dict[str, Any]:
    return _schema_definition()


# =============================================================================
# Public API
# =============================================================================
class CoverLetterInput:
    """Everything the service needs to generate a cover letter."""

    def __init__(
        self,
        resume: dict,
        extracted_text: str,
        profile: Optional[dict],
        job: Any,
        analysis: Optional[dict] = None,
    ):
        self.resume = resume or {}
        self.extracted_text = extracted_text or ""
        self.profile = profile or {}
        self.job = job
        self.analysis = analysis


def _validate_content(data: Dict[str, Any]) -> CoverLetterContent:
    """Validate the AI's structured response with Pydantic.

    Raises AIInvalidResponseError (Pydantic validation failure) if it does not
    conform. The error is controlled and does not expose raw model internals.
    """
    try:
        return CoverLetterContent.model_validate(data)
    except Exception as exc:
        logger.warning("AI cover letter output failed Pydantic validation: %s", type(exc).__name__)
        raise AIInvalidResponseError(
            "The AI returned an invalid cover letter structure."
        ) from exc


def build_provider(settings: Any) -> BaseAIProvider:
    """Build the configured AI provider or raise AIProviderConfigurationError."""
    return get_provider(
        provider_name=getattr(settings, "AI_PROVIDER", ""),
        api_key=getattr(settings, "AI_API_KEY", ""),
        model=getattr(settings, "AI_MODEL", ""),
        base_url=getattr(settings, "AI_BASE_URL", ""),
    )


def call_cover_letter(
    provider: BaseAIProvider,
    cover_letter_input: CoverLetterInput,
    timeout_seconds: float,
) -> Dict[str, Any]:
    """Run the grounded generation call and return the validated structured dict.

    Raises AIProviderError subclasses on failure; never returns unvalidated data.
    """
    system_prompt = SYSTEM_INSTRUCTION
    user_prompt = _user_prompt(
        cover_letter_input.resume,
        cover_letter_input.extracted_text,
        cover_letter_input.profile,
        cover_letter_input.job,
        cover_letter_input.analysis,
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

    validated = _validate_content(raw)
    return validated.model_dump()


def assemble_content(content: Dict[str, Any]) -> str:
    """Assemble the structured content into the final cover letter text."""
    paragraphs = [content.get("greeting") or "", content.get("opening") or ""]
    for body in content.get("body_paragraphs") or []:
        paragraphs.append(body)
    paragraphs.append(content.get("closing") or "")
    paragraphs.append(content.get("signature") or "")
    return "\n\n".join(p for p in paragraphs if p and p.strip())


def summarise_for_response(content: Dict[str, Any]) -> Dict[str, Any]:
    """Return the validated structured content as a frontend-friendly dict."""
    return {
        "greeting": content.get("greeting", ""),
        "opening": content.get("opening", ""),
        "body_paragraphs": content.get("body_paragraphs", []),
        "closing": content.get("closing", ""),
        "signature": content.get("signature", ""),
        "supported_points": content.get("supported_points", []),
        "unsupported_requirements": content.get("unsupported_requirements", []),
        "warnings": content.get("warnings", []),
    }
