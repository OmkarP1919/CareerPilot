import { ExternalLink, Check } from "lucide-react";

/**
 * ExternalApplyToast
 *
 * Lightweight, non-blocking toast confirmation displayed after an external
 * application destination has been opened. Never claims the user actually
 * submitted their application off-site; simply asks if they wish to advance
 * the opportunity to "Applied" in their CareerPilot pipeline.
 */
export default function ExternalApplyToast({
  job,
  onConfirm,
  onDismiss,
}) {
  const jobTitle = job?.title || "opportunity";

  return (
    <div
      className="external-apply-toast"
      role="status"
      aria-live="polite"
      aria-label="Track external application status"
    >
      <div className="external-apply-toast-content">
        <div className="external-apply-toast-msg">
          <ExternalLink size={16} className="text-accent flex-shrink-0" aria-hidden="true" />
          <span>
            Application opened. Mark <strong>{jobTitle}</strong> as Applied?
          </span>
        </div>
        <div className="external-apply-toast-actions">
          <button
            type="button"
            className="btn btn-primary btn-sm prompt-confirm-btn"
            onClick={onConfirm}
          >
            <Check size={14} aria-hidden="true" />
            <span>Mark Applied</span>
          </button>
          <button
            type="button"
            className="btn btn-ghost btn-sm prompt-dismiss-btn"
            onClick={onDismiss}
          >
            <span>Not now</span>
          </button>
        </div>
      </div>
    </div>
  );
}
