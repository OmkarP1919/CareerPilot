# CareerPilot AI

CareerPilot AI is an AI-powered career and job-search companion that helps you discover
relevant jobs, understand how well they fit your background, tailor your resume to each
opportunity, generate grounded cover letters, manage your application pipeline, and track
your career progress over time.

The platform combines multi-source job discovery with a deterministic, explainable matching
engine and structured, grounded AI assistance. It is designed for students and job seekers
who want a practical, transparent companion for the entire job-application journey.

---

## 🚀 Live Demo

**Public Beta:** [https://happy-meadow-00d50d800.5.azurestaticapps.net](https://happy-meadow-00d50d800.5.azurestaticapps.net)

The public beta frontend is hosted on **Azure Static Web Apps (Free tier)** and is backed by
the production FastAPI service. Sign in with email/password or Google to try it.

For technical verification, the backend exposes unauthenticated health probes:
`GET /healthz` (liveness) and `GET /health/readyz` (readiness, includes a database check).

---

## ✨ Features

### Authentication
- Firebase Authentication with email/password sign-up and Google Sign-In.
- Every backend request is authenticated with a Firebase ID token (Firebase Admin SDK) and
  scoped to the signed-in user.

### Profile
Build a searchable career profile around:
- **Education** — degree, institution, branch/CGPA, graduation year
- **Skills** — categorized technical skills
- **Projects** — with descriptions and technology tags
- **Experience** — roles, companies, and descriptions
- **Certifications** — professional certifications and issuers

### Resume Management
- PDF resume upload with a 10 MB per-file limit.
- Structured resume parsing (**Resume Parsing 2.0**) that extracts skills, projects,
  experience, education, and certifications into structured data.
- Review parsed resume insights, upload multiple versions, and designate a master resume.
- Tailored resume library and PDF/DOCX export.

### Job Discovery
- Multi-source job fetching with a common normalization, filtering, and sorting pipeline.
- Cross-source de-duplication so the same listing appears once.
- Recommended and personalized discovery, full-text search, and filters (employment type,
  experience level, work mode, posting recency).
- Saved searches that can be re-run and report newly seen results.
- Manual job tracking for opportunities you found yourself.

**Production source status (honest):**
- ✅ **Jobicy** — enabled in production (public API, no key required).
- ⏸️ **Adzuna** — integration present; production credentials are not currently configured.
- ⏸️ **Jooble** — integration present; production credentials are not currently configured.

### Job Matching
Every job is scored against your profile with a deterministic, explainable 5-factor
weighted algorithm:

| Factor | Weight | What is evaluated |
|---|:---:|---|
| **Skills** | **50%** | Overlap between your skills and required/inferred job skills |
| **Projects** | **20%** | Relevance of your projects to the job |
| **Experience** | **15%** | Alignment with your work history |
| **Role Alignment** | **10%** | Match between preferred roles and the job title |
| **Location** | **5%** | Preferred locations and remote suitability |

The result is a clear overall score plus per-factor sub-scores, a list of matched and missing
skills, and a plain-language explanation of *why* the job matches.

### Job Analysis
Resume-to-job fit analysis uses your parsed resume against a specific job to highlight where
your background aligns and where it does not — supporting informed "apply or skip" decisions.

### AI Resume Tailoring
- **Resume + job + profile + deterministic match evidence → structured AI tailoring.**
- Output is produced through structured-output validation and grounded in your actual
  resume/profile content (anti-hallucination rules: no invented skills, metrics, employers,
  or responsibilities; unsupported job keywords are reported rather than inserted).
- Tailored versions are saved and can be exported as PDF or DOCX.

### AI Cover Letters
- Structured, grounded cover-letter generation for a parsed resume + job.
- Requirements that your background does not support are reported separately and are never
  presented as yours.

### Application Tracking
- Track applications through the pipeline: **Saved → Applied → Interview → Offer** (plus **Rejected**).
- Timeline/event history, interview scheduling records, and per-application documents.
- Analytics and funnel visualization for your entire application pipeline.

### Security
- Firebase-authenticated backend APIs with ownership checks on every resource (jobs, resumes,
  tailored resumes, applications) to prevent IDOR-style cross-user access.
- HTTPS in production, strict CORS allowlist, trusted-host enforcement, security headers
  (including a Content-Security-Policy), request-body and upload limits, rate limiting, and
  strict exclusion of secrets from Git.

---

## 🧠 AI Architecture

AI features are built behind a small provider abstraction. The application depends on a
simple `BaseAIProvider` contract (one structured JSON response per call) rather than any
vendor SDK, so providers can be added or swapped without rewriting the tailoring, analysis,
or cover-letter services.

Current production configuration:

```
OpenAI-compatible provider abstraction
        ↓
     OpenRouter
        ↓
  openrouter/free
```

- The provider uses the Chat Completions interface over HTTPS with **structured-output**
  (`json_schema` strict mode, with a `json_object` fallback for endpoints that do not support it).
- Prompts and outputs are grounded in source resume/profile content; candidate PII is stripped
  before upstream requests.
- The current beta uses OpenRouter's **free** model route to keep the AI costing **$0
  out-of-pocket**.

> ### ⚠️ Transparency
> Free-tier availability and latency can vary. Requests may occasionally be slow, and the
> free route may be rate-limited or unavailable at peak times. CareerPilot does not promise
> unlimited AI usage.

---

## 🏗️ Architecture

```mermaid
flowchart TB
    U([User]) --> FE["React + Vite SPA"]
    FE --> SWA["Azure Static Web Apps (Free)"]
    SWA -->|"HTTPS + Firebase ID token"| API["FastAPI backend"]
    API --> FA["Firebase Authentication"]
    API --> ORM["SQLAlchemy"]
    ORM --> PG[("PostgreSQL")]
    API --> JOBS["Job source providers"]
    JOBS --> JOBICY["Jobicy"]
    API --> AI["AI provider abstraction"]
    AI --> ROUTER["OpenRouter"]
    ROUTER --> MODEL["openrouter/free"]
```

The frontend talks to the backend API at its origin root (routes such as `/jobs`,
`/resumes`, `/applications`, `/analytics` — there is no `/api` prefix).

---

## 🛠️ Tech Stack

**Backend**
- Python 3.12
- FastAPI 0.141
- SQLAlchemy 2.0 + psycopg2
- PostgreSQL (production) / SQLite (unit tests)
- PyMuPDF (resume text extraction), python-docx (export)
- Pydantic v2, httpx, python-dotenv, uvicorn, python-multipart
- Firebase Admin SDK 7.5

**Frontend**
- React 19 + Vite 8 (JavaScript/JSX)
- React Router 7
- Firebase client SDK
- Lucide React icons
- Oxlint for linting

**Authentication**
- Firebase Authentication (email/password + Google Sign-In)

**AI**
- OpenAI-compatible provider abstraction
- OpenRouter (`openrouter/free`)

**Infrastructure**
- Azure Static Web Apps (Free tier)
- Azure App Service (Basic B1, Linux)
- Azure Database for PostgreSQL Flexible Server
- GitHub Actions with OIDC federated deployment

---

## ☁️ Production Deployment

| Layer | Choice |
|---|---|
| **Frontend** | Azure Static Web Apps — Free tier |
| **Backend** | Azure App Service — Basic B1 Linux |
| **Database** | Azure Database for PostgreSQL Flexible Server — Standard_B1ms |
| **CI/CD** | GitHub Actions + OIDC |

Deployment runs from CI/CD (GitHub Actions) using OIDC federation rather than long-lived
credentials. Backend releases deploy a vendored Python artifact to App Service and are gated
by a health check that polls `/healthz` and `/health/readyz` after deploy.

---

## 🔄 CI/CD

GitHub Actions provides:

- **Backend CI** — Python 3.12, pinned dependencies, full `unittest` suite (SQLite), syntax check.
- **Frontend CI** — Node 22, contract tests, production build, lint.
- **Repository security** — whitespace/protected-file guard and an automated secret scan.
- **Deployment** — OIDC-based deployment to production with post-deploy health verification.

The CI pipeline is validation-only and never touches production resources. Workflow secrets
for deployment are stored in the repository settings and never appear in workflows or docs.

---

## 🧪 Testing

The current verified baseline:

- **AI-focused tests:** 83 passed
- **Full backend suite:** 810 passed, 9 skipped (skipped tests are the optional PostgreSQL
  round-trip tests, which self-skip when no PostgreSQL test URL is configured)
- **Production UAT:** completed
- **Production health verification:** completed
- **Backup/restore drill:** completed

---

## 🔐 Security & Reliability

- All backend APIs are authenticated; resources are scoped and ownership-checked per user
  (no cross-user access).
- HTTPS in production, with a strict CORS allowlist and TrustedHost enforcement.
- Security headers including Content-Security-Policy on responses.
- Request-body cap (16 MB) and per-file upload limit (10 MB).
- Rate limiting: global per-IP, per-authenticated-user, and a stricter tier for expensive
  routes (AI, discovery, uploads).
- Secrets (Firebase service accounts, API keys, connection strings) are excluded from Git and
  scanned for automatically.
- PostgreSQL credentials are rotated and the database is network-firewalled.

---

## 💾 Backup & Recovery

- **PostgreSQL:** Azure Flexible Server managed backups with point-in-time recovery (PITR) and
  a 7-day retention window.
- **Logical backups:** a verified `pg_dump`-based workflow (`python -m app.ops.backup
  create|list|verify|cleanup|restore`) with SHA-256 checksum sidecars; a restore drill has
  been completed successfully.

> **Note:** Resume/files uploaded by users are stored on the application host's filesystem and
> do **not** currently have a separate off-host backup system. They should not be assumed to
> carry the same recovery guarantees as the PostgreSQL database.

---

## ⚠️ Current Beta Limitations

CareerPilot is currently in **public beta**. These limitations are known and may be addressed
based on beta feedback:

1. **AI uses OpenRouter's free route.** Free-tier request limits apply, and latency can
   occasionally be high.
2. **Job discovery has only Jobicy enabled in production.** Adzuna and Jooble production
   credentials are not currently configured.
3. **Resume Parsing 2.0** has minor edge-case imperfections in Projects and Certifications
   extraction.
4. **Swagger/OpenAPI documentation is publicly accessible** on the backend.
5. **Monitoring is lightweight.** Health endpoints are available, but App Insights, advanced
   alerting, and deployment slots are not currently configured.

---

## 💰 Cost Philosophy

The current beta infrastructure is designed around a **$0 out-of-pocket** constraint:

- Azure free / low-cost, student-supported infrastructure.
- OpenRouter free AI route.
- No paid AI subscription is required for the current beta.

Operating costs depend on current provider allowances and usage — Azure free-tier and student
credit allowances, and free AI routes, are not guaranteed to last indefinitely.

---

## 🚀 Getting Started — Development

### Prerequisites
- Python 3.12+
- Node.js 22+
- A Firebase project (Authentication: email/password + Google Sign-In enabled)

### 1. Clone the repository
```bash
git clone https://github.com/OmkarP1919/CareerPilot.git
cd CareerPilot
```

### 2. Backend setup
```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

Populate `.env` with your local values (placeholders below). To initialize the database schema
(additive `create_all`, no migrations):

```bash
python -m app.database.init
```

Run the backend:

```bash
uvicorn app.main:app --reload
```

The API starts at `http://localhost:8000`.

### 3. Frontend setup
```bash
cd frontend
npm install
cp .env.example .env
```

Configure the public Firebase client values and `VITE_API_BASE_URL` in `frontend/.env`, then:

```bash
npm run dev
```

The dev server starts at `http://localhost:5173`.

### 4. Running tests
```bash
# Backend (from backend/)
python -m unittest discover -s tests -p "test_*.py"

# Frontend (from frontend/)
npm test
npm run lint
npm run build
```

### Environment configuration example (backend `.env`)
```env
AI_PROVIDER=openai
AI_BASE_URL=https://openrouter.ai/api/v1
AI_MODEL=openrouter/free
AI_API_KEY=<your-key>
AI_TIMEOUT_SECONDS=300
```

> **Security:** supply real credentials only in your local environment or as repository/deployment
> secrets. Never commit them. Firebase service-account JSON files (e.g. `firebase-service-account.json`)
> must remain gitignored.

---

## 🔧 Environment Variables

### Backend (`backend/.env`)

| Variable | Purpose | Required | Example |
|---|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | Production | `postgresql://user:password@localhost:5432/careerpilot` |
| `ENVIRONMENT` | `development` / `test` / `production` | Yes | `development` |
| `CORS_ORIGINS` | Allowed browser origins (comma-separated) | Production | `https://app.careerpilot.app` |
| `TRUSTED_HOSTS` | Allowed Host header values | Production | `api.careerpilot.app` |
| `FIREBASE_PROJECT_ID` | Firebase project for ID-token verification | Yes | `your-firebase-project-id` |
| `AI_PROVIDER` | AI provider name (`openai`) | For AI features | `openai` |
| `AI_API_KEY` | AI provider API key | For AI features | `<your-key>` |
| `AI_BASE_URL` | OpenAI-compatible endpoint | For OpenRouter | `https://openrouter.ai/api/v1` |
| `AI_MODEL` | Model identifier | For AI features | `openrouter/free` |
| `AI_TIMEOUT_SECONDS` | LLM request timeout | Optional | `60` |
| `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` / `ADZUNA_COUNTRY` | Adzuna credentials & region | For Adzuna | `your-adzuna-app-id` |
| `JOOBLE_API_KEY` | Jooble API key | For Jooble | `your-jooble-key` |
| `JOBICY_TIMEOUT_SECONDS` / `ADZUNA_TIMEOUT_SECONDS` / `JOOBLE_TIMEOUT_SECONDS` | Source request timeouts | Optional | `20` |
| `STORAGE_ROOT` | Upload directory root | Optional | `/var/lib/careerpilot/uploads` |
| `BACKUP_DIR` / `BACKUP_RETENTION_COUNT` | Logical backup location/retention | Optional | `/var/backups/careerpilot` / `30` |

### Frontend (`frontend/.env`)

| Variable | Purpose | Required | Example |
|---|---|---|---|
| `VITE_API_BASE_URL` | Backend API origin (no `/api` prefix) | Yes (production build fails if missing) | `http://localhost:8000` |
| `VITE_FIREBASE_API_KEY` | Firebase public client key | Yes | `your_api_key` |
| `VITE_FIREBASE_AUTH_DOMAIN` | Firebase auth domain | Yes | `your_project.firebaseapp.com` |
| `VITE_FIREBASE_PROJECT_ID` | Firebase project ID | Yes | `your_project_id` |
| `VITE_FIREBASE_STORAGE_BUCKET` | Firebase storage bucket | Yes | `your_project.appspot.com` |
| `VITE_FIREBASE_MESSAGING_SENDER_ID` | Firebase sender ID | Yes | `your_sender_id` |
| `VITE_FIREBASE_APP_ID` | Firebase app ID | Yes | `your_app_id` |

> Frontend `VITE_*` values are compiled into the static bundle and are public by design; never
> put backend secrets in them.

---

## 📁 Project Structure

```
CareerPilot/
├── .github/
│   └── workflows/            # CI + OIDC deployment workflows
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI route handlers
│   │   ├── core/             # config, middleware, security, rate limiting
│   │   ├── database/         # SQLAlchemy engine, schema init
│   │   ├── dependencies/     # auth dependencies
│   │   ├── models/           # SQLAlchemy models
│   │   ├── ops/              # backup/restore CLI
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   └── services/         # matching, discovery, AI, resume parsing
│   ├── tests/                # backend test suite
│   ├── docs/                 # backend operational documentation
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/       # UI components
│   │   ├── context/          # auth / theme / language state
│   │   ├── layouts/          # app + auth layout shells
│   │   ├── pages/            # route pages
│   │   ├── services/         # API client + Firebase config
│   │   ├── styles/           # CSS tokens and styles
│   │   └── utils/            # helpers
│   ├── tests/                # frontend contract tests
│   └── package.json
├── docs/                     # project-level documentation (CI/CD, etc.)
├── scripts/                  # repo guard + secret-scan tooling
└── README.md
```

---

## 🗺️ Roadmap

Planned future work, based on current beta limitations (no dates promised):

- Additional job providers (e.g. enable Adzuna/Jooble production credentials).
- Improved Resume Parsing 2.0 extraction (Projects, Certifications edge cases).
- Richer monitoring and alerting.
- Improved AI latency and reliability.
- Expanded career intelligence and analytics.
- Broader beta-driven UX improvements.

---

## 🤝 Contributing

Contributions are welcome:

1. Create a branch for your change.
2. Make focused changes.
3. Run the relevant tests (`npm test`, backend `unittest`, `npm run build`, `npm run lint`).
4. Never commit secrets or credentials.
5. Open a pull request against `main`.

CI runs backend tests, frontend contract tests/build/lint, and a repository security scan on
every pull request.

---

## 📄 License

License: Not currently specified.

---

## 📬 Feedback / Beta

CareerPilot is currently in **public beta**. Please report issues or suggestions via the
[GitHub Issues](https://github.com/OmkarP1919/CareerPilot/issues) tracker, including:

- Bugs
- Confusing UX
- Inaccurate job matches
- Resume parsing problems
- AI quality problems
- Slow AI responses
- Feature suggestions