import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import Modal from "../Modal";
import { api } from "../../services/api";
import {
  FileText,
  CheckCircle2,
  AlertCircle,
  Sparkles,
  RefreshCw,
  FileSearch,
  ArrowRight,
  GraduationCap,
  Briefcase,
  FolderGit2,
} from "lucide-react";

function isResumeUsable(resume) {
  return resume.parsing_status === "completed" && !resume.parsing_error;
}

export default function AnalyzeResumeModal({
  isOpen,
  onClose,
  job,
  onTailorResume,
}) {
  const [resumes, setResumes] = useState([]);
  const [resumesLoading, setResumesLoading] = useState(false);
  const [resumesError, setResumesError] = useState(null);
  const [selectedResumeId, setSelectedResumeId] = useState(null);

  const [analyzing, setAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);

  const loadResumes = useCallback(async () => {
    setResumesLoading(true);
    setResumesError(null);
    setAnalysisError(null);
    setAnalysisResult(null);
    try {
      const data = await api.get("/resumes");
      const list = Array.isArray(data) ? data : [];
      setResumes(list);
      const firstUsable = list.find(isResumeUsable);
      if (firstUsable) {
        setSelectedResumeId(firstUsable.id);
      } else if (list.length > 0) {
        setSelectedResumeId(list[0].id);
      }
    } catch (err) {
      setResumesError(err.message || "Failed to load uploaded resumes.");
    } finally {
      setResumesLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      loadResumes();
    }
  }, [isOpen, loadResumes]);

  const handleRunAnalysis = async () => {
    if (!selectedResumeId || !job?.id) return;
    setAnalyzing(true);
    setAnalysisError(null);
    try {
      const result = await api.analyzeResume(job.id, selectedResumeId);
      setAnalysisResult(result);
    } catch (err) {
      setAnalysisError(err.message || "Resume match analysis could not be completed.");
    } finally {
      setAnalyzing(false);
    }
  };

  const handleClose = () => {
    if (analyzing) return;
    onClose();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Resume Match Analysis"
    >
      <div className="analyze-resume-modal-body">
        {analysisResult ? (
          /* Report View */
          <div className="resume-analysis-report stack" style={{ gap: "var(--space-4)" }}>
            <div className="card fit-hero-card" style={{ padding: "var(--space-4)" }}>
              <span className="section-eyebrow">RESUME FIT SCORE</span>
              <div className="fit-score-display" style={{ marginTop: "4px" }}>
                <span className="fit-score-number font-mono">{analysisResult.overall_score}%</span>
                <span className={`fit-score-badge ${analysisResult.overall_score >= 70 ? "high" : ""}`}>
                  {analysisResult.overall_score >= 80
                    ? "High Match"
                    : analysisResult.overall_score >= 60
                    ? "Strong Match"
                    : analysisResult.overall_score >= 40
                    ? "Moderate Match"
                    : "Low Match"}
                </span>
              </div>
              <p className="text-secondary text-xs" style={{ marginTop: "var(--space-2)" }}>
                Analysis of selected resume against <strong>{job.title}</strong> at <strong>{job.company}</strong>.
              </p>
            </div>

            {/* Factor Scores */}
            {analysisResult.scores && (
              <div className="fit-factors-section">
                <h4 className="fit-subheading">Resume Fit Breakdown</h4>
                <div className="fit-factors-bars">
                  {Object.entries(analysisResult.scores).map(([factor, val]) => (
                    <div key={factor} className="factor-bar-item">
                      <div className="factor-bar-header">
                        <span className="factor-name font-medium" style={{ textTransform: "capitalize" }}>
                          {factor} Alignment
                        </span>
                        <span className="factor-val font-mono font-semibold">{val ?? 0}%</span>
                      </div>
                      <div className="score-bar-track">
                        <div
                          className="score-bar-fill"
                          style={{ width: `${Math.min(100, Math.max(0, val ?? 0))}%`, background: "var(--accent)" }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Matched & Missing Skills */}
            <div className="grid-2" style={{ gap: "var(--space-3)" }}>
              <div className="card" style={{ padding: "var(--space-3)" }}>
                <h5 className="text-xs font-semibold text-success" style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                  <CheckCircle2 size={14} />
                  <span>Matching Skills ({analysisResult.matched_skills?.length || 0})</span>
                </h5>
                <div className="skills-chips-wrap" style={{ marginTop: "var(--space-2)" }}>
                  {analysisResult.matched_skills?.length > 0 ? (
                    analysisResult.matched_skills.map((s) => (
                      <span key={s} className="skill-chip match">
                        ✓ {s}
                      </span>
                    ))
                  ) : (
                    <span className="text-xs text-muted">No direct skill matches detected.</span>
                  )}
                </div>
              </div>

              <div className="card" style={{ padding: "var(--space-3)" }}>
                <h5 className="text-xs font-semibold text-warning" style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                  <AlertCircle size={14} />
                  <span>Missing Skills ({analysisResult.missing_skills?.length || 0})</span>
                </h5>
                <div className="skills-chips-wrap" style={{ marginTop: "var(--space-2)" }}>
                  {analysisResult.missing_skills?.length > 0 ? (
                    analysisResult.missing_skills.map((s) => (
                      <span key={s} className="skill-chip missing">
                        ⚠ {s}
                      </span>
                    ))
                  ) : (
                    <span className="text-xs text-success font-medium">No critical missing skills!</span>
                  )}
                </div>
              </div>
            </div>

            {/* Education & Certification Relevance */}
            {analysisResult.education_certification_relevance?.reason && (
              <div className="aligned-evidence-item">
                <div className="evidence-header">
                  <GraduationCap size={14} className="text-accent" aria-hidden="true" />
                  <span>Education Relevance:</span>
                </div>
                <p className="evidence-text">{analysisResult.education_certification_relevance.reason}</p>
              </div>
            )}

            {/* Actions */}
            <div className="modal-footer" style={{ marginTop: "var(--space-4)" }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setAnalysisResult(null)}
              >
                <RefreshCw size={14} />
                <span>Analyze Different Resume</span>
              </button>
              {onTailorResume && (
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => {
                    handleClose();
                    onTailorResume();
                  }}
                >
                  <Sparkles size={16} />
                  <span>Tailor Resume for this Role</span>
                </button>
              )}
            </div>
          </div>
        ) : (
          /* Selection View */
          <div className="resume-select-prompt">
            <p className="text-secondary text-sm">
              Select one of your uploaded master resumes to evaluate deterministic match alignment against{" "}
              <strong>{job.title}</strong>:
            </p>

            {resumesLoading ? (
              <div className="loading-state" style={{ padding: "var(--space-8) 0", textAlign: "center" }}>
                <div className="spinner-inline" style={{ margin: "0 auto var(--space-2)" }} />
                <p className="text-xs text-muted">Loading uploaded resumes...</p>
              </div>
            ) : resumesError ? (
              <div className="alert alert-error" style={{ marginTop: "var(--space-3)" }}>
                <AlertCircle size={16} />
                <span>{resumesError}</span>
              </div>
            ) : resumes.length === 0 ? (
              <div className="empty-resumes-prompt card text-center" style={{ padding: "var(--space-6)", marginTop: "var(--space-3)" }}>
                <FileText size={28} className="text-muted" style={{ margin: "0 auto var(--space-2)" }} />
                <p className="text-sm text-secondary">You haven't uploaded any resumes yet.</p>
                <div style={{ marginTop: "var(--space-3)" }}>
                  <Link to="/resumes" className="btn btn-primary btn-sm">
                    Upload a Resume First
                  </Link>
                </div>
              </div>
            ) : (
              <div className="resumes-pick-list" style={{ marginTop: "var(--space-3)" }}>
                {resumes.map((r) => {
                  const usable = isResumeUsable(r);
                  return (
                    <label
                      key={r.id}
                      className={`resume-pick-item ${selectedResumeId === r.id ? "selected" : ""} ${!usable ? "disabled" : ""}`}
                    >
                      <input
                        type="radio"
                        name="resume_analysis_pick"
                        disabled={!usable}
                        checked={selectedResumeId === r.id}
                        onChange={() => setSelectedResumeId(r.id)}
                      />
                      <div className="pick-info">
                        <strong>{r.filename || r.original_filename || "Resume Document"}</strong>
                        <span className="text-xs text-muted">
                          {usable ? "✓ Ready for analysis" : "Processing required"}
                        </span>
                      </div>
                    </label>
                  );
                })}
              </div>
            )}

            {analysisError && (
              <div className="alert alert-error" style={{ marginTop: "var(--space-3)" }}>
                <AlertCircle size={16} />
                <span>{analysisError}</span>
              </div>
            )}

            <div className="modal-footer" style={{ marginTop: "var(--space-6)" }}>
              <button type="button" className="btn btn-ghost" onClick={handleClose}>
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleRunAnalysis}
                disabled={!selectedResumeId || analyzing}
              >
                {analyzing ? (
                  <>
                    <div className="spinner-inline" />
                    <span>Analyzing...</span>
                  </>
                ) : (
                  <>
                    <FileSearch size={16} />
                    <span>Run Resume Analysis</span>
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}
