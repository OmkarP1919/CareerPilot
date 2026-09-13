import { useState, useRef, useEffect } from "react";
import { Link } from "react-router-dom";
import {
  Building2,
  MapPin,
  Calendar,
  Clock,
  Sparkles,
  ChevronRight,
  Trash2,
  CheckCircle2,
  ChevronDown,
} from "lucide-react";
import {
  PIPELINE_STATUSES,
  STATUS_LABELS,
  STATUS_VARIANTS,
  getNextStatus,
  formatFriendlyDate,
} from "./pipelineUtils";

export default function PipelineCard({
  application,
  job,
  onOpenDetail,
  onUpdateStatus,
  onDelete,
  isUpdating = false,
}) {
  const [statusMenuOpen, setStatusMenuOpen] = useState(false);
  const statusMenuRef = useRef(null);

  const currentStatus = application.status || "Saved";
  const statusVariant = STATUS_VARIANTS[currentStatus] || "saved";
  const displayStatus = STATUS_LABELS[currentStatus] || currentStatus;
  const nextStatus = getNextStatus(currentStatus);

  const roleTitle = application.job_title || job?.title || "Role Title";
  const companyName = application.job_company || application.company_name || job?.company || "Company";
  const location = job?.location || application.location;
  const appliedDate = application.application_date || application.created_at;
  const updatedDate = application.updated_at || application.created_at;

  // Genuine match score ONLY if present on application or job object
  const genuineScore =
    typeof application.match_score === "number"
      ? application.match_score
      : typeof job?.match_score === "number"
      ? job.match_score
      : null;

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event) {
      if (statusMenuRef.current && !statusMenuRef.current.contains(event.target)) {
        setStatusMenuOpen(false);
      }
    }
    if (statusMenuOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [statusMenuOpen]);

  const handleSelectStatus = (newStatus) => {
    setStatusMenuOpen(false);
    if (newStatus !== currentStatus) {
      onUpdateStatus(application.id, newStatus);
    }
  };

  return (
    <article className="pipeline-card" aria-labelledby={`app-title-${application.id}`}>
      {/* Top Row: Company & Status Badge */}
      <div className="pipeline-card-top">
        <div className="pipeline-card-company-wrap">
          <span className="pipeline-card-company-icon">
            <Building2 size={14} aria-hidden="true" />
          </span>
          <span className="pipeline-card-company">{companyName}</span>
        </div>

        {/* Status Dropdown Trigger */}
        <div className="pipeline-status-trigger-wrap" ref={statusMenuRef}>
          <button
            type="button"
            className={`pipeline-status-badge status-${statusVariant}`}
            onClick={() => setStatusMenuOpen(!statusMenuOpen)}
            aria-expanded={statusMenuOpen}
            aria-label={`Current status: ${displayStatus}. Click to change status`}
            disabled={isUpdating}
          >
            <span>{displayStatus}</span>
            <ChevronDown size={12} aria-hidden="true" />
          </button>

          {statusMenuOpen && (
            <div className="pipeline-status-menu" role="menu">
              <div className="pipeline-status-menu-header">Change Status</div>
              {PIPELINE_STATUSES.map((st) => (
                <button
                  key={st}
                  type="button"
                  className={`pipeline-status-menu-item ${st === currentStatus ? "active" : ""}`}
                  role="menuitem"
                  onClick={() => handleSelectStatus(st)}
                >
                  <span className={`status-dot dot-${STATUS_VARIANTS[st]}`} />
                  <span>{STATUS_LABELS[st]}</span>
                  {st === currentStatus && <CheckCircle2 size={13} className="menu-check text-success" />}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Role Title */}
      <h3 id={`app-title-${application.id}`} className="pipeline-card-role">
        {application.job_id ? (
          <Link to={`/discover/${application.job_id}`} className="pipeline-card-role-link">
            {roleTitle}
          </Link>
        ) : (
          <span>{roleTitle}</span>
        )}
      </h3>

      {/* Metadata: Location, Salary, Fit Score */}
      <div className="pipeline-card-meta">
        {location && (
          <span className="pipeline-meta-item">
            <MapPin size={13} aria-hidden="true" />
            <span>{location}</span>
          </span>
        )}
        {genuineScore !== null && (
          <span className="pipeline-meta-item score-badge">
            <Sparkles size={12} aria-hidden="true" />
            <span>{genuineScore}% Match</span>
          </span>
        )}
      </div>

      {/* Notes preview if present */}
      {application.notes && (
        <p className="pipeline-card-notes">
          {application.notes.length > 80 ? `${application.notes.slice(0, 80)}…` : application.notes}
        </p>
      )}

      {/* Dates Footer */}
      <div className="pipeline-card-dates">
        {appliedDate && (
          <span className="pipeline-date-item" title="Applied Date">
            <Calendar size={12} aria-hidden="true" />
            <span>Applied {formatFriendlyDate(appliedDate)}</span>
          </span>
        )}
        {updatedDate && (
          <span className="pipeline-date-item text-muted" title="Last Updated">
            <Clock size={12} aria-hidden="true" />
            <span>Updated {formatFriendlyDate(updatedDate)}</span>
          </span>
        )}
      </div>

      {/* Actions Row */}
      <div className="pipeline-card-actions">
        {nextStatus && (
          <button
            type="button"
            className="btn btn-secondary btn-sm pipeline-advance-btn"
            onClick={() => onUpdateStatus(application.id, nextStatus)}
            disabled={isUpdating}
            title={`Advance to ${STATUS_LABELS[nextStatus]}`}
            aria-label={`Advance application status to ${STATUS_LABELS[nextStatus]}`}
          >
            <span>Advance to {STATUS_LABELS[nextStatus]}</span>
            <ChevronRight size={14} aria-hidden="true" />
          </button>
        )}

        <div className="pipeline-actions-secondary">
          <button
            type="button"
            className="btn btn-ghost btn-sm pipeline-detail-btn"
            onClick={() => onOpenDetail(application)}
            aria-label={`View details for ${roleTitle} at ${companyName}`}
          >
            View Details
          </button>

          <button
            type="button"
            className="btn btn-ghost btn-icon btn-sm text-danger pipeline-delete-btn"
            onClick={() => onDelete(application.id)}
            title="Remove from pipeline"
            aria-label={`Remove application for ${roleTitle} at ${companyName}`}
          >
            <Trash2 size={15} aria-hidden="true" />
          </button>
        </div>
      </div>
    </article>
  );
}
