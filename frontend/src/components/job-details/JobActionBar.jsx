import { Sparkles, FileText, ExternalLink, Bookmark, Check, FileSearch } from "lucide-react";
import { useTranslation } from "../../context/LanguageContext";

const PIPELINE_STATUSES = [
  { value: "Saved", label: "Saved in Pipeline" },
  { value: "Applied", label: "Applied" },
  { value: "Interview", label: "Interviewing" },
  { value: "Offer", label: "Offer Received" },
  { value: "Rejected", label: "Archived / Rejected" },
];

export default function JobActionBar({
  job,
  application,
  savingApp,
  onTailor,
  onCoverLetter,
  onAnalyzeResume,
  onUpdateStatus,
  isStickyMobile = false,
}) {
  const { t } = useTranslation();
  const currentStatus = application?.status || "Saved";
  const externalUrl = job.application_url || job.url;

  if (isStickyMobile) {
    return (
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
            title={t("jobDetail.applyExternal", "Apply Externally")}
            aria-label={t("jobDetail.applyExternal", "Apply Externally")}
          >
            <ExternalLink size={18} />
          </a>
        )}
      </aside>
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
              <option key={st.value} value={st.value}>
                {st.label}
              </option>
            ))}
          </select>
        </div>
      </div>
    </section>
  );
}
