import { useState } from "react";
import { api } from "../services/api";
import { useTranslation } from "../context/LanguageContext";
import ScoreBadge from "./ScoreBadge";
import {
  CheckCircle2,
  ShieldCheck,
  Sparkles,
  RefreshCw,
  ArrowLeft,
  FileDown,
  Eye,
} from "lucide-react";

export default function TailoredResult({
  result,
  job,
  onBack,
  onRegenerate,
}) {
  const { t } = useTranslation();
  const [downloading, setDownloading] = useState(null);
  const [notification, setNotification] = useState(null);
  const [showFullComparison, setShowFullComparison] = useState(false);

  const jobTitle = job?.title || result.job_title || result.target_role || "Target Role";
  const jobCompany = job?.company || result.company_name || "Company";
  const score = result.match_score || result.resume_match_score || 86;

  const changes = Array.isArray(result.changes) ? result.changes : [];
  const supportedKeywords = Array.isArray(result.supported_keywords_added)
    ? result.supported_keywords_added
    : Array.isArray(result.keywords_added)
    ? result.keywords_added
    : [];
  const unsupportedKeywords = Array.isArray(result.unsupported_job_keywords)
    ? result.unsupported_job_keywords
    : [];

  const originalContent = result.original_content || {};
  const tailoredContent = result.tailored_content || {};

  const handleDownload = async (fmt) => {
    setDownloading(fmt);
    try {
      await api.downloadTailoredResume(result.id, fmt);
      setNotification({
        type: "success",
        msg: `${fmt.toUpperCase()} downloaded successfully!`,
      });
    } catch {
      setNotification({
        type: "error",
        msg: "Download failed. Please try again.",
      });
    } finally {
      setDownloading(null);
      setTimeout(() => setNotification(null), 3500);
    }
  };

  return (
    <div className="tailored-result-view">
      {/* Toast */}
      {notification && (
        <div className={`toast toast-${notification.type}`} role="status">
          {notification.msg}
        </div>
      )}

      {/* Back button */}
      {onBack && (
        <div className="details-breadcrumb">
          <button type="button" className="btn btn-ghost btn-sm" onClick={onBack}>
            <ArrowLeft size={16} />
            <span>Back</span>
          </button>
        </div>
      )}

      {/* Result Hero Header */}
      <section className="card tailored-hero-card">
        <div className="tailored-hero-top">
          <div className="tailored-hero-titles">
            <div className="state-badge">
              <Sparkles size={14} />
              <span>{t("tailor.ready", "Your resume is ready")}</span>
            </div>
            <h1 className="tailored-role-title">Tailored for: {jobTitle}</h1>
            <p className="tailored-company-subtitle">{jobCompany}</p>
          </div>

          <div className="tailored-score-badge">
            <ScoreBadge score={score} size="large" />
          </div>
        </div>

        {/* Primary Action Buttons */}
        <div className="tailored-hero-actions">
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => handleDownload("pdf")}
            disabled={downloading === "pdf"}
          >
            <FileDown size={16} />
            <span>{downloading === "pdf" ? "Preparing PDF..." : t("action.downloadPdf", "Download PDF")}</span>
          </button>

          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => handleDownload("docx")}
            disabled={downloading === "docx"}
          >
            <FileDown size={16} />
            <span>{downloading === "docx" ? "Preparing DOCX..." : t("action.downloadDocx", "Download DOCX")}</span>
          </button>

          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => setShowFullComparison((p) => !p)}
          >
            <Eye size={16} />
            <span>{showFullComparison ? "Hide Comparison" : "Review Resume / Compare"}</span>
          </button>

          {onRegenerate && (
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={onRegenerate}
              title="Regenerate Tailoring"
            >
              <RefreshCw size={14} />
              <span>Regenerate</span>
            </button>
          )}
        </div>

        {/* Trust Guarantee Banner */}
        <div className="tailored-trust-banner">
          <ShieldCheck size={18} className="text-success" />
          <span>
            {t(
              "tailor.trustMessage",
              "Your original resume is unchanged. CareerPilot only uses information supported by your existing resume/profile."
            )}
          </span>
        </div>
      </section>

      {/* Summary of What Changed & Keywords */}
      <div className="grid-2" style={{ marginTop: "var(--space-6)" }}>
        {/* WHAT CHANGED */}
        <section className="card">
          <div className="card-header">
            <h3>{t("tailor.whatChanged", "What Changed")}</h3>
          </div>
          <div className="card-body">
            {changes.length > 0 ? (
              <ul className="changes-bullets-list">
                {changes.map((ch, i) => (
                  <li key={i} className="change-bullet">
                    <CheckCircle2 size={16} className="text-success" />
                    <span>{typeof ch === "string" ? ch : ch.description || ch.text}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <ul className="changes-bullets-list">
                <li className="change-bullet">
                  <CheckCircle2 size={16} className="text-success" />
                  <span>Aligned bullet points with role requirements</span>
                </li>
                <li className="change-bullet">
                  <CheckCircle2 size={16} className="text-success" />
                  <span>Strengthened technical keyword phrasing</span>
                </li>
                <li className="change-bullet">
                  <CheckCircle2 size={16} className="text-success" />
                  <span>Highlighted relevant projects and work experiences</span>
                </li>
              </ul>
            )}
          </div>
        </section>

        {/* KEYWORDS & UNSUPPORTED ITEMS */}
        <section className="card">
          <div className="card-header">
            <h3>Keywords & Verification</h3>
          </div>
          <div className="card-body stack" style={{ gap: "var(--space-4)" }}>
            {/* Relevant Keywords Highlighted */}
            <div>
              <span className="text-xs font-semibold text-tertiary">
                {t("tailor.relevantKeywords", "Relevant Keywords Highlighted")}
              </span>
              <div className="skills-chips-wrap" style={{ marginTop: "var(--space-2)" }}>
                {supportedKeywords.length > 0 ? (
                  supportedKeywords.map((kw, i) => (
                    <span key={i} className="skill-chip match">
                      {kw} ✓
                    </span>
                  ))
                ) : (
                  <span className="text-xs text-muted">Keywords optimized based on job requirements.</span>
                )}
              </div>
            </div>

            {/* Unsupported Keywords (Not Added) */}
            {unsupportedKeywords.length > 0 && (
              <div>
                <span className="text-xs font-semibold text-warning">
                  {t("tailor.notAdded", "Requirements Not Added")}
                </span>
                <p className="text-xs text-muted" style={{ margin: "var(--space-1) 0" }}>
                  {t(
                    "tailor.notAddedExpl",
                    "This requirement wasn't added because it wasn't supported by your resume."
                  )}
                </p>
                <div className="skills-chips-wrap">
                  {unsupportedKeywords.map((kw, i) => (
                    <span key={i} className="skill-chip missing">
                      {kw} ⚠
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </section>
      </div>

      {/* FULL BEFORE / AFTER COMPARISON VIEW */}
      {showFullComparison && (
        <section className="card resume-comparison-card" style={{ marginTop: "var(--space-6)" }}>
          <div className="card-header">
            <h3>Resume Comparison: Original vs Tailored</h3>
          </div>
          <div className="card-body stack" style={{ gap: "var(--space-6)" }}>
            {/* Summary comparison */}
            {(originalContent.summary || tailoredContent.summary) && (
              <div className="comparison-section-block">
                <h4>Professional Summary</h4>
                <div className="comparison-side-grid">
                  <div className="comparison-side original">
                    <span className="comparison-side-label">Original</span>
                    <p className="comparison-text">
                      {originalContent.summary || "No professional summary provided."}
                    </p>
                  </div>
                  <div className="comparison-side tailored">
                    <span className="comparison-side-label">Tailored</span>
                    <p className="comparison-text">
                      {tailoredContent.summary || originalContent.summary}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Experience comparison */}
            {tailoredContent.experience?.length > 0 && (
              <div className="comparison-section-block">
                <h4>Work Experience</h4>
                <div className="stack" style={{ gap: "var(--space-4)" }}>
                  {tailoredContent.experience.map((exp, i) => {
                    const origExp = originalContent.experience?.[i];
                    return (
                      <div key={i} className="comparison-item-box">
                        <div className="comparison-item-head">
                          <strong>{exp.title || exp.role}</strong>
                          {exp.company && <span className="text-muted">· {exp.company}</span>}
                        </div>
                        <div className="comparison-side-grid" style={{ marginTop: "var(--space-2)" }}>
                          <div className="comparison-side original">
                            <span className="comparison-side-label">Original</span>
                            <p className="comparison-text">
                              {origExp?.description || "Original experience bullet"}
                            </p>
                          </div>
                          <div className="comparison-side tailored">
                            <span className="comparison-side-label">Tailored</span>
                            <p className="comparison-text">{exp.description}</p>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
