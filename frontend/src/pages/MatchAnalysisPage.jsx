import { useState, useEffect, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../services/api";
import {
  ArrowLeft,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Sparkles,
} from "lucide-react";

function ScoreBar({ label, weight, value, max = 100, color = "var(--accent)" }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="factor-bar-item">
      <div className="factor-bar-header">
        <div className="match-factor-label-wrap">
          <span className="font-medium">{label}</span>
          <span className="text-xs text-muted" style={{ marginLeft: "6px" }}>({weight})</span>
        </div>
        <span className="font-mono font-semibold">{pct}%</span>
      </div>
      <div className="score-bar-track">
        <div
          className="score-bar-fill"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
    </div>
  );
}

export default function MatchAnalysisPage() {
  const params = useParams();
  const effectiveJobId = params.id || params.jobId;

  const [job, setJob] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const runAnalysis = useCallback(async () => {
    if (!effectiveJobId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.post(`/jobs/${effectiveJobId}/match`);
      setAnalysis(result);
    } catch (err) {
      setError(
        err.message ||
          "Analysis failed. Ensure your career profile has skills and experiences configured."
      );
    } finally {
      setLoading(false);
    }
  }, [effectiveJobId]);

  useEffect(() => {
    const fetchJobMeta = async () => {
      try {
        const jobData = await api.get(`/jobs/${effectiveJobId}`);
        setJob(jobData);
      } catch {
        // Non-blocking
      }
    };
    if (effectiveJobId) {
      fetchJobMeta();
      runAnalysis();
    }
  }, [effectiveJobId, runAnalysis]);

  const breakdown = analysis?.breakdown || {};
  const matchedSkills = analysis?.matched_skills || [];
  const missingSkills = analysis?.missing_skills || [];

  return (
    <div className="page match-analysis-page">
      {/* Navigation Breadcrumb */}
      <div className="details-breadcrumb">
        <Link to={`/discover/${effectiveJobId}`} className="breadcrumb-link">
          <ArrowLeft size={16} />
          <span>Back to Opportunity</span>
        </Link>
      </div>

      {/* Page Header */}
      <header className="page-header">
        <div className="page-header-row">
          <div>
            <h1>Profile Match Analysis</h1>
            <p>
              Deep fit breakdown for <strong>{job?.title || "Target Role"}</strong> at{" "}
              <strong>{job?.company || "Company"}</strong>
            </p>
          </div>

          <div className="page-header-actions">
            <button
              className="btn btn-secondary"
              onClick={runAnalysis}
              disabled={loading}
              type="button"
            >
              <RefreshCw size={16} className={loading ? "spin" : ""} />
              <span>Recalculate Fit</span>
            </button>

            <Link
              to={`/discover/${effectiveJobId}`}
              state={{ openTailor: true }}
              className="btn btn-primary"
            >
              <Sparkles size={16} />
              <span>Tailor Resume</span>
            </Link>
          </div>
        </div>
      </header>

      {error && (
        <div className="alert alert-error" role="alert">
          <AlertTriangle size={18} />
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <div className="card text-center" style={{ padding: "var(--space-12)" }}>
          <div className="spinner-inline" style={{ margin: "0 auto var(--space-4)" }} />
          <h3>Calculating Transparent Match...</h3>
          <p className="text-secondary">Comparing your verified skills and background against requirements.</p>
        </div>
      ) : analysis ? (
        <div className="stack" style={{ gap: "var(--space-6)" }}>
          {/* Hero Score Box */}
          <section className="card fit-hero-card">
            <div className="fit-hero-content">
              <div>
                <span className="section-eyebrow">OVERALL FIT SCORE</span>
                <div className="fit-score-display">
                  <span className="fit-score-number font-mono">{analysis.overall_score}%</span>
                  <span className="fit-score-badge">
                    {analysis.overall_score >= 80
                      ? "Excellent Match"
                      : analysis.overall_score >= 60
                      ? "Strong Match"
                      : "Moderate Match"}
                  </span>
                </div>
              </div>
            </div>

            {/* Breakdown Bars */}
            <div className="fit-factors-bars">
              <ScoreBar
                label="Skills Alignment"
                weight="40%"
                value={breakdown.skills?.score || 0}
                max={breakdown.skills?.max || 40}
              />
              <ScoreBar
                label="Project Relevance"
                weight="20%"
                value={breakdown.projects?.score || 0}
                max={breakdown.projects?.max || 20}
              />
              <ScoreBar
                label="Experience Depth"
                weight="20%"
                value={breakdown.experience?.score || 0}
                max={breakdown.experience?.max || 20}
              />
              <ScoreBar
                label="Role Fit"
                weight="15%"
                value={breakdown.role?.score || 0}
                max={breakdown.role?.max || 15}
              />
              <ScoreBar
                label="Location & Remote"
                weight="5%"
                value={breakdown.location?.score || 0}
                max={breakdown.location?.max || 5}
              />
            </div>
          </section>

          {/* Matched vs Missing Skills */}
          <div className="grid-2">
            <section className="card match-reasons-card success">
              <div className="card-header">
                <h3 style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <CheckCircle2 size={18} className="text-success" />
                  <span>Matching Skills ({matchedSkills.length})</span>
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
                  <p className="text-secondary text-sm">No exact skill matches detected.</p>
                )}
              </div>
            </section>

            <section className="card match-reasons-card warning">
              <div className="card-header">
                <h3 style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <AlertTriangle size={18} className="text-warning" />
                  <span>Missing Skills ({missingSkills.length})</span>
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
                  <p className="text-success text-sm font-medium">No missing skills detected!</p>
                )}
              </div>
            </section>
          </div>
        </div>
      ) : null}
    </div>
  );
}
