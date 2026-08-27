import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../services/api";
import ScoreBadge from "../components/ScoreBadge";
import EmptyState from "../components/EmptyState";
import {
  ArrowLeft,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Sparkles,
  Layers,
  ExternalLink,
  Briefcase,
  Code2,
  FolderGit2,
  Lightbulb,
} from "lucide-react";

function ScoreBar({ label, weight, value, max = 100, color = "var(--accent)" }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="match-factor-row">
      <div className="match-factor-header">
        <div className="match-factor-label-wrap">
          <span className="match-factor-label">{label}</span>
          <span className="match-factor-weight">({weight} weight)</span>
        </div>
        <span className="match-factor-value font-mono">{pct}%</span>
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
  const [hasRun, setHasRun] = useState(false);

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
      // Auto-run analysis if desired, or user can click
      runAnalysis();
    }
  }, [effectiveJobId]);

  const runAnalysis = async () => {
    if (!effectiveJobId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.post(`/jobs/${effectiveJobId}/match`);
      setAnalysis(result);
      setHasRun(true);
    } catch (err) {
      setError(
        err.message ||
          "Analysis failed. Ensure your career profile has skills, projects, and education configured."
      );
    } finally {
      setLoading(false);
    }
  };

  const breakdown = analysis?.breakdown || {};
  const matchedSkills = analysis?.matched_skills || [];
  const missingSkills = analysis?.missing_skills || [];

  return (
    <div className="page">
      {/* === Navigation Breadcrumb === */}
      <div className="page-nav-breadcrumb">
        <Link to={`/discover/${effectiveJobId}`} className="btn btn-ghost btn-sm">
          <ArrowLeft size={16} />
          <span>Back to Opportunity</span>
        </Link>
      </div>

      {/* === Page Header === */}
      <header className="page-header">
        <div className="page-header-row">
          <div>
            <h1>Intelligent Match Analysis</h1>
            <p>
              {job ? (
                <>Evaluating fit for <strong>{job.title}</strong> at <strong>{job.company}</strong></>
              ) : (
                "Multidimensional fit breakdown and skill gap coaching"
              )}
            </p>
          </div>

          <div className="page-header-actions">
            <button
              className="btn btn-secondary btn-sm"
              onClick={runAnalysis}
              disabled={loading}
            >
              <RefreshCw size={14} className={loading ? "spin" : ""} />
              <span>{loading ? "Analyzing..." : "Re-run Analysis"}</span>
            </button>
            <Link to="/pipeline" className="btn btn-primary btn-sm">
              <Layers size={14} />
              <span>Track in Pipeline</span>
            </Link>
          </div>
        </div>
      </header>

      {error && (
        <div className="alert alert-error" role="alert">
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      {loading && !analysis && (
        <div className="card" style={{ textAlign: "center", padding: "var(--space-16)" }}>
          <div className="spinner" />
          <h3 style={{ marginTop: "var(--space-4)" }}>Running 5-Factor Fit Engine...</h3>
          <p className="text-secondary" style={{ maxWidth: 420, margin: "var(--space-2) auto 0" }}>
            Evaluating your skills (50%), projects (20%), experience (15%), role fit (10%), and location (5%).
          </p>
        </div>
      )}

      {!hasRun && !loading && !analysis && (
        <EmptyState
          icon={Sparkles}
          title="Ready to evaluate match"
          text="Run an intelligent multi-dimensional evaluation to see how your career profile aligns with this role."
          action={
            <button className="btn btn-primary" onClick={runAnalysis}>
              <Sparkles size={16} /> Run Match Analysis
            </button>
          }
        />
      )}

      {analysis && (
        <div className="match-workspace-content">
          {/* === Hero Match Narrative Banner === */}
          <section className="match-overview-card">
            <div className="match-overview-score-col">
              <ScoreBadge score={analysis.match_score} size="large" />
            </div>

            <div className="match-overview-narrative">
              <div className="match-narrative-eyebrow">
                <Lightbulb size={14} />
                <span>Executive Fit Narrative</span>
              </div>
              <h2 className="match-narrative-title">
                {analysis.match_score >= 80
                  ? "Strong Competitive Alignment"
                  : analysis.match_score >= 60
                  ? "Moderate Alignment with Growth Potential"
                  : "Growth Opportunity"}
              </h2>
              <p className="match-narrative-text">
                {analysis.explanation ||
                  `Your profile demonstrates a ${analysis.match_score}% calculated fit. Review the capability breakdown below to understand matched strengths and growth targets.`}
              </p>
            </div>
          </section>

          {/* === Two-Column Capabilities & Breakdown === */}
          <div className="match-columns-grid">
            {/* Left Column: Strengths vs Missing Skills & Evidence */}
            <div className="match-main-col">
              {/* Strengths & Growth Skills */}
              <div className="match-skills-dual-grid">
                <div className="card">
                  <div className="card-header">
                    <h3 className="text-success" style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                      <CheckCircle2 size={18} />
                      <span>Matched Capabilities ({matchedSkills.length})</span>
                    </h3>
                  </div>
                  <div className="card-body">
                    {matchedSkills.length > 0 ? (
                      <div className="skills-tags-wrap">
                        {matchedSkills.map((s) => (
                          <span key={s} className="skill-tag skill-matched">{s}</span>
                        ))}
                      </div>
                    ) : (
                      <p className="text-secondary" style={{ fontSize: "var(--text-sm)" }}>
                        No direct skill matches found. Check your profile skills to make sure all relevant technologies are listed.
                      </p>
                    )}
                  </div>
                </div>

                <div className="card">
                  <div className="card-header">
                    <h3 className="text-warning" style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                      <AlertCircle size={18} />
                      <span>Skill Growth Focus ({missingSkills.length})</span>
                    </h3>
                  </div>
                  <div className="card-body">
                    {missingSkills.length > 0 ? (
                      <div className="skills-tags-wrap">
                        {missingSkills.map((s) => (
                          <span key={s} className="skill-tag skill-missing">{s}</span>
                        ))}
                      </div>
                    ) : (
                      <p className="text-success" style={{ fontSize: "var(--text-sm)", fontWeight: "var(--weight-medium)" }}>
                        No missing skills detected! You satisfy 100% of stated skill requirements.
                      </p>
                    )}
                  </div>
                </div>
              </div>

              {/* Relevant Projects Alignment */}
              {analysis.relevant_projects?.length > 0 && (
                <div className="card" style={{ marginTop: "var(--space-6)" }}>
                  <div className="card-header">
                    <h3 style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                      <FolderGit2 size={18} className="text-accent" />
                      <span>Supporting Projects Alignment</span>
                    </h3>
                  </div>
                  <div className="card-body">
                    <ul className="match-evidence-list">
                      {analysis.relevant_projects.map((proj, i) => (
                        <li key={i} className="match-evidence-item">
                          <CheckCircle2 size={16} className="text-success" />
                          <span>{proj}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}

              {/* Relevant Experience Alignment */}
              {analysis.relevant_experience?.length > 0 && (
                <div className="card" style={{ marginTop: "var(--space-6)" }}>
                  <div className="card-header">
                    <h3 style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                      <Briefcase size={18} className="text-accent" />
                      <span>Relevant Work Experience Alignment</span>
                    </h3>
                  </div>
                  <div className="card-body">
                    <ul className="match-evidence-list">
                      {analysis.relevant_experience.map((exp, i) => (
                        <li key={i} className="match-evidence-item">
                          <CheckCircle2 size={16} className="text-success" />
                          <span>{exp}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}
            </div>

            {/* Right Column: 5-Factor Weighted Algorithm Breakdown */}
            <aside className="match-side-col">
              <div className="card">
                <div className="card-header">
                  <h3 style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                    <Code2 size={16} className="text-accent" />
                    <span>5-Factor Algorithm Breakdown</span>
                  </h3>
                </div>
                <div className="card-body">
                  <p style={{ fontSize: "var(--text-xs)", color: "var(--text-secondary)", marginBottom: "var(--space-4)" }}>
                    Calculated using CareerPilot's weighted matching algorithm:
                  </p>

                  <div className="match-factors-list">
                    <ScoreBar
                      label="Skills"
                      weight="50%"
                      value={breakdown.skills ?? breakdown.technical_skills ?? 0}
                      color="var(--accent)"
                    />
                    <ScoreBar
                      label="Projects"
                      weight="20%"
                      value={breakdown.projects ?? 0}
                      color="var(--purple)"
                    />
                    <ScoreBar
                      label="Experience"
                      weight="15%"
                      value={breakdown.experience ?? 0}
                      color="var(--info)"
                    />
                    <ScoreBar
                      label="Role Alignment"
                      weight="10%"
                      value={breakdown.role_alignment ?? breakdown.role_fit ?? 0}
                      color="var(--success)"
                    />
                    <ScoreBar
                      label="Location"
                      weight="5%"
                      value={breakdown.location ?? 0}
                      color="var(--warning)"
                    />
                  </div>
                </div>
              </div>

              {/* Action Callout */}
              <div className="card" style={{ marginTop: "var(--space-6)" }}>
                <div className="card-header">
                  <h3>Next Steps</h3>
                </div>
                <div className="card-body">
                  <Link to="/pipeline" className="btn btn-primary btn-block">
                    <Layers size={16} />
                    <span>Track in Application Pipeline</span>
                  </Link>
                  {job?.url && (
                    <a
                      href={job.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn btn-outline btn-block"
                      style={{ marginTop: "var(--space-2)" }}
                    >
                      <ExternalLink size={16} />
                      <span>Open Application URL</span>
                    </a>
                  )}
                </div>
              </div>
            </aside>
          </div>
        </div>
      )}
    </div>
  );
}
