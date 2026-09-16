import { useState } from "react";
import {
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  HelpCircle,
  ChevronDown,
  ChevronUp,
  FolderGit2,
  Briefcase,
  GraduationCap,
  FileSearch,
} from "lucide-react";

function FactorBar({ label, weight, value, color = "var(--accent)" }) {
  const pct = Math.min(100, Math.max(0, Math.round(value || 0)));
  return (
    <div className="factor-bar-item">
      <div className="factor-bar-header">
        <div className="match-factor-label-wrap">
          <span className="factor-name font-medium">{label}</span>
          <span className="factor-weight text-xs text-muted" style={{ marginLeft: "6px" }}>
            ({weight})
          </span>
        </div>
        <span className="factor-val font-mono font-semibold">{pct}%</span>
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

export default function JobFitPanel({
  matchData,
  job,
  loading = false,
  onRecalculate,
  onAnalyzeResume,
  onTailor,
}) {
  const [showExplainer, setShowExplainer] = useState(false);

  const overallScore = matchData?.overall_score ?? job?.match_score ?? 0;
  const hasAnalysis = Boolean(matchData);

  const FACTOR_LABELS = {
    skills: "Skills",
    experience: "Experience",
    role: "Role Alignment",
    projects: "Projects",
    location: "Location",
    education: "Education",
    work_mode: "Work Mode",
  };

  const displayFactors = Array.isArray(matchData?.factors)
    ? matchData.factors
        .filter((f) => f && f.available === true && f.score !== null && f.score !== undefined)
        .map((f) => ({
          key: f.key,
          label: FACTOR_LABELS[f.key] || f.key,
          weight: f.weight,
          score: f.score,
        }))
    : [
        { key: "skills", label: FACTOR_LABELS.skills, weight: 35, score: matchData?.skills_score ?? 0 },
        { key: "experience", label: FACTOR_LABELS.experience, weight: 20, score: matchData?.experience_score ?? 0 },
        { key: "role", label: FACTOR_LABELS.role, weight: 15, score: matchData?.role_score ?? 0 },
        { key: "projects", label: FACTOR_LABELS.projects, weight: 10, score: matchData?.project_score ?? 0 },
        { key: "location", label: FACTOR_LABELS.location, weight: 10, score: matchData?.location_score ?? 0 },
        ...(matchData?.education_score !== null && matchData?.education_score !== undefined
          ? [{ key: "education", label: FACTOR_LABELS.education, weight: 5, score: matchData.education_score }]
          : []),
        ...(matchData?.work_mode_score !== null && matchData?.work_mode_score !== undefined
          ? [{ key: "work_mode", label: FACTOR_LABELS.work_mode, weight: 5, score: matchData.work_mode_score }]
          : []),
      ];

  const matchedSkills = matchData?.matched_skills || [];
  const missingSkills = matchData?.missing_skills || [];
  const relevantProjects = matchData?.relevant_projects || [];
  const relevantExperience = matchData?.relevant_experience || [];

  // Finding #6: Only display genuine education evidence if present; never infer from experience_level
  const realEducationEvidence =
    matchData?.education ||
    matchData?.education_certification_relevance?.reason ||
    matchData?.factors?.find((f) => f.key === "education")?.evidence ||
    null;

  const tier =
    overallScore >= 80
      ? "High Match"
      : overallScore >= 60
      ? "Strong Match"
      : overallScore >= 40
      ? "Moderate Match"
      : overallScore > 0
      ? "Low Match"
      : "Not Calculated";

  return (
    <aside className="job-fit-sidebar" aria-label="Job Match and Fit Analysis">
      <div className="card fit-panel-card">
        {/* Header with Score & Actions */}
        <div className="fit-panel-header">
          <div>
            <span className="section-eyebrow">YOUR FIT ANALYSIS</span>
            <div className="fit-score-display">
              <span className="fit-score-number font-mono">{overallScore}%</span>
              <span className={`fit-score-badge ${overallScore >= 70 ? "high" : ""}`}>
                {tier}
              </span>
            </div>
          </div>

          <div className="fit-panel-header-actions" style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
            {onAnalyzeResume && (
              <button
                type="button"
                className="btn btn-secondary btn-sm fit-analyze-btn"
                onClick={onAnalyzeResume}
                title="Evaluate an uploaded resume directly against this job"
                aria-label="Analyze Resume"
              >
                <FileSearch size={14} aria-hidden="true" />
                <span>Analyze Resume</span>
              </button>
            )}
            <button
              type="button"
              className="btn btn-ghost btn-sm fit-recalc-btn"
              onClick={onRecalculate}
              disabled={loading}
              title="Recalculate match score against your profile"
              aria-label="Recalculate match score"
            >
              <RefreshCw size={14} className={loading ? "spin" : ""} aria-hidden="true" />
              <span>{loading ? "Calculating..." : "Recalculate"}</span>
            </button>
          </div>
        </div>

        {/* Fit Factors Breakdown */}
        <div className="fit-factors-section">
          <h3 className="fit-subheading">Fit Factors Breakdown</h3>
          <div className="fit-factors-bars">
            {displayFactors.map((factor) => (
              <FactorBar
                key={factor.key}
                label={factor.label}
                weight={factor.weight != null ? `${factor.weight}%` : ""}
                value={factor.score}
              />
            ))}
          </div>
        </div>

        {/* Matching Skills */}
        <div className="fit-skills-section match-group">
          <div className="fit-section-title-row">
            <h3 className="fit-subheading text-success">
              <CheckCircle2 size={16} aria-hidden="true" />
              <span>Matching Skills ({matchedSkills.length})</span>
            </h3>
          </div>
          {!hasAnalysis ? (
            <p className="text-secondary text-xs">
              Match analysis isn't available yet.
            </p>
          ) : matchedSkills.length > 0 ? (
            <div className="skills-chips-wrap">
              {matchedSkills.map((s) => (
                <span key={s} className="skill-chip match">
                  ✓ {s}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-secondary text-xs">
              No direct skill overlap detected yet. Add relevant tools to your Profile or Master Resume.
            </p>
          )}
        </div>

        {/* Missing Skills (Finding #5 Fix: Do not claim no skill gaps when analysis hasn't run) */}
        <div className="fit-skills-section missing-group">
          <div className="fit-section-title-row">
            <h3 className="fit-subheading text-warning">
              <AlertTriangle size={16} aria-hidden="true" />
              <span>Skills to Strengthen ({missingSkills.length})</span>
            </h3>
          </div>
          {!hasAnalysis ? (
            <p className="text-secondary text-xs">
              Match analysis isn't available yet. Run a match or analyze an uploaded resume to evaluate skill gaps.
            </p>
          ) : missingSkills.length > 0 ? (
            <div className="skills-chips-wrap">
              {missingSkills.map((s) => (
                <span key={s} className="skill-chip missing">
                  ⚠ {s}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-success text-xs font-medium">
              No critical skill gaps detected for this role!
            </p>
          )}
        </div>

        {/* Aligned Projects, Experience & Education Evidence (Finding #6 Fix: No invented evidence) */}
        <div className="fit-aligned-history-section">
          <h3 className="fit-subheading">Aligned Profile Evidence</h3>
          {relevantProjects.length > 0 && (
            <div className="aligned-evidence-item">
              <div className="evidence-header">
                <FolderGit2 size={14} className="text-accent" aria-hidden="true" />
                <span>Project Fit:</span>
              </div>
              <p className="evidence-text">{relevantProjects.join(", ")}</p>
            </div>
          )}
          {relevantExperience.length > 0 && (
            <div className="aligned-evidence-item">
              <div className="evidence-header">
                <Briefcase size={14} className="text-accent" aria-hidden="true" />
                <span>Experience Fit:</span>
              </div>
              <p className="evidence-text">{relevantExperience.join(", ")}</p>
            </div>
          )}
          <div className="aligned-evidence-item">
            <div className="evidence-header">
              <GraduationCap size={14} className="text-accent" aria-hidden="true" />
              <span>Education Fit:</span>
            </div>
            <p className={`evidence-text ${!realEducationEvidence ? "text-muted" : ""}`}>
              {realEducationEvidence || "Education fit not assessed."}
            </p>
          </div>
        </div>

        {/* Copilot Next Action Prompt */}
        <div className="fit-copilot-cta-box">
          <div className="copilot-cta-text">
            <Sparkles size={16} className="text-accent" aria-hidden="true" />
            <p className="text-xs text-secondary">
              Tailoring adjusts your resume bullet points and keywords specifically for this job description.
            </p>
          </div>
          <button
            type="button"
            className="btn btn-primary btn-sm btn-block"
            onClick={onTailor}
          >
            <Sparkles size={14} aria-hidden="true" />
            <span>Tailor Resume for this Role</span>
          </button>
        </div>

        {/* Expandable "How this score works" */}
        <div className="fit-explainer-accordion">
          <button
            type="button"
            className="fit-explainer-toggle"
            onClick={() => setShowExplainer((prev) => !prev)}
            aria-expanded={showExplainer}
          >
            <HelpCircle size={14} aria-hidden="true" />
            <span>How this score works</span>
            {showExplainer ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>

          {showExplainer && (
            <div className="fit-explainer-content">
              <p className="text-xs text-secondary">
                CareerPilot computes your overall fit using a weighted, dynamically normalized set of profile and job factors:
              </p>
              <ul className="explainer-list text-xs">
                <li><strong>Skills:</strong> Matches your declared skills against required technologies.</li>
                <li><strong>Experience:</strong> Evaluates role history and experience depth.</li>
                <li><strong>Role Alignment:</strong> Measures title overlap and career trajectory compatibility.</li>
                <li><strong>Projects:</strong> Compares project technologies and descriptions against job requirements.</li>
                <li><strong>Location:</strong> Evaluates regional compatibility and remote work alignment.</li>
                <li><strong>Education & Work Mode:</strong> Dynamically evaluated when specific requirements (degrees, certifications, remote/hybrid mode) are specified.</li>
              </ul>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
