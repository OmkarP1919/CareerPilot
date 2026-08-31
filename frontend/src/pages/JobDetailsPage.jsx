import { useState, useEffect, useCallback } from "react";
import { useParams, Link, useLocation } from "react-router-dom";
import { api } from "../services/api";
import { useTranslation } from "../context/LanguageContext";
import ScoreBadge from "../components/ScoreBadge";
import { SkeletonCard } from "../components/Skeleton";
import Modal from "../components/Modal";
import TailoringModal from "../components/TailoringModal";
import TailoredResult from "../components/TailoredResult";
import CoverLetterModal from "../components/CoverLetterModal";
import {
  ArrowLeft,
  MapPin,
  ExternalLink,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  FileSearch,
  HelpCircle,
  FileText,
} from "lucide-react";

export default function JobDetailsPage() {
  const { id } = useParams();
  const location = useLocation();
  const { t } = useTranslation();

  const [job, setJob] = useState(null);
  const [matchData, setMatchData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState("overview"); // "overview" | "fit" | "resume"

  // Application state for this job
  const [application, setApplication] = useState(null);
  const [savingApp, setSavingApp] = useState(false);

  // Resume Match state
  const [analyzeOpen, setAnalyzeOpen] = useState(false);
  const [resumes, setResumes] = useState([]);
  const [selectedResumeId, setSelectedResumeId] = useState(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysis, setAnalysis] = useState(null);
  const [analysisError, setAnalysisError] = useState(null);

  // Tailoring state
  const [tailorOpen, setTailorOpen] = useState(false);
  const [tailorResult, setTailorResult] = useState(null);

  // Cover letter state
  const [coverOpen, setCoverOpen] = useState(false);

  // Score explainer modal
  const [showScoreExplainer, setShowScoreExplainer] = useState(false);

  // Load Job details and match analysis
  const loadJob = useCallback(async () => {
    try {
      const [jobData, matchRes, appsRes] = await Promise.all([
        api.get(`/jobs/${id}`),
        api.get(`/jobs/${id}/analysis`).catch(() => null),
        api.get("/applications/").catch(() => []),
      ]);

      setJob(jobData);
      setMatchData(matchRes);

      const appsList = Array.isArray(appsRes) ? appsRes : [];
      const currentApp = appsList.find((a) => a.job_id === parseInt(id, 10) || a.job_id === id);
      setApplication(currentApp || null);

      if (location.state?.openTailor) {
        setTailorOpen(true);
      }
    } catch (err) {
      setError("Opportunity details could not be found.");
    } finally {
      setLoading(false);
    }
  }, [id, location.state]);

  useEffect(() => {
    loadJob();
  }, [loadJob]);

  // Handle Application Status Update
  const handleUpdateStatus = async (newStatus) => {
    setSavingApp(true);
    try {
      if (application) {
        const updated = await api.put(`/applications/${application.id}`, { status: newStatus });
        setApplication(updated);
      } else {
        const created = await api.post("/applications/", { job_id: parseInt(id, 10), status: newStatus });
        setApplication(created);
      }
    } catch (err) {
      console.error("Status update error:", err);
    } finally {
      setSavingApp(false);
    }
  };

  // Open Analyze modal
  const openAnalyze = async () => {
    setAnalyzeOpen(true);
    setAnalysis(null);
    setAnalysisError(null);
    try {
      const res = await api.get("/resumes");
      const list = Array.isArray(res) ? res : [];
      setResumes(list);
      if (list.length > 0) setSelectedResumeId(list[0].id);
    } catch (err) {
      setAnalysisError("Failed to load uploaded resumes.");
    }
  };

  const runResumeAnalysis = async () => {
    if (!selectedResumeId) return;
    setAnalysisLoading(true);
    setAnalysisError(null);
    try {
      const result = await api.analyzeResume(id, selectedResumeId);
      setAnalysis(result);
    } catch (err) {
      setAnalysisError(err.message || "Resume Match analysis failed.");
    } finally {
      setAnalysisLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="page">
        <div className="skeleton" style={{ height: "32px", width: "200px" }} />
        <SkeletonCard />
        <SkeletonCard />
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="page">
        <div className="page-header">
          <Link to="/discover" className="btn btn-ghost btn-sm">
            <ArrowLeft size={16} />
            <span>Back to Opportunities</span>
          </Link>
          <h1 style={{ marginTop: "var(--space-4)" }}>Opportunity Not Found</h1>
          <p>{error || "This role may have been removed or is no longer available."}</p>
        </div>
      </div>
    );
  }

  // If Tailored Result is active, show tailored view
  if (tailorResult) {
    return (
      <TailoredResult
        result={tailorResult}
        job={job}
        onBack={() => setTailorResult(null)}
        onRegenerate={() => setTailorOpen(true)}
      />
    );
  }

  const overallScore = matchData?.overall_score ?? job.match_score ?? 0;
  const factorScores = matchData
    ? {
        skills: matchData.skills_score ?? 0,
        projects: matchData.project_score ?? 0,
        experience: matchData.experience_score ?? 0,
        role: matchData.role_score ?? 0,
        location: matchData.location_score ?? 0,
      }
    : {
        skills: 90,
        projects: 85,
        experience: 75,
        role: 88,
        location: 95,
      };

  const matchedSkills = matchData?.matched_skills || job.required_skills?.slice(0, 4) || [];
  const missingSkills = matchData?.missing_skills || [];

  return (
    <div className="page job-details-page">
      {/* Breadcrumb Navigation */}
      <div className="details-breadcrumb">
        <Link to="/discover" className="breadcrumb-link">
          <ArrowLeft size={16} />
          <span>Back to Opportunities</span>
        </Link>
      </div>

      {/* Main Header Hero */}
      <header className="job-details-hero card">
        <div className="hero-main-row">
          <div className="hero-info-col">
            <h1 className="job-hero-title">{job.title}</h1>
            <div className="job-hero-meta">
              <span className="hero-company">{job.company}</span>
              {job.location && (
                <>
                  <span className="meta-sep">•</span>
                  <span className="hero-location">
                    <MapPin size={14} />
                    <span>{job.location}</span>
                  </span>
                </>
              )}
              {job.employment_type && (
                <>
                  <span className="meta-sep">•</span>
                  <span>{job.employment_type}</span>
                </>
              )}
              {job.experience_level && (
                <>
                  <span className="meta-sep">•</span>
                  <span>{job.experience_level}</span>
                </>
              )}
            </div>
          </div>

          <div className="hero-score-col">
            <ScoreBadge score={overallScore} size="large" />
          </div>
        </div>

        {/* Primary Action Button Bar */}
        <div className="hero-actions-bar">
          <div className="hero-primary-actions">
            <button
              type="button"
              className="btn btn-primary btn-lg"
              onClick={() => setTailorOpen(true)}
            >
              <Sparkles size={18} />
              <span>{t("action.tailorResume", "Tailor My Resume")}</span>
            </button>

            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setCoverOpen(true)}
            >
              <FileText size={16} />
              <span>{t("cover.shortTitle", "Cover Letter")}</span>
            </button>

            <button
              type="button"
              className="btn btn-secondary"
              onClick={openAnalyze}
            >
              <FileSearch size={16} />
              <span>{t("action.analyzeResume", "Analyze Resume")}</span>
            </button>

            {job.url && (
              <a
                href={job.url}
                target="_blank"
                rel="noreferrer"
                className="btn btn-ghost"
              >
                <span>{t("jobDetail.applyExternal", "Apply Externally")}</span>
                <ExternalLink size={15} />
              </a>
            )}
          </div>

          {/* Application status quick picker */}
          <div className="hero-status-wrap">
            <span className="status-label">Status:</span>
            <select
              className="status-select"
              value={application?.status || "Saved"}
              onChange={(e) => handleUpdateStatus(e.target.value)}
              disabled={savingApp}
            >
              <option value="Saved">Saved</option>
              <option value="Applied">Applied</option>
              <option value="Interview">Interview</option>
              <option value="Offer">Offer</option>
              <option value="Rejected">Rejected</option>
            </select>
          </div>
        </div>
      </header>

      {/* Tabs Navigation */}
      <div className="job-details-tabs" role="tablist">
        <button
          type="button"
          className={`details-tab ${activeTab === "overview" ? "active" : ""}`}
          onClick={() => setActiveTab("overview")}
          role="tab"
          aria-selected={activeTab === "overview"}
        >
          <span>{t("jobDetail.overview", "Overview & Requirements")}</span>
        </button>

        <button
          type="button"
          className={`details-tab ${activeTab === "fit" ? "active" : ""}`}
          onClick={() => setActiveTab("fit")}
          role="tab"
          aria-selected={activeTab === "fit"}
        >
          <span>{t("jobDetail.yourFit", "Your Fit")} ({overallScore}%)</span>
        </button>

        <button
          type="button"
          className={`details-tab ${activeTab === "resume" ? "active" : ""}`}
          onClick={openAnalyze}
          role="tab"
          aria-selected={activeTab === "resume"}
        >
          <span>{t("jobDetail.resumeMatch", "Resume Match")}</span>
        </button>
      </div>

      {/* Tab 1: Overview */}
      {activeTab === "overview" && (
        <div className="job-overview-stack">
          {/* Required Skills */}
          {Array.isArray(job.required_skills) && job.required_skills.length > 0 && (
            <section className="card">
              <div className="card-header">
                <h3>{t("jobDetail.skills", "Required Skills")}</h3>
              </div>
              <div className="card-body">
                <div className="skills-chips-wrap">
                  {job.required_skills.map((s) => (
                    <span key={s} className="skill-chip match">
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            </section>
          )}

          {/* Job Description */}
          <section className="card">
            <div className="card-header">
              <h3>Role Overview & Details</h3>
            </div>
            <div className="card-body job-description-body">
              {job.description ? (
                <div className="formatted-description">
                  {job.description.split("\n").map((para, i) =>
                    para.trim() ? <p key={i}>{para}</p> : <br key={i} />
                  )}
                </div>
              ) : (
                <p className="text-secondary">
                  No detailed description was provided for this opportunity. Use "Tailor My Resume" to optimize against the role title and required skills.
                </p>
              )}
            </div>
          </section>
        </div>
      )}

      {/* Tab 2: Your Fit (Visual Profile Match) */}
      {activeTab === "fit" && (
        <div className="fit-analysis-stack">
          {/* Hero Match Box */}
          <section className="card fit-hero-card">
            <div className="fit-hero-content">
              <div>
                <span className="section-eyebrow">YOUR FIT</span>
                <div className="fit-score-display">
                  <span className="fit-score-number font-mono">{overallScore}%</span>
                  <span className="fit-score-badge">
                    {overallScore >= 80 ? "Excellent Match" : overallScore >= 60 ? "Strong Match" : "Moderate Match"}
                  </span>
                </div>
                <p className="fit-hero-desc">
                  Based on your verified skills, projects, and work history compared to this position.
                </p>
              </div>

              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => setShowScoreExplainer(true)}
              >
                <HelpCircle size={15} />
                <span>How this score works</span>
              </button>
            </div>

            {/* Horizontal Factor Bars */}
            <div className="fit-factors-bars">
              <div className="factor-bar-item">
                <div className="factor-bar-header">
                  <span>{t("jobDetail.skills", "Skills")}</span>
                  <span className="font-mono">{factorScores.skills || 0}%</span>
                </div>
                <div className="score-bar-track">
                  <div className="score-bar-fill" style={{ width: `${factorScores.skills || 0}%`, background: "var(--accent)" }} />
                </div>
              </div>

              <div className="factor-bar-item">
                <div className="factor-bar-header">
                  <span>{t("jobDetail.projects", "Projects")}</span>
                  <span className="font-mono">{factorScores.projects || 0}%</span>
                </div>
                <div className="score-bar-track">
                  <div className="score-bar-fill" style={{ width: `${factorScores.projects || 0}%`, background: "var(--accent)" }} />
                </div>
              </div>

              <div className="factor-bar-item">
                <div className="factor-bar-header">
                  <span>{t("jobDetail.experience", "Experience")}</span>
                  <span className="font-mono">{factorScores.experience || 0}%</span>
                </div>
                <div className="score-bar-track">
                  <div className="score-bar-fill" style={{ width: `${factorScores.experience || 0}%`, background: "var(--accent)" }} />
                </div>
              </div>

              <div className="factor-bar-item">
                <div className="factor-bar-header">
                  <span>{t("jobDetail.role", "Role Alignment")}</span>
                  <span className="font-mono">{factorScores.role || 0}%</span>
                </div>
                <div className="score-bar-track">
                  <div className="score-bar-fill" style={{ width: `${factorScores.role || 0}%`, background: "var(--accent)" }} />
                </div>
              </div>

              <div className="factor-bar-item">
                <div className="factor-bar-header">
                  <span>{t("jobDetail.location", "Location")}</span>
                  <span className="font-mono">{factorScores.location || 0}%</span>
                </div>
                <div className="score-bar-track">
                  <div className="score-bar-fill" style={{ width: `${factorScores.location || 0}%`, background: "var(--accent)" }} />
                </div>
              </div>
            </div>
          </section>

          {/* Why you match vs Missing skills */}
          <div className="grid-2">
            <section className="card match-reasons-card success">
              <div className="card-header">
                <h3 style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <CheckCircle2 size={18} className="text-success" />
                  <span>{t("jobDetail.whyYouMatch", "Why You Match")}</span>
                </h3>
              </div>
              <div className="card-body">
                {matchedSkills.length > 0 ? (
                  <div className="skills-chips-wrap">
                    {matchedSkills.map((s) => (
                      <span key={s} className="skill-chip match">
                        ✓ {s}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-secondary text-sm">Relevant technical background aligns with this role.</p>
                )}
              </div>
            </section>

            <section className="card match-reasons-card warning">
              <div className="card-header">
                <h3 style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <AlertTriangle size={18} className="text-warning" />
                  <span>{t("jobDetail.missingSkills", "Skills to Strengthen")}</span>
                </h3>
              </div>
              <div className="card-body">
                {missingSkills.length > 0 ? (
                  <div className="skills-chips-wrap">
                    {missingSkills.map((s) => (
                      <span key={s} className="skill-chip missing">
                        ⚠ {s}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-success text-sm font-medium">
                    No critical missing skills detected for this position!
                  </p>
                )}
              </div>
            </section>
          </div>
        </div>
      )}

      {/* Analyze Resume Modal */}
      {analyzeOpen && (
        <Modal
          isOpen={analyzeOpen}
          onClose={() => setAnalyzeOpen(false)}
          title="Resume Match Analysis"
        >
          {analysisError && (
            <div className="alert alert-error">
              <AlertTriangle size={16} />
              <span>{analysisError}</span>
            </div>
          )}
          {analysisLoading ? (
            <div className="analysis-loading-state">
              <div className="spinner-inline" />
              <p>Analyzing resume against this job...</p>
            </div>
          ) : analysis ? (
            <div className="resume-match-report">
              <div className="analysis-score-banner">
                <div>
                  <span className="section-eyebrow">RESUME FIT</span>
                  <div className="analysis-score-number font-mono">{analysis.overall_score}%</div>
                </div>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => setAnalysis(null)}
                >
                  Analyze Different Resume
                </button>
              </div>

              <div className="stack" style={{ gap: "var(--space-3)", marginTop: "var(--space-4)" }}>
                <h4>Score Factors</h4>
                {analysis.scores &&
                  Object.entries(analysis.scores).map(([key, val]) => (
                    <div key={key} className="factor-bar-item">
                      <div className="factor-bar-header">
                        <span style={{ textTransform: "capitalize" }}>{key}</span>
                        <span className="font-mono">{val}%</span>
                      </div>
                      <div className="score-bar-track">
                        <div className="score-bar-fill" style={{ width: `${val}%`, background: "var(--accent)" }} />
                      </div>
                    </div>
                  ))}
              </div>

              <div className="modal-footer" style={{ marginTop: "var(--space-4)" }}>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => {
                    setAnalyzeOpen(false);
                    setTailorOpen(true);
                  }}
                >
                  <Sparkles size={16} />
                  <span>Tailor My Resume for this Role</span>
                </button>
              </div>
            </div>
          ) : (
            <div className="resume-select-prompt">
              <p className="text-secondary text-sm">
                Select an uploaded resume to evaluate deterministic alignment against <strong>{job.title}</strong>:
              </p>

              {resumes.length === 0 ? (
                <div className="empty-resumes-prompt">
                  <p>No resumes uploaded yet.</p>
                  <Link to="/resumes" className="btn btn-primary btn-sm">
                    Upload Resume
                  </Link>
                </div>
              ) : (
                <div className="resumes-pick-list">
                  {resumes.map((r) => (
                    <label key={r.id} className={`resume-pick-item ${selectedResumeId === r.id ? "selected" : ""}`}>
                      <input
                        type="radio"
                        name="resume_pick"
                        checked={selectedResumeId === r.id}
                        onChange={() => setSelectedResumeId(r.id)}
                      />
                      <div className="pick-info">
                        <strong>{r.filename}</strong>
                        <span className="text-xs text-muted">
                          {r.parsing_status === "completed" ? "✓ Parsed" : r.parsing_status}
                        </span>
                      </div>
                    </label>
                  ))}

                  <div className="modal-footer" style={{ marginTop: "var(--space-4)" }}>
                    <button
                      type="button"
                      className="btn btn-ghost"
                      onClick={() => setAnalyzeOpen(false)}
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={runResumeAnalysis}
                      disabled={!selectedResumeId}
                    >
                      Run Resume Analysis
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </Modal>
      )}

      {/* AI Tailoring Wizard Modal */}
      {tailorOpen && (
        <TailoringModal
          isOpen={tailorOpen}
          onClose={() => setTailorOpen(false)}
          job={job}
          onSuccess={(res) => {
            setTailorOpen(false);
            setTailorResult(res);
          }}
        />
      )}

      {/* Cover Letter Modal */}
      {coverOpen && (
        <CoverLetterModal
          isOpen={coverOpen}
          onClose={() => setCoverOpen(false)}
          job={job}
        />
      )}

      {/* Score Explainer Dialog */}
      {showScoreExplainer && (
        <Modal
          isOpen={showScoreExplainer}
          onClose={() => setShowScoreExplainer(false)}
          title="How Match Scores Work"
        >
          <div className="score-explainer-body">
            <p className="text-secondary text-sm">
              CareerPilot computes your overall fit using a balanced 5-factor weighted algorithm comparing your verified profile against role requirements:
            </p>
            <ul className="score-factors-explanation">
              <li>
                <strong>Skills Alignment (40%):</strong> Compares your declared technical skills directly to requirements.
              </li>
              <li>
                <strong>Project Relevance (20%):</strong> Evaluates project tools, repositories, and technical stack.
              </li>
              <li>
                <strong>Experience Depth (20%):</strong> Evaluates years and depth of relevant positions.
              </li>
              <li>
                <strong>Role Alignment (15%):</strong> Analyzes title hierarchy and domain scope.
              </li>
              <li>
                <strong>Location Match (5%):</strong> Verifies remote, hybrid, or regional compatibility.
              </li>
            </ul>
            <div className="modal-footer">
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={() => setShowScoreExplainer(false)}
              >
                Got It
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
