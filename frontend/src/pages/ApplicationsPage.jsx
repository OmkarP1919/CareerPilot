import { useState, useEffect, useCallback, useRef } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import { useTranslation } from "../context/LanguageContext";
import EmptyState from "../components/EmptyState";
import { SkeletonCard, SkeletonList } from "../components/Skeleton";
import Modal from "../components/Modal";
import CoverLetterModal from "../components/CoverLetterModal";
import {
  Layers,
  Plus,
  Trash2,
  ArrowRight,
  FileText,
  MessageSquare,
  CalendarClock,
  Link2,
  CloudUpload,
  Pencil,
} from "lucide-react";

const PIPELINE_STAGES = ["Saved", "Applied", "Interview", "Offer"];

const USER_EVENT_TYPES = ["note_added", "milestone", "other"];

const EVENT_LABELS = {
  created: "Created",
  status_changed: "Status Changed",
  note_added: "Note Added",
  resume_attached: "Resume Attached",
  document_attached: "Document Attached",
  interview_scheduled: "Interview Scheduled",
  interview_completed: "Interview Completed",
  milestone: "Milestone",
  other: "Other",
};

const INTERVIEW_KINDS = [
  "phone",
  "video",
  "onsite",
  "technical",
  "behavioral",
  "assessment",
  "panel",
  "other",
];

const INTERVIEW_KIND_LABELS = {
  phone: "Phone",
  video: "Video",
  onsite: "Onsite",
  technical: "Technical",
  behavioral: "Behavioral",
  assessment: "Assessment",
  panel: "Panel",
  other: "Other",
};

const INTERVIEW_STATUSES = [
  "scheduled",
  "completed",
  "cancelled",
  "rescheduled",
  "no_show",
];

const INTERVIEW_STATUS_LABELS = {
  scheduled: "Scheduled",
  completed: "Completed",
  cancelled: "Cancelled",
  rescheduled: "Rescheduled",
  no_show: "No Show",
};

const DOCUMENT_TYPES = [
  "resume",
  "cover_letter",
  "portfolio",
  "transcript",
  "assessment",
  "contract",
  "other",
];

const DOCUMENT_TYPE_LABELS = {
  resume: "Resume",
  cover_letter: "Cover Letter",
  portfolio: "Portfolio",
  transcript: "Transcript",
  assessment: "Assessment",
  contract: "Contract",
  other: "Other",
};

// Backend datetimes (SQLite/Postgres) are serialized as naive UTC strings like
// "2026-09-10T15:00:00". Append "Z" so the browser interprets them as UTC
// instead of local time, then convert for display / datetime-local inputs.
function parseBackendDatetime(str) {
  if (!str) return null;
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(str);
  const d = new Date(hasZone ? str : `${str}Z`);
  return isNaN(d.getTime()) ? null : d;
}

function formatDateTime(str) {
  const d = parseBackendDatetime(str);
  if (!d) return str || "";
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function toLocalInputValue(date) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function fromLocalInputValue(str) {
  if (!str) return null;
  const d = new Date(str);
  return isNaN(d.getTime()) ? null : d.toISOString();
}

function backendToInputValue(str) {
  const d = parseBackendDatetime(str);
  return d ? toLocalInputValue(d) : "";
}

function formatFileSize(size) {
  if (size === null || size === undefined || size === "") return null;
  const n = Number(size);
  if (Number.isNaN(n)) return null;
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function TimelinePanel({ applicationId, notify }) {
  const { t } = useTranslation();
  const [entries, setEntries] = useState(null);
  const [error, setError] = useState(null);
  const [adding, setAdding] = useState(false);
  const [eventType, setEventType] = useState("note_added");
  const [eventNotes, setEventNotes] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await api.getApplicationTimeline(applicationId);
      setEntries(Array.isArray(data?.entries) ? data.entries : []);
    } catch {
      setError(t("app.timelineError", "Couldn't load this application's timeline."));
      setEntries([]);
    }
  }, [applicationId, t]);

  useEffect(() => {
    load();
  }, [load]);

  const handleAdd = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.createApplicationEvent(applicationId, {
        event_type: eventType,
        notes: eventNotes.trim() || null,
      });
      setEventNotes("");
      setAdding(false);
      notify(t("app.timelineAdded", "Activity logged."));
      load();
    } catch {
      notify(t("app.timelineAddFailed", "Failed to log activity."), "error");
    } finally {
      setSaving(false);
    }
  };

  const renderTitle = (entry) => {
    if (entry.kind === "event") {
      if (entry.event_type === "status_changed" && entry.metadata) {
        const from = entry.metadata.from_status || "Unknown";
        const to = entry.metadata.to_status || "Unknown";
        return (
          <span className="tl-title">
            {EVENT_LABELS[entry.event_type] || entry.event_type}: {from} → {to}
          </span>
        );
      }
      return <span className="tl-title">{EVENT_LABELS[entry.event_type] || entry.event_type}</span>;
    }
    if (entry.kind === "interview") {
      return <span className="tl-title">{INTERVIEW_KIND_LABELS[entry.interview_kind] || entry.interview_kind} Interview</span>;
    }
    return <span className="tl-title">{DOCUMENT_TYPE_LABELS[entry.document_type] || entry.document_type}</span>;
  };

  if (error) {
    return <div className="alert alert-error">{error}</div>;
  }

  if (entries === null) {
    return <SkeletonList count={3} />;
  }

  return (
    <div className="pipeline-panel">
      {entries.length === 0 ? (
        <div className="pipeline-inline-empty">
          <MessageSquare size={20} />
          <p>{t("app.timelineEmpty", "No activity logged for this application yet.")}</p>
        </div>
      ) : (
        <ul className="pipeline-timeline-list">
          {entries.map((entry) => (
            <li key={`${entry.kind}-${entry.id}`} className="pipeline-timeline-item">
              <span className={`tl-dot tl-dot-${entry.kind}`} aria-hidden="true" />
              <div className="tl-content">
                <div className="tl-main">
                  {renderTitle(entry)}
                  {entry.notes && <p className="tl-notes">{entry.notes}</p>}
                  {entry.kind === "interview" && (
                    <p className="tl-meta">
                      <CalendarClock size={12} />
                      {formatDateTime(entry.scheduled_at)} · {INTERVIEW_STATUS_LABELS[entry.status] || entry.status}
                    </p>
                  )}
                  {entry.kind === "document" && entry.source_resume_id && (
                    <p className="tl-meta">
                      <Link2 size={12} />
                      {t("app.documentsLinkedResume", "Linked to your resume")}
                    </p>
                  )}
                </div>
                <span className="tl-time">{formatDateTime(entry.created_at)}</span>
              </div>
            </li>
          ))}
        </ul>
      )}

      <div className="pipeline-panel-actions">
        <button type="button" className="btn btn-secondary btn-sm" onClick={() => setAdding((v) => !v)}>
          <MessageSquare size={14} />
          <span>{t("app.timelineLog", "Log an activity")}</span>
        </button>
      </div>

      {adding && (
        <form className="pipeline-inline-form" onSubmit={handleAdd}>
          <div className="form-row">
            <div className="form-group">
              <label className="form-label">{t("app.timelineType", "Activity type")}</label>
              <select
                className="form-select"
                value={eventType}
                onChange={(e) => setEventType(e.target.value)}
              >
                {USER_EVENT_TYPES.map((et) => (
                  <option key={et} value={et}>
                    {EVENT_LABELS[et] || et}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group" style={{ flex: 1 }}>
              <label className="form-label">{t("app.timelineNotes", "Notes")}</label>
              <input
                className="form-input"
                placeholder="e.g. Followed up with the recruiter after submitting my application"
                value={eventNotes}
                onChange={(e) => setEventNotes(e.target.value)}
              />
            </div>
          </div>
          <div className="pipeline-form-actions">
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setAdding(false)}>
              {t("action.cancel", "Cancel")}
            </button>
            <button type="submit" className="btn btn-primary btn-sm" disabled={saving}>
              {saving ? "Saving..." : t("app.timelineAdd", "Add Entry")}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

function InterviewsPanel({ applicationId, notify }) {
  const { t } = useTranslation();
  const [interviews, setInterviews] = useState(null);
  const [error, setError] = useState(null);
  const [form, setForm] = useState(null);
  const [fields, setFields] = useState({ scheduled_at: "", kind: "video", status: "scheduled", notes: "" });
  const [saving, setSaving] = useState(false);

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
    setFields({ scheduled_at: "", kind: "video", status: "scheduled", notes: "" });
    setForm({ mode: "add" });
  };

  const openEdit = (interview) => {
    setFields({
      scheduled_at: backendToInputValue(interview.scheduled_at),
      kind: interview.kind,
      status: interview.status,
      notes: interview.notes || "",
    });
    setForm({ mode: "edit", interview });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!fields.scheduled_at) {
      notify(t("app.interviewsDateRequired", "Please select a date and time."), "error");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        scheduled_at: fromLocalInputValue(fields.scheduled_at),
        kind: fields.kind,
        status: fields.status,
        notes: fields.notes.trim() || null,
      };
      if (form.mode === "edit") {
        await api.updateApplicationInterview(applicationId, form.interview.id, payload);
        notify(t("app.interviewsUpdated", "Interview updated."));
      } else {
        await api.createApplicationInterview(applicationId, payload);
        notify(t("app.interviewsSaved", "Interview saved."));
      }
      setForm(null);
      load();
    } catch {
      notify(t("app.interviewsSavedFailed", "Couldn't save the interview."), "error");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (interview) => {
    if (!window.confirm(t("app.interviewsDeleteConfirm", "Delete this interview?"))) return;
    try {
      await api.deleteApplicationInterview(applicationId, interview.id);
      notify(t("app.interviewsDeleted", "Interview deleted."));
      load();
    } catch {
      notify(t("app.interviewsDeleteFailed", "Couldn't delete the interview."), "error");
    }
  };

  if (error) {
    return <div className="alert alert-error">{error}</div>;
  }

  if (interviews === null) {
    return <SkeletonList count={2} />;
  }

  return (
    <div className="pipeline-panel">
      {interviews.length === 0 ? (
        <div className="pipeline-inline-empty">
          <CalendarClock size={20} />
          <p>{t("app.interviewsEmpty", "No interviews scheduled for this application yet.")}</p>
        </div>
      ) : (
        <div className="pipeline-cards-stack">
          {interviews.map((interview) => (
            <div key={interview.id} className="card pipeline-card-row">
              <div className="pipeline-card-main">
                <div className="pipeline-card-header">
                  <span className="font-mono text-md text-accent">
                    {formatDateTime(interview.scheduled_at)}
                  </span>
                  <span className={`status-badge status-${interview.status}`}>
                    {INTERVIEW_STATUS_LABELS[interview.status] || interview.status}
                  </span>
                </div>
                <p className="text-xs text-secondary">
                  {INTERVIEW_KIND_LABELS[interview.kind] || interview.kind}
                </p>
                {interview.notes && <p className="text-sm text-secondary">{interview.notes}</p>}
              </div>
              <div className="pipeline-card-actions">
                <button
                  type="button"
                  className="btn btn-ghost btn-icon btn-sm"
                  onClick={() => openEdit(interview)}
                  title={t("app.interviewsEdit", "Edit interview")}
                  aria-label={t("app.interviewsEdit", "Edit interview")}
                >
                  <Pencil size={15} />
                </button>
                <button
                  type="button"
                  className="btn btn-ghost btn-icon btn-sm text-danger"
                  onClick={() => handleDelete(interview)}
                  title={t("action.delete", "Delete")}
                  aria-label={t("action.delete", "Delete")}
                >
                  <Trash2 size={15} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {form ? (
        <form className="pipeline-inline-form" onSubmit={handleSubmit}>
          <div className="form-row">
            <div className="form-group">
              <label className="form-label">{t("app.interviewsDate", "Date & time")}</label>
              <input
                type="datetime-local"
                className="form-input"
                value={fields.scheduled_at}
                onChange={(e) => setFields((f) => ({ ...f, scheduled_at: e.target.value }))}
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label">{t("app.interviewsKind", "Interview type")}</label>
              <select
                className="form-select"
                value={fields.kind}
                onChange={(e) => setFields((f) => ({ ...f, kind: e.target.value }))}
              >
                {INTERVIEW_KINDS.map((kind) => (
                  <option key={kind} value={kind}>
                    {INTERVIEW_KIND_LABELS[kind] || kind}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">{t("app.interviewsStatus", "Status")}</label>
              <select
                className="form-select"
                value={fields.status}
                onChange={(e) => setFields((f) => ({ ...f, status: e.target.value }))}
              >
                {INTERVIEW_STATUSES.map((status) => (
                  <option key={status} value={status}>
                    {INTERVIEW_STATUS_LABELS[status] || status}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">{t("app.timelineNotes", "Notes")}</label>
            <textarea
              className="form-textarea"
              rows={2}
              placeholder="e.g. Virtual first-round with the hiring manager"
              value={fields.notes}
              onChange={(e) => setFields((f) => ({ ...f, notes: e.target.value }))}
            />
          </div>
          <div className="pipeline-form-actions">
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setForm(null)}>
              {t("action.cancel", "Cancel")}
            </button>
            <button type="submit" className="btn btn-primary btn-sm" disabled={saving}>
              {saving
                ? "Saving..."
                : form.mode === "edit"
                  ? t("app.interviewsUpdate", "Update interview")
                  : t("app.interviewsSave", "Save interview")}
            </button>
          </div>
        </form>
      ) : (
        <div className="pipeline-panel-actions">
          <button type="button" className="btn btn-secondary btn-sm" onClick={openAdd}>
            <Plus size={14} />
            <span>{t("app.interviewsAdd", "Schedule interview")}</span>
          </button>
        </div>
      )}
    </div>
  );
}

function DocumentsPanel({ applicationId, notify }) {
  const { t } = useTranslation();
  const [documents, setDocuments] = useState(null);
  const [error, setError] = useState(null);
  const [resumes, setResumes] = useState([]);
  const [attachForm, setAttachForm] = useState({ source_resume_id: "", document_type: "resume", name: "" });
  const [attaching, setAttaching] = useState(false);
  const [uploadType, setUploadType] = useState("resume");
  const [uploadName, setUploadName] = useState("");
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [docs, resumeData] = await Promise.all([
        api.getApplicationDocuments(applicationId),
        api.get("/resumes").catch(() => []),
      ]);
      const resumeList = Array.isArray(resumeData) ? resumeData : [];
      setDocuments(Array.isArray(docs) ? docs : []);
      setResumes(resumeList);
      setAttachForm((f) => {
        if (f.source_resume_id) return f;
        const usable = resumeList.find((r) => r.parsing_status === "completed" && !r.parsing_error);
        return { ...f, source_resume_id: usable ? usable.id : resumeList[0]?.id || "" };
      });
    } catch {
      setError("Couldn't load documents for this application.");
      setDocuments([]);
    }
  }, [applicationId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleAttach = async (e) => {
    e.preventDefault();
    if (!attachForm.source_resume_id) {
      notify("Select a resume to attach.", "error");
      return;
    }
    setAttaching(true);
    try {
      await api.attachApplicationDocument(applicationId, {
        source_resume_id: attachForm.source_resume_id,
        document_type: attachForm.document_type,
        name: attachForm.name.trim() || null,
      });
      notify(t("app.documentsAttached", "Document attached."));
      setAttachForm((f) => ({ ...f, name: "" }));
      load();
    } catch (err) {
      notify(err?.message || t("app.documentsActionFailed", "Couldn't update documents."), "error");
    } finally {
      setAttaching(false);
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) {
      notify("Choose a file to upload.", "error");
      return;
    }
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("document_type", uploadType);
      if (uploadName.trim()) formData.append("name", uploadName.trim());
      await api.uploadApplicationDocument(applicationId, formData);
      notify(t("app.documentsUploaded", "Document uploaded."));
      setUploadName("");
      if (fileRef.current) fileRef.current.value = "";
      load();
    } catch (err) {
      notify(err?.message || t("app.documentsActionFailed", "Couldn't update documents."), "error");
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (doc) => {
    if (
      !window.confirm(
        t(
          "app.documentsDeleteConfirm",
          "Remove this application document? Your original resume will not be affected."
        )
      )
    ) {
      return;
    }
    try {
      await api.deleteApplicationDocument(applicationId, doc.id);
      notify(t("app.documentsDeleted", "Document removed."));
      load();
    } catch {
      notify(t("app.documentsActionFailed", "Couldn't update documents."), "error");
    }
  };

  if (error) {
    return <div className="alert alert-error">{error}</div>;
  }

  if (documents === null) {
    return <SkeletonList count={2} />;
  }

  return (
    <div className="pipeline-panel">
      {documents.length === 0 ? (
        <div className="pipeline-inline-empty">
          <FileText size={20} />
          <p>{t("app.documentsEmpty", "No documents attached to this application yet.")}</p>
        </div>
      ) : (
        <div className="pipeline-cards-stack">
          {documents.map((doc) => {
            const sizeLabel = formatFileSize(doc.file_size);
            return (
              <div key={doc.id} className="card pipeline-card-row">
                <div className="pipeline-card-main">
                  <div className="pipeline-card-header">
                    <span className="text-md font-medium">
                      {doc.name || doc.original_filename || doc.filename || DOCUMENT_TYPE_LABELS[doc.document_type] || doc.document_type}
                    </span>
                    <span className="status-badge status-applied">
                      {DOCUMENT_TYPE_LABELS[doc.document_type] || doc.document_type}
                    </span>
                  </div>
                  <p className="text-xs text-secondary">
                    {doc.source_resume_id
                      ? t("app.documentsLinkedResume", "Linked to your resume")
                      : doc.original_filename || doc.filename}
                    {sizeLabel ? ` · ${sizeLabel}` : ""}
                  </p>
                </div>
                <div className="pipeline-card-actions">
                  <button
                    type="button"
                    className="btn btn-ghost btn-icon btn-sm text-danger"
                    onClick={() => handleDelete(doc)}
                    title={t("action.delete", "Delete")}
                    aria-label={t("action.delete", "Delete")}
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div className="pipeline-form-grid">
        {/* Attach an existing resume (reference-only) */}
        <form className="card pipeline-card-block" onSubmit={handleAttach}>
          <h4 className="pipeline-block-title">
            <Link2 size={14} />
            {t("app.documentsAttachResume", "Attach an existing resume")}
          </h4>
          <div className="form-group">
            <label className="form-label">{t("app.documentsChooseResume", "Choose resume")}</label>
            <select
              className="form-select"
              value={attachForm.source_resume_id}
              onChange={(e) => setAttachForm((f) => ({ ...f, source_resume_id: e.target.value }))}
            >
              <option value="">—</option>
              {resumes.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.original_filename || r.filename || "Untitled resume"}
                </option>
              ))}
            </select>
            {resumes.length === 0 && (
              <p className="text-xs text-tertiary" style={{ marginTop: "var(--space-1)" }}>
                Upload a resume from the Resume page to attach it here.
              </p>
            )}
          </div>
          <div className="form-row">
            <div className="form-group">
              <label className="form-label">{t("app.documentsType", "Document type")}</label>
              <select
                className="form-select"
                value={attachForm.document_type}
                onChange={(e) => setAttachForm((f) => ({ ...f, document_type: e.target.value }))}
              >
                {DOCUMENT_TYPES.map((dt) => (
                  <option key={dt} value={dt}>
                    {DOCUMENT_TYPE_LABELS[dt] || dt}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">{t("app.documentsLabel", "Label (optional)")}</label>
              <input
                className="form-input"
                placeholder="e.g. Updated resume"
                value={attachForm.name}
                onChange={(e) => setAttachForm((f) => ({ ...f, name: e.target.value }))}
              />
            </div>
          </div>
          <div className="pipeline-form-actions">
            <button type="submit" className="btn btn-secondary btn-sm" disabled={attaching}>
              {attaching ? "Attaching..." : t("app.documentsAttach", "Attach")}
            </button>
          </div>
        </form>

        {/* Upload a new document */}
        <form className="card pipeline-card-block" onSubmit={handleUpload}>
          <h4 className="pipeline-block-title">
            <CloudUpload size={14} />
            {t("app.documentsUpload", "Upload a document")}
          </h4>
          <div className="form-group">
            <label className="form-label">File</label>
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.docx"
              className="form-input"
            />
            <p className="text-xs text-tertiary" style={{ marginTop: "var(--space-1)" }}>
              PDF or DOCX, up to 10MB.
            </p>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label className="form-label">{t("app.documentsType", "Document type")}</label>
              <select
                className="form-select"
                value={uploadType}
                onChange={(e) => setUploadType(e.target.value)}
              >
                {DOCUMENT_TYPES.map((dt) => (
                  <option key={dt} value={dt}>
                    {DOCUMENT_TYPE_LABELS[dt] || dt}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">{t("app.documentsLabel", "Label (optional)")}</label>
              <input
                className="form-input"
                placeholder="e.g. Offer letter"
                value={uploadName}
                onChange={(e) => setUploadName(e.target.value)}
              />
            </div>
          </div>
          <div className="pipeline-form-actions">
            <button type="submit" className="btn btn-secondary btn-sm" disabled={uploading}>
              {uploading ? "Uploading..." : t("app.documentsUploadBtn", "Upload")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function ApplicationsPage() {
  const { t } = useTranslation();
  const [applications, setApplications] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("all");

  // Cover letters for the selected job
  const [coverLetters, setCoverLetters] = useState([]);
  const [viewCoverLetter, setViewCoverLetter] = useState(null);

  // Detail / Edit modal
  const [selectedApp, setSelectedApp] = useState(null);
  const [detailTab, setDetailTab] = useState("overview");
  const [editNotes, setEditNotes] = useState("");
  const [savingNotes, setSavingNotes] = useState(false);
  const [notification, setNotification] = useState(null);

  const notify = (msg, type = "success") => {
    setNotification({ msg, type });
    setTimeout(() => setNotification(null), 3500);
  };

  const fetchData = useCallback(async () => {
    try {
      const [apps, jobsData, letters] = await Promise.all([
        api.get("/applications/"),
        api.get("/jobs/"),
        api.getCoverLetters().catch(() => []),
      ]);
      setApplications(Array.isArray(apps) ? apps : []);
      setJobs(Array.isArray(jobsData) ? jobsData : []);
      setCoverLetters(Array.isArray(letters) ? letters : []);
    } catch {
      notify("Failed to load applications.", "error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const getCoverLetterForJob = (jobId) => {
    const numeric = parseInt(jobId, 10);
    return coverLetters.find((cl) => cl.job_id === jobId || cl.job_id === numeric) || null;
  };

  const getJobForApp = (app) => {
    return jobs.find((j) => j.id === app.job_id) || {
      title: app.job_title || "Target Role",
      company: app.company_name || "Company",
      location: "",
    };
  };

  const handleUpdateStatus = async (appId, newStatus) => {
    try {
      const updated = await api.put(`/applications/${appId}`, { status: newStatus });
      setApplications((prev) =>
        prev.map((a) => (a.id === appId ? { ...a, status: newStatus } : a))
      );
      if (selectedApp?.id === appId) {
        setSelectedApp((prev) => ({ ...prev, status: newStatus, updated_at: updated?.updated_at ?? prev.updated_at }));
      }
      notify(`Status updated to ${newStatus}`);
    } catch {
      notify("Failed to update status.", "error");
    }
  };

  const handleSaveNotes = async () => {
    if (!selectedApp) return;
    setSavingNotes(true);
    try {
      await api.put(`/applications/${selectedApp.id}`, { notes: editNotes });
      setApplications((prev) =>
        prev.map((a) => (a.id === selectedApp.id ? { ...a, notes: editNotes } : a))
      );
      setSelectedApp((prev) => ({ ...prev, notes: editNotes }));
      notify("Notes updated successfully.");
    } catch {
      notify("Failed to save notes.", "error");
    } finally {
      setSavingNotes(false);
    }
  };

  const handleDeleteApp = async (appId) => {
    if (!window.confirm("Remove this application from your pipeline?")) return;
    try {
      await api.delete(`/applications/${appId}`);
      setApplications((prev) => prev.filter((a) => a.id !== appId));
      if (selectedApp?.id === appId) setSelectedApp(null);
      notify("Application removed from pipeline.");
    } catch {
      notify("Failed to delete application.", "error");
    }
  };

  const openDetail = (app) => {
    setSelectedApp(app);
    setEditNotes(app.notes || "");
    setDetailTab("overview");
  };

  const activeJob = selectedApp ? getJobForApp(selectedApp) : null;

  // Pipeline counts
  const savedCount = applications.filter((a) => a.status?.toLowerCase() === "saved").length;
  const appliedCount = applications.filter((a) => a.status?.toLowerCase() === "applied").length;
  const interviewCount = applications.filter((a) => a.status?.toLowerCase() === "interview").length;
  const offerCount = applications.filter((a) => a.status?.toLowerCase() === "offer").length;
  const rejectedCount = applications.filter((a) => a.status?.toLowerCase() === "rejected").length;

  const filteredApps = applications.filter((app) => {
    if (statusFilter === "all") return true;
    return app.status?.toLowerCase() === statusFilter.toLowerCase();
  });

  return (
    <div className="page applications-page">
      {/* Toast Notification */}
      {notification && (
        <div className={`toast toast-${notification.type}`} role="status">
          {notification.msg}
        </div>
      )}

      {/* Page Header */}
      <header className="page-header">
        <div className="page-header-row">
          <div>
            <h1>{t("app.title", "Applications")}</h1>
            <p>
              {applications.length} {t("app.activeCount", "active applications in your career pipeline")}
            </p>
          </div>

          <div className="page-header-actions">
            <Link to="/discover" className="btn btn-primary">
              <Plus size={16} />
              <span>Explore Opportunities to Apply</span>
            </Link>
          </div>
        </div>
      </header>

      {/* Visual Status Pipeline Strip */}
      <section className="card pipeline-strip-card">
        <div className="pipeline-stages-row">
          <button
            type="button"
            className={`pipeline-stage-box ${statusFilter === "saved" ? "active" : ""}`}
            onClick={() => setStatusFilter(statusFilter === "saved" ? "all" : "saved")}
          >
            <span className="stage-num font-mono">{savedCount}</span>
            <span className="stage-name">{t("app.saved", "Saved")}</span>
          </button>

          <div className="stage-arrow">→</div>

          <button
            type="button"
            className={`pipeline-stage-box ${statusFilter === "applied" ? "active" : ""}`}
            onClick={() => setStatusFilter(statusFilter === "applied" ? "all" : "applied")}
          >
            <span className="stage-num font-mono">{appliedCount}</span>
            <span className="stage-name">{t("app.applied", "Applied")}</span>
          </button>

          <div className="stage-arrow">→</div>

          <button
            type="button"
            className={`pipeline-stage-box ${statusFilter === "interview" ? "active" : ""}`}
            onClick={() => setStatusFilter(statusFilter === "interview" ? "all" : "interview")}
          >
            <span className="stage-num font-mono">{interviewCount}</span>
            <span className="stage-name">{t("app.interview", "Interview")}</span>
          </button>

          <div className="stage-arrow">→</div>

          <button
            type="button"
            className={`pipeline-stage-box offer ${statusFilter === "offer" ? "active" : ""}`}
            onClick={() => setStatusFilter(statusFilter === "offer" ? "all" : "offer")}
          >
            <span className="stage-num font-mono text-success">{offerCount}</span>
            <span className="stage-name">{t("app.offer", "Offer")}</span>
          </button>

          {rejectedCount > 0 && (
            <>
              <div className="stage-arrow">|</div>
              <button
                type="button"
                className={`pipeline-stage-box rejected ${statusFilter === "rejected" ? "active" : ""}`}
                onClick={() => setStatusFilter(statusFilter === "rejected" ? "all" : "rejected")}
              >
                <span className="stage-num font-mono text-muted">{rejectedCount}</span>
                <span className="stage-name">{t("app.rejected", "Rejected")}</span>
              </button>
            </>
          )}
        </div>
      </section>

      {/* Filter Tabs */}
      <div className="apps-filter-bar">
        <div className="tabs-pill" role="tablist">
          {["all", "saved", "applied", "interview", "offer", "rejected"].map((st) => (
            <button
              key={st}
              type="button"
              className={`tab-pill-item ${statusFilter === st ? "active" : ""}`}
              onClick={() => setStatusFilter(st)}
              role="tab"
              aria-selected={statusFilter === st}
            >
              <span style={{ textTransform: "capitalize" }}>{st === "all" ? "All Applications" : st}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Applications List */}
      {loading ? (
        <div className="stack" style={{ gap: "var(--space-4)" }}>
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : filteredApps.length === 0 ? (
        <EmptyState
          icon={Layers}
          title={t("app.noApps", "No applications yet")}
          description={
            statusFilter !== "all"
              ? `No applications found with status "${statusFilter}".`
              : t("app.noAppsDesc", "Once you apply to a job, you can track its progress and milestones here.")
          }
          action={
            <Link to="/discover" className="btn btn-primary">
              <span>Find Jobs</span>
              <ArrowRight size={16} />
            </Link>
          }
        />
      ) : (
        <div className="applications-list-stack">
          {filteredApps.map((app) => {
            const job = getJobForApp(app);
            const appliedDate = app.application_date || app.created_at;

            return (
              <div key={app.id} className="card application-item-card">
                <div className="app-item-main">
                  <div className="app-item-header">
                    <div>
                      <h3 className="app-item-title">
                        <Link to={`/discover/${app.job_id}`}>{job.title}</Link>
                      </h3>
                      <p className="app-item-company">
                        {job.company}
                        {job.location && ` • ${job.location}`}
                      </p>
                    </div>

                    <div className="app-status-select-wrap">
                      <select
                        className="status-select-sm"
                        value={app.status || "Saved"}
                        onChange={(e) => handleUpdateStatus(app.id, e.target.value)}
                        aria-label="Change application status"
                      >
                        <option value="Saved">Saved</option>
                        <option value="Applied">Applied</option>
                        <option value="Interview">Interview</option>
                        <option value="Offer">Offer</option>
                        <option value="Rejected">Rejected</option>
                      </select>
                    </div>
                  </div>

                  <div className="app-item-meta">
                    <span className="text-xs text-muted">
                      {appliedDate ? `Applied ${new Date(appliedDate).toLocaleDateString()}` : "Saved recently"}
                    </span>
                    {app.notes && (
                      <span className="app-notes-preview text-xs text-secondary">
                        Note: {app.notes.slice(0, 60)}{app.notes.length > 60 ? "..." : ""}
                      </span>
                    )}
                  </div>
                </div>

                <div className="app-item-actions">
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() => openDetail(app)}
                  >
                    <span>{t("app.viewApp", "View Application")}</span>
                  </button>

                  <button
                    type="button"
                    className="btn btn-ghost btn-icon btn-sm text-danger"
                    onClick={() => handleDeleteApp(app.id)}
                    title="Remove from pipeline"
                    aria-label="Remove application"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Application Detail Modal */}
      {selectedApp && activeJob && (
        <Modal
          isOpen={Boolean(selectedApp)}
          onClose={() => setSelectedApp(null)}
          wide
          title={`Application: ${activeJob.title}`}
        >
          <div className="app-detail-modal-body">
            <div className="tabs-pill detail-tabs" role="tablist">
              {[
                { id: "overview", label: t("app.tabOverview", "Overview") },
                { id: "timeline", label: t("app.tabTimeline", "Timeline") },
                { id: "interviews", label: t("app.tabInterviews", "Interviews") },
                { id: "documents", label: t("app.tabDocuments", "Documents") },
              ].map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  aria-selected={detailTab === tab.id}
                  className={`tab-pill-item ${detailTab === tab.id ? "active" : ""}`}
                  onClick={() => setDetailTab(tab.id)}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {detailTab === "overview" && (
              <>
                <div className="app-detail-company-box">
                  <h3>{activeJob.title}</h3>
                  <p className="text-secondary">{activeJob.company}</p>
                </div>

                {/* Stage Timeline */}
                <div className="app-timeline-section">
                  <span className="timeline-title">Stage Progression</span>
                  <div className="app-timeline-steps">
                    {PIPELINE_STAGES.map((st, idx) => {
                      const currentIdx = PIPELINE_STAGES.indexOf(
                        selectedApp.status ? selectedApp.status.charAt(0).toUpperCase() + selectedApp.status.slice(1).toLowerCase() : "Saved"
                      );
                      const isDone = idx <= currentIdx;
                      const isCurrent = idx === currentIdx;

                      return (
                        <div key={st} className={`timeline-node ${isDone ? "done" : ""} ${isCurrent ? "current" : ""}`}>
                          <div className="node-circle font-mono">{idx + 1}</div>
                          <span className="node-label">{st}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Quick Status Update */}
                <div className="form-group" style={{ marginTop: "var(--space-4)" }}>
                  <label className="form-label">Current Pipeline Status</label>
                  <select
                    className="form-select"
                    value={selectedApp.status || "Saved"}
                    onChange={(e) => handleUpdateStatus(selectedApp.id, e.target.value)}
                  >
                    <option value="Saved">Saved</option>
                    <option value="Applied">Applied</option>
                    <option value="Interview">Interview</option>
                    <option value="Offer">Offer</option>
                    <option value="Rejected">Rejected</option>
                  </select>
                </div>

                {/* Application Notes */}
                <div className="form-group" style={{ marginTop: "var(--space-4)" }}>
                  <label className="form-label">Application Notes & Follow-up Milestones</label>
                  <textarea
                    className="form-textarea"
                    rows={3}
                    placeholder="e.g. Interview scheduled with Engineering Manager on Friday..."
                    value={editNotes}
                    onChange={(e) => setEditNotes(e.target.value)}
                  />
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    style={{ marginTop: "var(--space-2)" }}
                    onClick={handleSaveNotes}
                    disabled={savingNotes}
                  >
                    {savingNotes ? "Saving..." : "Save Notes"}
                  </button>
                </div>

                <div className="modal-footer" style={{ marginTop: "var(--space-6)" }}>
                  {(() => {
                    const coverLetter = getCoverLetterForJob(selectedApp.job_id);
                    return coverLetter ? (
                      <button
                        type="button"
                        className="btn btn-outline btn-sm"
                        onClick={() => setViewCoverLetter(coverLetter)}
                      >
                        <FileText size={14} />
                        <span>View Cover Letter</span>
                      </button>
                    ) : null;
                  })()}
                  <Link to={`/discover/${selectedApp.job_id}`} className="btn btn-secondary btn-sm">
                    <span>View Job Details</span>
                    <ArrowRight size={14} />
                  </Link>
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    onClick={() => setSelectedApp(null)}
                  >
                    Done
                  </button>
                </div>
              </>
            )}

            {detailTab === "timeline" && (
              <TimelinePanel applicationId={selectedApp.id} notify={notify} />
            )}

            {detailTab === "interviews" && (
              <InterviewsPanel applicationId={selectedApp.id} notify={notify} />
            )}

            {detailTab === "documents" && (
              <DocumentsPanel applicationId={selectedApp.id} notify={notify} />
            )}
          </div>
        </Modal>
      )}

      {/* Cover Letter View Modal */}
      {viewCoverLetter && selectedApp && (
        <CoverLetterModal
          isOpen={Boolean(viewCoverLetter)}
          onClose={() => setViewCoverLetter(null)}
          job={{ title: selectedApp.job_title, company: selectedApp.company_name }}
          viewOnly
          initialLetter={viewCoverLetter}
        />
      )}
    </div>
  );
}