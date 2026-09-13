import { useState } from "react";
import { Link } from "react-router-dom";
import { ExternalLink, FileText, ArrowRight } from "lucide-react";
import {
  PIPELINE_STATUSES,
  STATUS_LABELS,
  STATUS_VARIANTS,
  formatFriendlyDate,
} from "./pipelineUtils";

export default function PipelineOverviewTab({
  application,
  job,
  onUpdateStatus,
  onSaveNotes,
  isSavingNotes = false,
  coverLetter = null,
  onViewCoverLetter,
}) {
  const [notes, setNotes] = useState(application.notes || "");
  const currentStatus = application.status || "Saved";

  const handleNotesSubmit = (e) => {
    e.preventDefault();
    onSaveNotes(notes);
  };

  const externalUrl = job?.application_url || job?.url || application.job_url;

  return (
    <div className="pipeline-tab-panel pipeline-overview-tab">
      {/* Status progression bar */}
      <div className="pipeline-lifecycle-section card">
        <h4 className="pipeline-section-title">Application Status</h4>
        <div className="pipeline-status-selector-grid">
          {PIPELINE_STATUSES.map((st) => {
            const isSelected = st === currentStatus;
            const variant = STATUS_VARIANTS[st];

            return (
              <button
                key={st}
                type="button"
                className={`pipeline-status-choice-btn status-${variant} ${isSelected ? "selected" : ""}`}
                onClick={() => onUpdateStatus(application.id, st)}
                aria-pressed={isSelected}
              >
                <span className={`status-dot dot-${variant}`} />
                <span>{STATUS_LABELS[st]}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Metadata Overview */}
      <div className="pipeline-meta-section card">
        <h4 className="pipeline-section-title">Role & Organization</h4>
        <div className="pipeline-meta-grid">
          <div className="meta-field">
            <span className="meta-field-label">Company</span>
            <span className="meta-field-val">
              {application.job_company || application.company_name || job?.company || "Not specified"}
            </span>
          </div>

          <div className="meta-field">
            <span className="meta-field-label">Target Role</span>
            <span className="meta-field-val">
              {application.job_title || job?.title || "Not specified"}
            </span>
          </div>

          <div className="meta-field">
            <span className="meta-field-label">Location</span>
            <span className="meta-field-val">{job?.location || application.location || "Remote / Unspecified"}</span>
          </div>

          <div className="meta-field">
            <span className="meta-field-label">Date Tracked</span>
            <span className="meta-field-val">{formatFriendlyDate(application.created_at)}</span>
          </div>
        </div>

        {/* Quick Links */}
        <div className="pipeline-detail-links">
          {externalUrl && (
            <a
              href={externalUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-secondary btn-sm"
            >
              <ExternalLink size={14} aria-hidden="true" />
              <span>External Job Posting</span>
            </a>
          )}

          {application.job_id && (
            <Link to={`/discover/${application.job_id}`} className="btn btn-secondary btn-sm">
              <span>View Job Details</span>
              <ArrowRight size={14} aria-hidden="true" />
            </Link>
          )}

          {coverLetter && (
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => onViewCoverLetter && onViewCoverLetter(coverLetter)}
            >
              <FileText size={14} aria-hidden="true" />
              <span>View Cover Letter</span>
            </button>
          )}
        </div>
      </div>

      {/* Notes Form */}
      <form className="pipeline-notes-section card" onSubmit={handleNotesSubmit}>
        <h4 className="pipeline-section-title">Application Notes & Insights</h4>
        <div className="form-group">
          <label htmlFor="pipeline-notes-input" className="sr-only">
            Application Notes
          </label>
          <textarea
            id="pipeline-notes-input"
            className="form-textarea"
            rows={4}
            placeholder="Log recruiter notes, follow-up deadlines, interview impressions, or salary expectations..."
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        </div>
        <div className="pipeline-notes-actions">
          <button
            type="submit"
            className="btn btn-primary btn-sm"
            disabled={isSavingNotes || notes === (application.notes || "")}
          >
            {isSavingNotes ? "Saving Notes..." : "Save Notes"}
          </button>
        </div>
      </form>
    </div>
  );
}
