import { useState } from "react";
import { Sparkles, Check, Loader2 } from "lucide-react";
import Modal from "../Modal";

export default function ProfileResumeSyncModal({
  isOpen,
  onClose,
  diff,
  resumeName = "Master Resume",
  onConfirmSync,
}) {
  const [syncing, setSyncing] = useState(false);

  if (!isOpen) return null;

  const { counts, totalItems, hasChanges } = diff || {
    counts: {},
    totalItems: 0,
    hasChanges: false,
  };

  const handleConfirm = async () => {
    setSyncing(true);
    try {
      await onConfirmSync();
      onClose();
    } finally {
      setSyncing(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={syncing ? () => {} : onClose}
      title="Sync Profile from Resume"
    >
      <div className="profile-sync-modal-body">
        <div className="profile-sync-header-box">
          <div className="profile-sync-badge">
            <Sparkles size={14} aria-hidden="true" />
            <span>Structured Data Sync</span>
          </div>
          <p className="text-secondary text-sm">
            Review the information extracted from <strong>{resumeName}</strong>. Only missing information will be added; existing profile details will remain untouched.
          </p>
        </div>

        {!hasChanges ? (
          <div className="profile-sync-no-changes">
            <Check size={20} className="text-success" aria-hidden="true" />
            <p className="text-sm">
              Your profile already contains all skills, experiences, and education found in this resume. No new items needed!
            </p>
          </div>
        ) : (
          <div className="profile-sync-summary-grid">
            {counts.skills > 0 && (
              <div className="profile-sync-item">
                <span className="sync-item-count">{counts.skills}</span>
                <span className="sync-item-label">New Skills</span>
              </div>
            )}
            {counts.experiences > 0 && (
              <div className="profile-sync-item">
                <span className="sync-item-count">{counts.experiences}</span>
                <span className="sync-item-label">Work Experiences</span>
              </div>
            )}
            {counts.projects > 0 && (
              <div className="profile-sync-item">
                <span className="sync-item-count">{counts.projects}</span>
                <span className="sync-item-label">Featured Projects</span>
              </div>
            )}
            {counts.education > 0 && (
              <div className="profile-sync-item">
                <span className="sync-item-count">{counts.education}</span>
                <span className="sync-item-label">Education Records</span>
              </div>
            )}
            {counts.certifications > 0 && (
              <div className="profile-sync-item">
                <span className="sync-item-count">{counts.certifications}</span>
                <span className="sync-item-label">Certifications</span>
              </div>
            )}
            {counts.location > 0 && (
              <div className="profile-sync-item">
                <span className="sync-item-count">1</span>
                <span className="sync-item-label">Current Base Location</span>
              </div>
            )}
          </div>
        )}

        {hasChanges && (
          <div className="profile-sync-detail-preview">
            {diff.toAdd.skills.length > 0 && (
              <div className="sync-detail-group">
                <span className="sync-detail-title">Skills to be added:</span>
                <div className="sync-tags-wrap">
                  {diff.toAdd.skills.slice(0, 10).map((s) => (
                    <span key={s.name} className="skill-chip-sm">
                      {s.name}
                    </span>
                  ))}
                  {diff.toAdd.skills.length > 10 && (
                    <span className="text-xs text-muted">+{diff.toAdd.skills.length - 10} more</span>
                  )}
                </div>
              </div>
            )}

            {diff.toAdd.experiences.length > 0 && (
              <div className="sync-detail-group">
                <span className="sync-detail-title">Experience to be added:</span>
                <ul className="sync-simple-list">
                  {diff.toAdd.experiences.map((exp, idx) => (
                    <li key={idx}>
                      <strong>{exp.role}</strong> at {exp.company}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        <div className="profile-sync-actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onClose}
            disabled={syncing}
          >
            Cancel
          </button>
          {hasChanges && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleConfirm}
              disabled={syncing}
            >
              {syncing ? (
                <>
                  <Loader2 size={16} className="animate-spin" aria-hidden="true" />
                  <span>Adding {totalItems} Items...</span>
                </>
              ) : (
                <>
                  <Check size={16} aria-hidden="true" />
                  <span>Add {totalItems} Items to Profile</span>
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </Modal>
  );
}
