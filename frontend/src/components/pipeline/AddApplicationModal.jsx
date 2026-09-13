import { useState } from "react";
import { X, Plus, AlertCircle } from "lucide-react";
import { PIPELINE_STATUSES, STATUS_LABELS } from "./pipelineUtils";

export default function AddApplicationModal({
  isOpen,
  onClose,
  onSubmit,
  isSubmitting = false,
}) {
  const [formData, setFormData] = useState({
    title: "",
    company: "",
    status: "Applied",
    location: "",
    application_url: "",
    notes: "",
  });

  const [validationError, setValidationError] = useState(null);

  if (!isOpen) return null;

  const handleChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    if (validationError) setValidationError(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.title.trim()) {
      setValidationError("Role Title is required.");
      return;
    }
    if (!formData.company.trim()) {
      setValidationError("Company Name is required.");
      return;
    }

    try {
      await onSubmit({
        title: formData.title.trim(),
        company: formData.company.trim(),
        status: formData.status,
        location: formData.location.trim() || null,
        application_url: formData.application_url.trim() || null,
        notes: formData.notes.trim() || null,
      });
      // Reset
      setFormData({
        title: "",
        company: "",
        status: "Applied",
        location: "",
        application_url: "",
        notes: "",
      });
      setValidationError(null);
      onClose();
    } catch (err) {
      setValidationError(err?.message || "Failed to create application. Please check your connection.");
    }
  };

  return (
    <div
      className="pipeline-modal-overlay"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isSubmitting) onClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="add-app-modal-title"
    >
      <div className="pipeline-modal card">
        <header className="pipeline-modal-header">
          <div className="modal-header-icon-title">
            <h3 id="add-app-modal-title" className="pipeline-modal-title">
              Add External Application
            </h3>
            <p className="pipeline-modal-subtitle">
              Log a role you found or applied to outside CareerPilot.
            </p>
          </div>
          <button
            type="button"
            className="btn btn-ghost btn-icon"
            onClick={onClose}
            disabled={isSubmitting}
            aria-label="Close dialog"
          >
            <X size={18} aria-hidden="true" />
          </button>
        </header>

        {validationError && (
          <div className="pipeline-modal-error" role="alert">
            <AlertCircle size={15} aria-hidden="true" />
            <span>{validationError}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="pipeline-modal-form">
          {/* Role & Company (Required) */}
          <div className="form-row">
            <div className="form-group" style={{ flex: 1 }}>
              <label htmlFor="add-app-title" className="form-label">
                Role Title <span className="text-danger">*</span>
              </label>
              <input
                id="add-app-title"
                type="text"
                className="form-input"
                placeholder="e.g. Senior Frontend Engineer"
                value={formData.title}
                onChange={(e) => handleChange("title", e.target.value)}
                required
                disabled={isSubmitting}
              />
            </div>

            <div className="form-group" style={{ flex: 1 }}>
              <label htmlFor="add-app-company" className="form-label">
                Company Name <span className="text-danger">*</span>
              </label>
              <input
                id="add-app-company"
                type="text"
                className="form-input"
                placeholder="e.g. Acme Corp"
                value={formData.company}
                onChange={(e) => handleChange("company", e.target.value)}
                required
                disabled={isSubmitting}
              />
            </div>
          </div>

          {/* Status & Location */}
          <div className="form-row">
            <div className="form-group" style={{ flex: 1 }}>
              <label htmlFor="add-app-status" className="form-label">
                Initial Status
              </label>
              <select
                id="add-app-status"
                className="form-select"
                value={formData.status}
                onChange={(e) => handleChange("status", e.target.value)}
                disabled={isSubmitting}
              >
                {PIPELINE_STATUSES.map((st) => (
                  <option key={st} value={st}>
                    {STATUS_LABELS[st]}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group" style={{ flex: 1 }}>
              <label htmlFor="add-app-location" className="form-label">
                Location (optional)
              </label>
              <input
                id="add-app-location"
                type="text"
                className="form-input"
                placeholder="e.g. Remote, San Francisco, CA"
                value={formData.location}
                onChange={(e) => handleChange("location", e.target.value)}
                disabled={isSubmitting}
              />
            </div>
          </div>

          {/* Job URL */}
          <div className="form-group">
            <label htmlFor="add-app-url" className="form-label">
              Posting or Application URL (optional)
            </label>
            <input
              id="add-app-url"
              type="url"
              className="form-input"
              placeholder="https://..."
              value={formData.application_url}
              onChange={(e) => handleChange("application_url", e.target.value)}
              disabled={isSubmitting}
            />
          </div>

          {/* Notes */}
          <div className="form-group">
            <label htmlFor="add-app-notes" className="form-label">
              Initial Notes (optional)
            </label>
            <textarea
              id="add-app-notes"
              className="form-textarea"
              rows={3}
              placeholder="Referrals, salary expectations, interview notes..."
              value={formData.notes}
              onChange={(e) => handleChange("notes", e.target.value)}
              disabled={isSubmitting}
            />
          </div>

          <div className="pipeline-modal-actions">
            <button
              type="button"
              className="btn btn-ghost"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={isSubmitting}
            >
              <Plus size={16} aria-hidden="true" />
              <span>{isSubmitting ? "Adding..." : "Add to Pipeline"}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
