import { useState, useEffect, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../services/api";
import { SkeletonCard } from "../components/Skeleton";
import Modal from "../components/Modal";
import {
  ArrowLeft,
  MapPin,
  Briefcase,
  BarChart3,
  ExternalLink,
  Layers,
  Sparkles,
  Building2,
  Globe,
  Clock,
  FileText,
  CheckCircle2,
  AlertCircle,
  XCircle,
  RefreshCw,
  FileSearch,
  Loader2,
  GraduationCap,
  Gauge,
} from "lucide-react";

function ResumeMatchResult({ analysis, onReset }) {
  const scores = analysis.scores || {};
  const scoreFactors = [
    { key: "skills", label: "Skills", weight: "40%" },
    { key: "keywords", label: "Keywords", weight: "20%" },
    { key: "experience", label: "Experience", weight: "20%" },
    { key: "projects", label: "Projects", weight: "15%" },
    { key: "education", label: "Education / Certifications", weight: "5%" },
  ];

  return (
    <div className="resume-match-result">
      {/* Score hero */}
      <div className="resume-match-hero">
        <div className="resume-match-badge">
          <span className="resume-match-label">RESUME MATCH</span>
          <span className="resume-match-score">{analysis.overall_score}%</span>
        </div>
        <p className="resume-match-subtitle">
          Deterministic analysis of your selected resume against this role.
        </p>
      </div>

      {analysis.note && (
        <div className="alert alert-warning" role="alert">
          <AlertCircle size={16} />
          <span>{analysis.note}</span>
        </div>
      )}

      {/* Breakdown */}
      <div className="card">
        <div className="card-header">
          <h4 style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <Gauge size={16} className="text-accent" />
            <span>Score Breakdown</span>
          </h4>
        </div>
        <div className="card-body">
          <div className="match-factors-list">
            {scoreFactors.map((f) => {
              const value = scores[f.key];
              const pct = typeof value === "number" ? value : null;
              return (
                <div className="match-factor-row" key={f.key}>
                  <div className="match-factor-header">
                    <div className="match-factor-label-wrap">
                      <span className="match-factor-label">{f.label}</span>
                      {pct === null && (
                        <span className="match-factor-weight">(not applicable)</span>
                      )}
                    </div>
                    <span className="match-factor-value font-mono">
                      {pct === null ? "—" : `${pct}%`}
                    </span>
                  </div>
                  {pct !== null && (
                    <div className="score-bar-track">
                      <div
                        className="score-bar-fill"
                        style={{
                          width: `${Math.min(100, pct)}%`,
                          background: "var(--accent)",
                        }}
                      />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Matched vs Missing skills */}
      <div className="match-skills-dual-grid">
        <div className="card">
          <div className="card-header">
            <h4 className="text-success" style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <CheckCircle2 size={18} />
              <span>Matched Skills ({analysis.matched_skills?.length ?? 0})</span>
            </h4>
          </div>
          <div className="card-body">
            {analysis.matched_skills?.length ? (
              <div className="skills-tags-wrap">
                {analysis.matched_skills.map((s) => (
                  <span key={s} className="skill-tag skill-matched">{s}</span>
                ))}
              </div>
            ) : (
              <p className="text-secondary" style={{ fontSize: "var(--text-sm)" }}>No matched skills detected.</p>
            )}
          </div>
        </div>
        <div className="card">
          <div className="card-header">
            <h4 className="text-warning" style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <AlertCircle size={18} />
              <span>Missing Skills ({analysis.missing_skills?.length ?? 0})</span>
            </h4>
          </div>
          <div className="card-body">
            {analysis.missing_skills?.length ? (
              <div className="skills-tags-wrap">
                {analysis.missing_skills.map((s) => (
                  <span key={s} className="skill-tag skill-missing">{s}</span>
                ))}
              </div>
            ) : (
              <p className="text-success" style={{ fontSize: "var(--text-sm)", fontWeight: "var(--weight-medium)" }}>
                No missing skills detected!
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Relevant projects */}
      {analysis.relevant_projects?.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h4 style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <CheckCircle2 size={18} className="text-success" />
              <span>Relevant Projects ({analysis.relevant_projects.length})</span>
            </h4>
          </div>
          <div className="card-body">
            {analysis.relevant_projects.map((p, i) => (
              <div className="resume-match-entry" key={i}>
                <div className="resume-match-entry-head">
                  <strong>{p.name || "Project"}</strong>
                  <span className="resume-match-entry-score">{p.relevance_score}%</span>
                </div>
                {p.matched_technologies?.length > 0 && (
                  <div className="skills-tags-wrap" style={{ marginTop: "var(--space-1)" }}>
                    {p.matched_technologies.map((t, j) => (
                      <span className="skill-tag" key={`${t}-${j}`}>{t}</span>
                    ))}
                  </div>
                )}
                {p.reason && <p className="resume-match-entry-reason">{p.reason}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Relevant experience */}
      {analysis.relevant_experience?.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h4 style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <Briefcase size={18} className="text-accent" />
              <span>Relevant Experience ({analysis.relevant_experience.length})</span>
            </h4>
          </div>
          <div className="card-body">
            {analysis.relevant_experience.map((e, i) => (
              <div className="resume-match-entry" key={i}>
                <div className="resume-match-entry-head">
                  <strong>{[e.job_title, e.company].filter(Boolean).join(" — ") || "Experience"}</strong>
                  <span className="resume-match-entry-score">{e.relevance_score}%</span>
                </div>
                {e.dates && <span className="insight-muted">{e.dates}</span>}
                {e.reason && <p className="resume-match-entry-reason">{e.reason}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Missing keywords */}
      {analysis.missing_keywords?.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h4 className="text-warning" style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <AlertCircle size={18} />
              <span>Missing Keywords ({analysis.missing_keywords.length})</span>
            </h4>
          </div>
          <div className="card-body">
            <div className="skills-tags-wrap">
              {analysis.missing_keywords.map((k, i) => (
                <span className="skill-tag skill-missing" key={`${k}-${i}`}>{k}</span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Education */}
      {analysis.education_certification_relevance && (
        <div className="card">
          <div className="card-header">
            <h4 style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <GraduationCap size={18} className="text-accent" />
              <span>Education / Certification</span>
            </h4>
          </div>
          <div className="card-body">
            <div className="resume-match-entry-head">
              <span className="match-factor-label">
                {analysis.education_certification_relevance.score != null
                  ? `${analysis.education_certification_relevance.score}%`
                  : "Not applicable"}
              </span>
            </div>
            {analysis.education_certification_relevance.reason && (
              <p className="resume-match-entry-reason">
                {analysis.education_certification_relevance.reason}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Recommendations */}
      {analysis.suggestions?.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h4 style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <FileSearch size={18} className="text-accent" />
              <span>Recommendations</span>
            </h4>
          </div>
          <div className="card-body">
            <ul className="match-evidence-list">
              {analysis.suggestions.map((s, i) => (
                <li className="match-evidence-item" key={i}>
                  <CheckCircle2 size={16} className="text-accent" />
                  <span>{s}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      <button className="btn btn-outline btn-block" onClick={onReset} type="button">
        <RefreshCw size={16} />
        <span>Analyze a different resume</span>
      </button>
    </div>
  );
}

export default function JobDetailsPage() {
  const { id } = useParams();
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Analyze Resume modal state
  const [analyzeOpen, setAnalyzeOpen] = useState(false);
  const [resumes, setResumes] = useState([]);
  const [resumesLoading, setResumesLoading] = useState(false);
  const [resumesError, setResumesError] = useState(null);
  const [selectedResumeId, setSelectedResumeId] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState(null);

  useEffect(() => {
    const loadJob = async () => {
      try {
        const data = await api.get(`/jobs/${id}`);
        setJob(data);
      } catch {
        setError("Opportunity details could not be found.");
      } finally {
        setLoading(false);
      }
    };
    loadJob();
  }, [id]);

  const openAnalyze = useCallback(async () => {
    setAnalyzeOpen(true);
    setAnalysis(null);
    setAnalysisError(null);
    setSelectedResumeId(null);
    setResumesLoading(true);
    setResumesError(null);
    try {
      const data = await api.get("/resumes");
      setResumes(Array.isArray(data) ? data : []);
      const firstUsable = (Array.isArray(data) ? data : []).find((r) => isResumeAnalyzable(r));
      if (firstUsable) setSelectedResumeId(firstUsable.id);
    } catch (err) {
      setResumesError(err.message || "Failed to load your resumes.");
    } finally {
      setResumesLoading(false);
    }
  }, []);

  const closeAnalyze = () => {
    setAnalyzeOpen(false);
    setAnalysis(null);
    setAnalysisError(null);
    setAnalysisLoading(false);
  };

  const runAnalysis = async () => {
    if (!selectedResumeId) return;
    setAnalysisLoading(true);
    setAnalysisError(null);
    setAnalysis(null);
    try {
      const result = await api.analyzeResume(id, selectedResumeId);
      setAnalysis(result);
    } catch (err) {
      setAnalysisError(err.message || "Resume Match analysis could not be completed.");
    } finally {
      setAnalysisLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="page">
        <div className="page-header">
          <div className="skeleton skeleton-title" style={{ width: 300, height: 32 }} />
        </div>
        <div className="grid-2">
          <SkeletonCard lines={6} />
          <SkeletonCard lines={4} />
        </div>
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

  return (
    <div className="page">
      {/* === Navigation Breadcrumb === */}
      <div className="page-nav-breadcrumb">
        <Link to="/discover" className="btn btn-ghost btn-sm">
          <ArrowLeft size={16} />
          <span>Back to Opportunities</span>
        </Link>
      </div>

      {/* === Analyze Resume Modal === */}
      <Modal
        isOpen={analyzeOpen}
        onClose={closeAnalyze}
        title="Resume Match Analysis"
      >
        {analysisLoading ? (
          <div className="resume-insights-loading">
            <div className="spinner" />
            <p>Analyzing resume against this job...</p>
          </div>
        ) : analysis ? (
          <ResumeMatchResult analysis={analysis} onReset={() => { setAnalysis(null); }} />
        ) : (
          <div className="resume-analyze-select">
            <p className="text-secondary" style={{ fontSize: "var(--text-sm)", marginBottom: "var(--space-4)" }}>
              Select one of your uploaded resumes to compare against{" "}
              <strong>{job.title}</strong> at <strong>{job.company}</strong>. This is a{" "}
              <strong>Resume Match</strong> — separate from your CareerPilot profile match.
            </p>

            {resumesLoading ? (
              <div className="resume-insights-loading">
                <div className="spinner" />
                <p>Loading resumes...</p>
              </div>
            ) : resumesError ? (
              <div className="resume-insight-error">
                <AlertCircle size={20} />
                <div>
                  <strong>Could not load resumes.</strong>
                  <p>{resumesError}</p>
                </div>
              </div>
            ) : resumes.length === 0 ? (
              <div className="resume-insight-empty">
                <FileText size={20} />
                <p>You have no uploaded resumes yet.</p>
                <Link to="/resumes" className="btn btn-primary btn-sm">
                  <FileText size={14} />
                  <span>Upload a Resume</span>
                </Link>
              </div>
            ) : (
              <div className="resume-analyze-list">
                {resumes.map((resume) => {
                  const analyzable = isResumeAnalyzable(resume);
                  const selected = selectedResumeId === resume.id;
                  return (
                    <button
                      key={resume.id}
                      type="button"
                      disabled={!analyzable}
                      onClick={() => setSelectedResumeId(resume.id)}
                      className={`resume-analyze-option ${selected ? "is-selected" : ""} ${!analyzable ? "is-disabled" : ""}`}
                    >
                      <div className="resume-analyze-option-main">
                        <div className="resume-analyze-option-icon">
                          <FileText size={18} />
                        </div>
                        <div className="resume-analyze-option-details">
                          <strong className="resume-analyze-option-name">
                            {resume.original_filename}
                          </strong>
                          <span className={`parsing-status-chip parsing-${resume.parsing_status || "pending"}`}>
                            {resume.parsing_status === "completed" && !resume.parsing_error ? (
                              <CheckCircle2 size={12} />
                            ) : resume.parsing_status === "failed" ? (
                              <XCircle size={12} />
                            ) : (
                              <RefreshCw size={12} />
                            )}
                            <span>{parsingStatusLabel(resume)}</span>
                          </span>
                        </div>
                      </div>
                      {!analyzable && (
                        <span className="resume-analyze-option-note">
                          {!resume.parsing_error
                            ? "Not ready for analysis"
                            : "No usable text"}
                        </span>
                      )}
                    </button>
                  );
                })}

                {resumes.every((r) => !isResumeAnalyzable(r)) && (
                  <div className="resume-insight-empty" style={{ marginTop: "var(--space-3)" }}>
                    <AlertCircle size={20} />
                    <p>
                      No usable resume data is available for analysis. Try uploading a text-based
                      PDF or re-parse your resume.
                    </p>
                  </div>
                )}
              </div>
            )}

            {analysisError && (
              <div className="resume-insight-error" style={{ marginTop: "var(--space-3)" }}>
                <AlertCircle size={20} />
                <div>
                  <strong>Analysis failed.</strong>
                  <p>{analysisError}</p>
                </div>
              </div>
            )}

            <div className="modal-footer-inline">
              <button
                className="btn btn-primary btn-block"
                onClick={runAnalysis}
                disabled={!selectedResumeId || analysisLoading}
                type="button"
              >
                {analysisLoading ? <Loader2 size={16} className="spin" /> : <Sparkles size={16} />}
                <span>{analysisLoading ? "Analyzing..." : "Analyze Selected Resume"}</span>
              </button>
            </div>
          </div>
        )}
      </Modal>

      {/* === Hero Role Header === */}
      <header className="job-workspace-header">
        <div className="job-workspace-top">
          <div className="job-workspace-brand">
            <div className="job-workspace-logo">
              <Building2 size={24} />
            </div>
            <div>
              <span className="job-workspace-company">{job.company}</span>
              <h1 className="job-workspace-title">{job.title}</h1>
            </div>
          </div>

          <div className="job-workspace-primary-cta">
            <button className="btn btn-outline btn-lg" onClick={openAnalyze} type="button">
              <FileSearch size={18} />
              <span>Analyze Resume</span>
            </button>
            <Link to={`/discover/${job.id}/match`} className="btn btn-primary btn-lg">
              <Sparkles size={18} />
              <span>Run Match Analysis</span>
            </Link>
          </div>
        </div>

        <div className="job-workspace-meta-chips">
          {job.location && (
            <div className="meta-chip">
              <MapPin size={14} />
              <span>{job.location}</span>
            </div>
          )}
          {job.employment_type && (
            <div className="meta-chip">
              <Briefcase size={14} />
              <span>{job.employment_type}</span>
            </div>
          )}
          {job.experience_level && (
            <div className="meta-chip">
              <BarChart3 size={14} />
              <span>{job.experience_level}</span>
            </div>
          )}
          {job.source && (
            <div className="meta-chip">
              <Globe size={14} />
              <span>Source: {job.source}</span>
            </div>
          )}
          {job.created_at && (
            <div className="meta-chip">
              <Clock size={14} />
              <span>Discovered {new Date(job.created_at).toLocaleDateString()}</span>
            </div>
          )}
        </div>

        <p className="resume-match-context" style={{ marginTop: "var(--space-3)" }}>
          <strong>Resume Match</strong> compares an uploaded resume to this job.{" "}
          <strong>Match Analysis</strong> compares your CareerPilot profile to this job.
        </p>
      </header>

      {/* === Decision Workspace Two-Column Grid === */}
      <div className="job-workspace-grid">
        {/* Left Column: Description & Responsibilities */}
        <div className="job-workspace-main">
          <section className="card">
            <div className="card-header">
              <h2>Role Description & Context</h2>
            </div>
            <div className="card-body">
              {job.description ? (
                <div className="job-description-content">
                  {job.description.split("\n").map((para, i) =>
                    para.trim() ? <p key={i}>{para}</p> : null
                  )}
                </div>
              ) : (
                <p className="text-secondary">
                  No detailed description provided for this listing. You can run Match Analysis using the required skills.
                </p>
              )}
            </div>
          </section>
        </div>

        {/* Right Column: Required Skills & Action Deck */}
        <aside className="job-workspace-sidebar">
          {/* Match Analysis Callout */}
          <div className="card card-highlight">
            <div className="card-header">
              <h3>
                <Sparkles size={16} className="text-accent" />
                <span>AI Fit Evaluation</span>
              </h3>
            </div>
            <div className="card-body">
              <p style={{ fontSize: "var(--text-sm)", color: "var(--text-secondary)" }}>
                Compare your technical skills, projects, and work experience against this position's requirements.
              </p>
              <Link to={`/discover/${job.id}/match`} className="btn btn-primary btn-block">
                <Sparkles size={16} />
                <span>Inspect Match Breakdown</span>
              </Link>
            </div>
          </div>

          {/* Resume Match Callout */}
          <div className="card">
            <div className="card-header">
              <h3>
                <FileSearch size={16} className="text-accent" />
                <span>Resume Match</span>
              </h3>
            </div>
            <div className="card-body">
              <p style={{ fontSize: "var(--text-sm)", color: "var(--text-secondary)" }}>
                Compare an uploaded resume (skills, keywords, projects, experience, education) against this role.
              </p>
              <button className="btn btn-outline btn-block" onClick={openAnalyze} type="button">
                <FileSearch size={16} />
                <span>Analyze Resume</span>
              </button>
            </div>
          </div>

          {/* Required Skills */}
          {job.required_skills?.length > 0 && (
            <div className="card">
              <div className="card-header">
                <h3>Required Skills ({job.required_skills.length})</h3>
              </div>
              <div className="card-body">
                <div className="job-skills-tags-wrap">
                  {job.required_skills.map((s) => (
                    <span key={s} className="skill-tag">{s}</span>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Application Pipeline Action */}
          <div className="card">
            <div className="card-header">
              <h3>Take Action</h3>
            </div>
            <div className="card-body">
              <Link to="/pipeline" className="btn btn-outline btn-block">
                <Layers size={16} />
                <span>Track in Application Pipeline</span>
              </Link>

              {job.url && (
                <a
                  href={job.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-secondary btn-block"
                  style={{ marginTop: "var(--space-2)" }}
                >
                  <ExternalLink size={16} />
                  <span>Apply on Company Site</span>
                </a>
              )}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

function isResumeAnalyzable(resume) {
  return resume.parsing_status === "completed" && !resume.parsing_error;
}

function parsingStatusLabel(resume) {
  const status = resume.parsing_status || "pending";
  if (status === "completed" && !resume.parsing_error) return "Analyzed";
  if (status === "completed") return "Scanned / no text";
  if (status === "failed") return "Analysis failed";
  return "Pending analysis";
}
