# CareerPilot AI — Intelligent Career & Job Discovery Platform

CareerPilot AI is an intelligent career progression and job discovery platform designed to help students and job seekers manage their professional profile, discover tailored job opportunities, analyze job compatibility with explainable AI match scores, and track their entire application pipeline.

---

## Current Major Features

### 1. Authentication & Security
- **Firebase Authentication**: Robust Google Sign-In and Email/Password authentication.
- **JWT Verification**: Token-based backend authorization using Firebase Admin SDK.
- **Total User Data Isolation**: User match scores, profiles, and applications are strictly isolated per user account.

### 2. Comprehensive Career Profile Management
- **Personal & Contact Info**: Location preferences, portfolio links, and preferred job roles.
- **Education**: Degree, institution, branch, CGPA, and graduation year tracking.
- **Skills Matrix**: Categorized technical and soft skills.
- **Projects Showcase**: Project details, descriptions, and technology tags used for matching.
- **Work Experience**: Job titles, company history, and key contributions.
- **Certifications**: Professional certifications and issuing organizations.
- **Resume Hub**: PDF resume uploading, previewing, and master resume designation.

### 3. Job Discovery & Orchestration
- **Automated External Job Discovery**: Multi-source fetching from **Adzuna** and **Jobicy**.
- **Global Job Deduplication**: Idempotent global storage that reuses identical job postings across multiple users without creating duplicates.
- **Opportunity Browsing & Filtering**: Full-text search and filters for employment type and experience level.
- **Manual Job Tracking**: Ability to create custom opportunities for offline or direct applications.

### 4. 5-Factor Explainable Job Matching Engine
Every opportunity is evaluated against the candidate's career profile using a deterministic 5-factor weighted algorithm:

| Factor | Weight | Evaluation Criteria |
|---|:---:|---|
| **Skills Match** | **50%** | Overlap between user skills and required/inferred job skills |
| **Project Relevance** | **20%** | Semantic and technology overlap with candidate's past projects |
| **Experience Relevance**| **15%** | Alignment with past work history and responsibilities |
| **Role Alignment** | **10%** | Match between candidate's preferred roles and the job title |
| **Location Fit** | **5%** | Candidate location and preferred locations (with Remote bonus) |

- **Explainable Match Scores**: Detailed, human-readable breakdown explaining *why* a job matches and which skills are matched vs. missing.
- **Multi-Tier Recommendation Ranking**:
  1. Primary: Match Score (`overall_score` descending)
  2. Secondary: Role Alignment (`role_score` descending)
  3. Tertiary: Freshness (`posted_at` descending)

### 5. Application Pipeline & Analytics
- **Application Tracking**: Track status through *Saved*, *Preparing*, *Applied*, *Assessment*, *Interview*, *Offer*, *Rejected*, and *Withdrawn*.
- **Resume Tracking**: Associate specific resume versions with each application.
- **Career Analytics Dashboard**: Overview metrics, application funnel breakdown, and skill gap frequencies.

---

## Technology Stack

### Frontend
- **Framework**: React 18 with Vite
- **Routing**: React Router DOM
- **Icons**: Lucide React
- **Design System**: Calm Slate Modern Design System with HSL tokens and JetBrains Mono metrics
- **Authentication**: Firebase Client SDK

### Backend
- **Framework**: Python 3.10+ with FastAPI
- **ORM & Database**: SQLAlchemy with PostgreSQL (Supabase / Neon / Local PostgreSQL)
- **Data Validation**: Pydantic v2
- **Auth Verification**: Firebase Admin SDK
- **HTTP Client**: HTTPX with resilient connection timeouts

### External Job Sources
- **Adzuna API**: Structured job search across US, UK, Canada, Australia, Germany, and more.
- **Jobicy API**: Remote job opportunities across technical disciplines.

---

## System Architecture

```
                      ┌────────────────────────────┐
                      │    React Frontend (Vite)   │
                      └─────────────┬──────────────┘
                                    │ (Bearer Token)
                                    ▼
                      ┌────────────────────────────┐
                      │       FastAPI Backend      │
                      └─────────────┬──────────────┘
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          ▼                         ▼                         ▼
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│ Matching Engine  │      │  Job Discovery   │      │    PostgreSQL    │
│ (5-Factor Model) │      │ (Adzuna, Jobicy) │      │ (Users, Profile) │
└──────────────────┘      └──────────────────┘      └──────────────────┘
```

---

## Project Structure

```
CareerPilot/
├── frontend/
│   ├── src/
│   │   ├── components/       # UI Components (Navbar, Cards, Modals)
│   │   ├── pages/            # Workspace Pages (Home, Jobs, Applications, Profile)
│   │   ├── services/         # API client and Firebase integration
│   │   └── styles/           # CSS Tokens, layout, base, and component styles
│   ├── public/
│   ├── package.json
│   └── vite.config.js
│
├── backend/
│   ├── app/
│   │   ├── api/              # API Route Handlers (Auth, Profile, Jobs, Matching)
│   │   ├── core/             # Configuration and settings
│   │   ├── database/         # SQLAlchemy engine and session
│   │   ├── dependencies/     # Authentication dependencies
│   │   ├── models/           # Database models (User, Profile, Job, JobMatch, App)
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   └── services/         # Job discovery, source adapters, matching engine
│   ├── tests/                # Automated unit and integration test suite
│   └── requirements.txt
│
├── .gitignore
└── README.md
```

---

## Installation & Local Setup

### Prerequisites
- Node.js (v18+)
- Python (v3.10+)
- PostgreSQL Database
- Firebase Project with Google Authentication enabled

### 1. Frontend Setup
```bash
cd frontend
npm install
cp .env.example .env
# Configure your Firebase credentials in .env
npm run dev
```

### 2. Backend Setup
```bash
cd backend
python -m venv venv

# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Configure DATABASE_URL, FIREBASE_PROJECT_ID, and ADZUNA credentials in .env

uvicorn app.main:app --reload
```

---

## Environment Variables Configuration

### Backend (`backend/.env`)
```env
DATABASE_URL=postgresql://user:password@localhost:5432/careerpilot
FIREBASE_PROJECT_ID=your-firebase-project-id
ADZUNA_APP_ID=your-adzuna-app-id
ADZUNA_APP_KEY=your-adzuna-app-key
ADZUNA_COUNTRY=us
```

### Frontend (`frontend/.env`)
```env
VITE_FIREBASE_API_KEY=your_api_key
VITE_FIREBASE_AUTH_DOMAIN=your_project.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your_project_id
VITE_FIREBASE_STORAGE_BUCKET=your_project.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=your_sender_id
VITE_FIREBASE_APP_ID=your_app_id
VITE_API_BASE_URL=http://localhost:8000
```

---

## Current Development Status

The platform is actively in active development.

> **Note on Personalized Job Discovery**:
> The `POST /jobs/discover/personalized` endpoint is implemented and under active performance optimization with remote poolers. Stable job discovery via `POST /jobs/discover` and ranked recommendations via `GET /jobs/recommended` are fully functional and tested.

---

## License

This project is licensed under the MIT License.
