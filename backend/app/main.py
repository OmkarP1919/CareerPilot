from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.profile import router as profile_router
from app.api.resumes import router as resumes_router
from app.api.jobs import router as jobs_router
from app.api.match import router as match_router
from app.api.resume_analysis import router as resume_analysis_router
from app.api.resume_tailoring import router as resume_tailoring_router
from app.api.resume_tailoring import tailored_list_router
from app.api.resume_export import router as resume_export_router
from app.api.applications import router as applications_router
from app.api.analytics import router as analytics_router
from app.database.base import Base, engine

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="CareerPilot AI",
    description="Intelligent Job Matching & Application Management Platform",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(resumes_router)
app.include_router(jobs_router)
app.include_router(match_router)
app.include_router(resume_analysis_router)
app.include_router(resume_tailoring_router)
app.include_router(tailored_list_router)
app.include_router(resume_export_router)
app.include_router(applications_router)
app.include_router(analytics_router)


@app.get("/")
def root():
    return {"message": "CareerPilot AI API"}
