import { Bookmark, BookmarkCheck, ArrowRight, Loader2, Sparkles, CheckCircle2, Clock, Building2, MapPin, ExternalLink } from "lucide-react";
import ScoreBadge from "../ScoreBadge";
import { formatWorkMode } from "./jobUtils";

export default function JobCard({
  job,
  isSaved = false,
  onToggleSave,
  onViewDetails,
  onExternalApply,
  isMaterializing = false,
  isSaving = false,
}) {
  if (!job) return null;

  const {
    title,
    company,
    location,
    work_mode,
    employment_type,
    salary,
    skills = [],
    match_score,
    fit_summary,
    posted_at,
    freshness,
    source,
  } = job;

  // Format posted date cleanly
  let formattedDate = "";
  if (freshness) {
    formattedDate = freshness;
  } else if (posted_at) {
    try {
      const d = new Date(posted_at);
      if (!isNaN(d.getTime())) {
        formattedDate = d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
      }
    } catch {
      formattedDate = "";
    }
  }

  const handleSaveClick = (e) => {
    e.stopPropagation();
    onToggleSave?.(job);
  };

  const handleDetailsClick = (e) => {
    e.stopPropagation();
    onViewDetails?.(job);
  };

  const externalUrl = job.application_url || job.url;

  const handleExternalApply = (e) => {
    e.stopPropagation();
    if (onExternalApply) {
      onExternalApply(job, externalUrl);
    } else if (externalUrl) {
      window.open(externalUrl, "_blank", "noopener,noreferrer");
    }
  };

  return (
    <article className="unified-job-card card" aria-labelledby={`job-title-${job.canonical_key || job.id}`}>
      <div className="job-card-content">
        {/* Header row: Title + Meta and Score Badge */}
        <div className="job-card-top-row">
          <div className="job-card-title-col">
            {/* Real Match Score Badge ONLY if authentic score > 0 */}
            {typeof match_score === "number" && match_score > 0 && (
              <div className="job-card-score-badge-wrap">
                <ScoreBadge score={match_score} />
              </div>
            )}

            <h3 className="job-card-heading" id={`job-title-${job.canonical_key || job.id}`}>
              <button
                type="button"
                className="job-card-title-link"
                onClick={handleDetailsClick}
                disabled={isMaterializing}
              >
                {title}
              </button>
            </h3>

            <div className="job-card-meta-line">
              <span className="job-company-name">
                <Building2 size={13} className="meta-inline-icon" aria-hidden="true" />
                <span>{company}</span>
              </span>

              {location && (
                <>
                  <span className="meta-sep" aria-hidden="true">•</span>
                  <span className="job-location">
                    <MapPin size={13} className="meta-inline-icon" aria-hidden="true" />
                    <span>{location}</span>
                  </span>
                </>
              )}

              {formatWorkMode(work_mode) && (
                <>
                  <span className="meta-sep" aria-hidden="true">•</span>
                  <span className="job-work-mode">{formatWorkMode(work_mode)}</span>
                </>
              )}

              {employment_type && (
                <>
                  <span className="meta-sep" aria-hidden="true">•</span>
                  <span className="job-employment-type">{employment_type}</span>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Salary line IF available */}
        {salary && (
          <div className="job-card-salary-row">
            <span className="job-salary-tag">{salary}</span>
          </div>
        )}

        {/* Skills pills */}
        {skills && skills.length > 0 && (
          <div className="job-card-skills-row" aria-label="Required skills">
            {skills.slice(0, 6).map((skill, idx) => (
              <span key={`${skill}-${idx}`} className="job-skill-chip">
                {skill}
              </span>
            ))}
            {skills.length > 6 && (
              <span className="job-skill-chip-more">+{skills.length - 6} more</span>
            )}
          </div>
        )}

        {/* Fit insight IF genuine */}
        {fit_summary && (
          <div className="job-card-fit-box">
            <span className="job-fit-text">
              {match_score && match_score >= 70 ? (
                <CheckCircle2 size={14} className="job-fit-icon fit-positive" aria-hidden="true" />
              ) : (
                <Sparkles size={14} className="job-fit-icon fit-accent" aria-hidden="true" />
              )}
              <span>{fit_summary}</span>
            </span>
          </div>
        )}
      </div>

      {/* Action footer */}
      <div className="job-card-footer">
        <div className="job-card-footer-left">
          {formattedDate && (
            <span className="job-posted-time">
              <Clock size={12} className="meta-inline-icon" aria-hidden="true" />
              <span>{formattedDate}</span>
            </span>
          )}
          {source && (
            <span className="job-source-badge" title={`Discovered via ${source}`}>
              {source}
            </span>
          )}
        </div>

        <div className="job-card-actions">
          {externalUrl && (
            <button
              type="button"
              className="btn btn-ghost btn-sm job-card-external-btn"
              onClick={handleExternalApply}
              title="Apply Externally"
              aria-label={`Apply externally for ${title}`}
            >
              <ExternalLink size={14} aria-hidden="true" />
              <span>Apply</span>
            </button>
          )}

          <button
            type="button"
            className={`btn btn-sm ${isSaved ? "btn-secondary" : "btn-ghost"} job-save-btn`}
            onClick={handleSaveClick}
            disabled={isSaving}
            aria-label={isSaved ? "Saved to pipeline" : "Save job"}
            title={isSaved ? "Saved" : "Save to pipeline"}
          >
            {isSaving ? (
              <Loader2 size={15} className="spinner-inline" />
            ) : isSaved ? (
              <BookmarkCheck size={16} className="save-icon-active" />
            ) : (
              <Bookmark size={16} />
            )}
            <span>{isSaved ? "Saved" : "Save"}</span>
          </button>

          <button
            type="button"
            className="btn btn-primary btn-sm job-view-details-btn"
            onClick={handleDetailsClick}
            disabled={isMaterializing}
            aria-label={`View details for ${title}`}
          >
            {isMaterializing ? (
              <>
                <Loader2 size={14} className="spinner-inline" />
                <span>Opening...</span>
              </>
            ) : (
              <>
                <span>View Details</span>
                <ArrowRight size={14} />
              </>
            )}
          </button>
        </div>
      </div>
    </article>
  );
}
