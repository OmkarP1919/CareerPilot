import { useState, useEffect, useCallback } from "react";
import { Plus, Calendar, Trash2, Pencil } from "lucide-react";
import { api } from "../../services/api";
import ConfirmDialog from "../ConfirmDialog";
import {
  INTERVIEW_KINDS,
  INTERVIEW_KIND_LABELS,
  INTERVIEW_STATUSES,
  INTERVIEW_STATUS_LABELS,
  formatDateTime,
  fromLocalInputValue,
  backendToInputValue,
} from "./pipelineUtils";

export default function PipelineInterviewsTab({ applicationId, notify }) {
  const [interviews, setInterviews] = useState(null);
  const [error, setError] = useState(null);
  const [formMode, setFormMode] = useState(null); // null | 'add' | 'edit'
  const [editingInterview, setEditingInterview] = useState(null);
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const [formFields, setFormFields] = useState({
    kind: "technical",
    scheduled_at: "",
    status: "scheduled",
    notes: "",
  });

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await api.getApplicationInterviews(applicationId);
      setInterviews(Array.isArray(data) ? data : []);
    } catch {
      setError("Couldn't load interviews for this application.");
      setInterviews([]);
    }
  }, [applicationId]);

  useEffect(() => {
    load();
  }, [load]);

  const openAdd = () => {
    setFormFields({
      kind: "technical",
      scheduled_at: "",
      status: "scheduled",
      notes: "",
    });
    setEditingInterview(null);
    setFormMode("add");
  };

  const openEdit = (interview) => {
    setFormFields({
      kind: interview.kind || "technical",
      scheduled_at: backendToInputValue(interview.scheduled_at),
      status: interview.status || "scheduled",
      notes: interview.notes || "",
    });
    setEditingInterview(interview);
    setFormMode("edit");
  };

  const closeForm = () => {
    setFormMode(null);
    setEditingInterview(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const isoDate = fromLocalInputValue(formFields.scheduled_at);
    if (!isoDate) {
      notify("Please choose a valid date and time.", "error");
      return;
    }

    setSaving(true);
    try {
      const payload = {
        kind: formFields.kind,
        scheduled_at: isoDate,
        status: formFields.status,
        notes: formFields.notes.trim() || null,
      };

      if (formMode === "edit" && editingInterview) {
        await api.updateApplicationInterview(applicationId, editingInterview.id, payload);
        notify("Interview updated successfully.");
      } else {
        await api.createApplicationInterview(applicationId, payload);
        notify("Interview scheduled.");
      }

      closeForm();
      load();
    } catch (err) {
      notify(err?.message || "Failed to save interview.", "error");
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await api.deleteApplicationInterview(applicationId, deleteTarget.id);
      notify("Interview removed.");
      setDeleteTarget(null);
      load();
    } catch (err) {
      notify(err?.message || "Failed to delete interview.", "error");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="pipeline-tab-panel pipeline-interviews-tab">
      {/* Header with trigger button */}
      <div className="pipeline-tab-panel-header">
        <h4 className="pipeline-section-title">Scheduled Interviews</h4>
        {!formMode && (
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={openAdd}
          >
            <Plus size={14} aria-hidden="true" />
            <span>Schedule Interview</span>
          </button>
        )}
      </div>

      {/* Inline Add / Edit Form */}
      {formMode && (
        <form className="card pipeline-inline-form" onSubmit={handleSubmit}>
          <h4 className="pipeline-section-title">
            {formMode === "edit" ? "Edit Scheduled Interview" : "Schedule New Interview"}
          </h4>

          <div className="form-row">
            <div className="form-group" style={{ flex: 1 }}>
              <label htmlFor="pipeline-interview-kind" className="form-label">
                Format / Kind
              </label>
              <select
                id="pipeline-interview-kind"
                className="form-select"
                value={formFields.kind}
                onChange={(e) => setFormFields((f) => ({ ...f, kind: e.target.value }))}
              >
                {INTERVIEW_KINDS.map((k) => (
                  <option key={k} value={k}>
                    {INTERVIEW_KIND_LABELS[k] || k}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group" style={{ flex: 1 }}>
              <label htmlFor="pipeline-interview-status" className="form-label">
                Status
              </label>
              <select
                id="pipeline-interview-status"
                className="form-select"
                value={formFields.status}
                onChange={(e) => setFormFields((f) => ({ ...f, status: e.target.value }))}
              >
                {INTERVIEW_STATUSES.map((st) => (
                  <option key={st} value={st}>
                    {INTERVIEW_STATUS_LABELS[st] || st}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="pipeline-interview-time" className="form-label">
              Date & Time
            </label>
            <input
              id="pipeline-interview-time"
              type="datetime-local"
              className="form-input"
              value={formFields.scheduled_at}
              onChange={(e) => setFormFields((f) => ({ ...f, scheduled_at: e.target.value }))}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="pipeline-interview-notes" className="form-label">
              Preparation Notes (optional)
            </label>
            <input
              id="pipeline-interview-notes"
              type="text"
              className="form-input"
              placeholder="e.g. System design round with engineering manager"
              value={formFields.notes}
              onChange={(e) => setFormFields((f) => ({ ...f, notes: e.target.value }))}
            />
          </div>

          <div className="pipeline-form-actions">
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={closeForm}
              disabled={saving}
            >
              Cancel
            </button>
            <button type="submit" className="btn btn-primary btn-sm" disabled={saving}>
              {saving
                ? formMode === "edit"
                  ? "Saving Changes..."
                  : "Saving..."
                : formMode === "edit"
                ? "Update Interview"
                : "Save Interview"}
            </button>
          </div>
        </form>
      )}

      {error && <p className="pipeline-panel-error text-danger">{error}</p>}

      {interviews === null ? (
        <div className="pipeline-loading-text text-muted">Loading interviews...</div>
      ) : interviews.length === 0 ? (
        <div className="pipeline-inline-empty card">
          <Calendar size={28} aria-hidden="true" />
          <p>No interviews scheduled yet. Click &ldquo;Schedule Interview&rdquo; above to track upcoming rounds.</p>
        </div>
      ) : (
        <div className="pipeline-interview-cards">
          {interviews.map((iv) => (
            <div key={iv.id} className="card pipeline-interview-card">
              <div className="interview-card-header">
                <span className="interview-kind-tag">
                  {INTERVIEW_KIND_LABELS[iv.kind] || iv.kind}
                </span>
                <span className={`status-badge status-${iv.status}`}>
                  {INTERVIEW_STATUS_LABELS[iv.status] || iv.status}
                </span>
              </div>

              <div className="interview-card-time">
                <Calendar size={14} aria-hidden="true" />
                <span>{formatDateTime(iv.scheduled_at)}</span>
              </div>

              {iv.notes && <p className="interview-card-notes">{iv.notes}</p>}

              <div className="interview-card-actions">
                <button
                  type="button"
                  className="btn btn-ghost btn-sm pipeline-interview-edit-btn"
                  onClick={() => openEdit(iv)}
                  aria-label={`Edit ${iv.kind} interview`}
                >
                  <Pencil size={13} aria-hidden="true" />
                  <span>Edit</span>
                </button>
                <button
                  type="button"
                  className="btn btn-ghost btn-icon btn-sm text-danger"
                  onClick={() => setDeleteTarget(iv)}
                  title="Remove interview"
                  aria-label="Remove interview"
                >
                  <Trash2 size={14} aria-hidden="true" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Delete Confirmation */}
      <ConfirmDialog
        isOpen={Boolean(deleteTarget)}
        onClose={() => !deleting && setDeleteTarget(null)}
        onConfirm={confirmDelete}
        title="Delete Interview"
        message="Are you sure you want to remove this scheduled interview?"
        confirmLabel="Delete"
        cancelLabel="Cancel"
        destructive
        loading={deleting}
      />
    </div>
  );
}
