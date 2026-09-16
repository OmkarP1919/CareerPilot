import { useState, useEffect } from "react";
import { Sparkles, FileText, ExternalLink, Bookmark, Check, FileSearch, MoreHorizontal, X } from "lucide-react";
import { useTranslation } from "../../context/LanguageContext";
import { PIPELINE_STATUSES, STATUS_LABELS } from "../pipeline/pipelineUtils";

export default function JobActionBar({
  job,
  application,
  savingApp,
  onTailor,
  onCoverLetter,
  onAnalyzeResume,
  onUpdateStatus,
  onExternalApply,
  isStickyMobile = false,
}) {
  const { t } = useTranslation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const currentStatus = application?.status || "Saved";
  const externalUrl = job.application_url || job.url;

  // Keyboard accessibility for mobile sheet
  useEffect(() => {
    if (!mobileMenuOpen) return;
    const handleKeyDown = (e) => {
      if (e.key === "Escape") setMobileMenuOpen(false);
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [mobileMenuOpen]);

  const handleExternalApplyClick = (e) => {
    if (externalUrl) {
      if (onExternalApply) {
        e.preventDefault();
        onExternalApply(job, externalUrl);
      }
    }
  };

  if (isStickyMobile) {
    return (
      <>
        <aside className="job-details-sticky-actions" aria-label="Quick Actions">
          <button
            type="button"
            className="btn btn-secondary btn-icon status-quick-toggle"
            onClick={() => {
              const nextStatus = currentStatus === "Saved" ? "Applied" : "Saved";
              onUpdateStatus(nextStatus);
            }}
            disabled={savingApp}
            title={currentStatus ? `Status: ${currentStatus}` : "Save to Pipeline"}
            aria-label={currentStatus ? `Current Status: ${currentStatus}` : "Save to Pipeline"}
          >
            {currentStatus === "Applied" || currentStatus === "Interview" || currentStatus === "Offer" ? (
              <Check size={18} className="text-success" />
            ) : (
              <Bookmark size={18} className={currentStatus === "Saved" ? "text-accent" : ""} />
            )}
          </button>

          <button
            type="button"
            className="btn btn-primary job-sticky-primary-btn"
            onClick={onTailor}
          >
            <Sparkles size={16} aria-hidden="true" />
            <span>{t("action.tailorResume", "Tailor Resume")}</span>
          </button>

          {externalUrl && (
            <a
              href={externalUrl}
              target="_blank"
              rel="noreferrer"
              className="btn btn-ghost btn-icon"
              onClick={handleExternalApplyClick}
              title={t("jobDetail.applyExternal", "Apply Externally")}
              aria-label={t("jobDetail.applyExternal", "Apply Externally")}
            >
              <ExternalLink size={18} />
            </a>
          )}

          <button
            type="button"
            className="btn btn-ghost btn-icon job-sticky-more-btn"
            onClick={() => setMobileMenuOpen(true)}
            aria-label="More actions"
            aria-expanded={mobileMenuOpen}
            title="More actions"
          >
            <MoreHorizontal size={18} />
          </button>
        </aside>

        {mobileMenuOpen && (
          <div
            className="mobile-action-sheet-overlay"
            onClick={() => setMobileMenuOpen(false)}
            role="dialog"
            aria-modal="true"
            aria-label="Additional Job Actions"
          >
            <div className="mobile-action-sheet" onClick={(e) => e.stopPropagation()}>
              <div className="mobile-sheet-handle" />
              <div className="mobile-sheet-header">
                <span className="mobile-sheet-title">Job Actions</span>
                <button
                  type="button"
                  className="btn btn-ghost btn-icon btn-sm"
                  onClick={() => setMobileMenuOpen(false)}
                  aria-label="Close menu"
                >
                  <X size={18} />
                </button>
              </div>

              <div className="mobile-sheet-actions-list">
                {onCoverLetter && (
                  <button
                    type="button"
                    className="mobile-sheet-action-btn"
                    onClick={() => {
                      setMobileMenuOpen(false);
                      onCoverLetter();
                    }}
                  >
                    <FileText size={18} className="text-accent" />
                    <span>{t("cover.shortTitle", "Cover Letter")}</span>
                  </button>
                )}

                {onAnalyzeResume && (
                  <button
                    type="button"
                    className="mobile-sheet-action-btn"
                    onClick={() => {
                      setMobileMenuOpen(false);
                      onAnalyzeResume();
                    }}
                  >
                    <FileSearch size={18} className="text-accent" />
                    <span>{t("action.analyzeResume", "Analyze Resume")}</span>
                  </button>
                )}

                {externalUrl && (
                  <button
                    type="button"
                    className="mobile-sheet-action-btn"
                    onClick={(e) => {
                      setMobileMenuOpen(false);
                      handleExternalApplyClick(e);
                    }}
                  >
                    <ExternalLink size={18} className="text-accent" />
                    <span>{t("jobDetail.applyExternal", "Apply Externally")}</span>
                  </button>
                )}

                <div className="mobile-sheet-status-section" style={{ marginTop: "var(--space-2)", paddingTop: "var(--space-2)", borderTop: "1px solid var(--border-light)" }}>
                  <label htmlFor="mobile-pipeline-status-select" className="form-label text-xs text-muted" style={{ marginBottom: "var(--space-1)" }}>
                    Pipeline Stage:
                  </label>
                  <select
                    id="mobile-pipeline-status-select"
                    className="status-select"
                    style={{ width: "100%", height: "40px" }}
                    value={currentStatus}
                    onChange={(e) => {
                      onUpdateStatus(e.target.value);
                      setMobileMenuOpen(false);
                    }}
                    disabled={savingApp}
                  >
                    {PIPELINE_STATUSES.map((st) => (
                      <option key={st} value={st}>
                        {STATUS_LABELS[st] || st}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
          </div>
        )}
      </>
    );
  }

  return (
    <section className="job-action-bar card" aria-label="Job Actions">
      <div className="job-action-bar-inner">
        <div className="action-bar-primary-group">
          <button
            type="button"
            className="btn btn-primary btn-lg action-bar-primary-cta"
            onClick={onTailor}
          >
            <Sparkles size={18} aria-hidden="true" />
            <span>{t("action.tailorResume", "Tailor Resume")}</span>
          </button>

          {onAnalyzeResume && (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={onAnalyzeResume}
            >
              <FileSearch size={16} aria-hidden="true" />
              <span>{t("action.analyzeResume", "Analyze Resume")}</span>
            </button>
          )}

          <button
            type="button"
            className="btn btn-secondary"
            onClick={onCoverLetter}
          >
            <FileText size={16} aria-hidden="true" />
            <span>{t("cover.shortTitle", "Cover Letter")}</span>
          </button>

          {externalUrl && (
            <a
              href={externalUrl}
              target="_blank"
              rel="noreferrer"
              className="btn btn-ghost action-bar-external-link"
              onClick={handleExternalApplyClick}
            >
              <span>{t("jobDetail.applyExternal", "Apply Externally")}</span>
              <ExternalLink size={14} aria-hidden="true" />
            </a>
          )}
        </div>

        <div className="action-bar-status-group">
          <label htmlFor="pipeline-status-select" className="status-label">
            Pipeline:
          </label>
          <select
            id="pipeline-status-select"
            className="status-select"
            value={currentStatus}
            onChange={(e) => onUpdateStatus(e.target.value)}
            disabled={savingApp}
          >
            {PIPELINE_STATUSES.map((st) => (
              <option key={st} value={st}>
                {STATUS_LABELS[st] || st}
              </option>
            ))}
          </select>
        </div>
      </div>
    </section>
  );
}
