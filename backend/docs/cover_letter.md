# AI Cover Letter Generation (Phase 4A) — Backend

This document describes the backend-only Cover Letter generator added in
Phase 4A. The frontend will be integrated in a later phase. Nothing here
modifies the profile matching engine, resume parsing, resume match, resume
tailoring, or export behavior.

## Architecture

Three-tier structure mirroring the existing Resume Tailoring feature:

- `app/models/cover_letter.py` — `CoverLetter` ORM model
- `app/schemas/cover_letter.py` — Pydantic request/response + structured AI contract
- `app/services/cover_letter.py` — grounding + prompt construction + validation
- `app/api/cover_letter.py` — HTTP routers
- `app/models/__init__.py`, `app/schemas/__init__.py` — registrations
- `app/main.py` — router registration

The AI provider abstraction (`app/services/ai_provider/`) is reused as-is. There
is **no** second OpenAI client.

## Data flow

1. Client calls `POST /jobs/{job_id}/cover-letter` with `{ "resume_id", "regenerate" }`.
2. The job and the user's own resume are looked up; ownership is enforced.
3. The resume's parsing state is validated (pending/failed/empty → controlled error).
4. A deterministic Phase 2 **Resume Match** analysis is reused if present, or
   generated via `resume_job_analysis.analyze_resume_against_job` and persisted.
   The Resume Match algorithm is **not** duplicated.
5. A privacy-aware candidate profile view is built.
6. The AI provider is built from `AI_PROVIDER` / `AI_API_KEY` / `AI_MODEL` /
   `AI_BASE_URL` / `AI_TIMEOUT_SECONDS`. If not configured → 503.
7. A grounded prompt is constructed (sections below) and sent via
   `provider.generate_structured()`.
8. The structured response is validated with Pydantic. Invalid output → 502 and
   nothing is persisted.
9. On success the result is persisted (or the existing row is updated on
   regenerate) and returned. The original resume is never modified.

## Grounding / anti-hallucination strategy

The prompt presents **four clearly separated context sections**:

- `CANDIDATE PROFILE` (CareerPilot profile data)
- `CANDIDATE RESUME EVIDENCE` (parsed resume + extracted text)
- `JOB INFORMATION` (title/company/description/required skills)
- `RESUME-JOB MATCH EVIDENCE` (deterministic Resume Match grounding)

The system instruction (in `SYSTEM_INSTRUCTION`) explicitly forbids:
inventing qualifications, converting a job requirement into candidate
experience, claiming a technology because the job asks for it, inventing
metrics/achievements/employment/projects/education/certifications/years, and
claiming professional experience from personal projects. Unsupported job
requirements must be placed in `unsupported_requirements` and never appear as
candidate facts.

After generation, output is validated by Pydantic and rejected if malformed;
it is not persisted until it validates.

## Endpoints

| Method | Path | Notes |
|---|---|---|
| POST | `/jobs/{job_id}/cover-letter` | Generate (or reuse existing unless `regenerate=true`) |
| GET | `/jobs/{job_id}/cover-letter/{resume_id}` | Retrieve the user's existing letter |
| GET | `/cover-letters` | List the authenticated user's letters |
| DELETE | `/cover-letters/{id}` | Delete one of the user's letters |

Ownership is enforced on every read/write path. Cross-user access returns
`404` (not `403`) so the existence of a resource is never disclosed.

## Regeneration semantics

`regenerate=false` (default): if a CoverLetter already exists for the same
(user, resume, job), it is reused and no AI call is made.

`regenerate=true`: an AI call is made and the existing row is updated in place,
so repeated normal requests never create uncontrolled duplicate records.

## Security

- Everything is scoped to the authenticated Firebase user (`user_id`).
- **No API keys** stored in the model or logs.
- **No raw prompts** stored.
- **No unnecessary PII** transmitted: `basic_info` (name/email/phone/address/
  links) is removed before the prompt, and email/phone/URL-shaped tokens in the
  extracted text are redacted.
- Resume text, cover letter contents, prompts with candidate data and API keys
  are never logged.

## Error handling

Controlled, human-readable errors only. No tracebacks, internals, API keys or
raw provider responses are returned.

| Condition | Status |
|---|---|
| Resume not found / belongs to another user | 404 |
| Job not found | 404 |
| Resume parsing pending | 409 |
| Resume parsing failed / no usable data | 422 |
| Job has no description/required skills | 422 |
| AI not configured | 503 |
| AI timeout | 504 |
| AI provider unavailable | 503 |
| Rate limit | 429 |
| Invalid / malformed AI output | 502 |
| Unexpected error | 500 |

## Anti-hallucination validation

1. Provider returns a JSON object.
2. Pydantic validates required fields and types (`CoverLetterContent`).
3. Malformed output is rejected and **not** persisted.
4. Unsupported requirements must remain in `unsupported_requirements` and not
   appear as candidate facts in the letter body.

No unreliable keyword blacklist is used.

## Tests

`tests/test_cover_letter.py` covers generation, validation, persistence,
reuse, regeneration, ownership isolation, cross-user access, missing
resume/job, parsing states, AI-not-configured, timeout, provider failure,
malformed output, no-usable-data, original-resume-unchanged, unsupported
requirement handling, privacy of contact info, and existing-engine integrity.
Providers are mocked; no real API key is required.
