import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import StatusBadge from "../components/StatusBadge";
import EmptyState from "../components/EmptyState";
import { SkeletonCard } from "../components/Skeleton";
import {
  Plus,
  X,
  Briefcase,
  Edit3,
  Trash2,
  Calendar,
  FileText,
  Building2,
  CheckCircle2,
  AlertCircle,
  Clock,
  Layers,
} from "lucide-react";

const STATUSES = [
  "saved",
  "preparing",
  "applied",
  "assessment",
  "interview",
  "offer",
  "rejected",
  "withdrawn",
];

const EMPTY_FORM = {
  job_id: "",
  status: "saved",
  application_date: new Date().toISOString().split("T")[0],
  resume_version: "",
  notes: "",
};

export default function ApplicationsPage() {
  const [applications, setApplications] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [editApp, setEditApp] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [notification, setNotification] = useState(null);

  const showNotif = (msg, type = "success") => {
    setNotification({ msg, type });
    setTimeout(() => setNotification(null), 3500);
  };

  const fetchData = async () => {
    try {
      const [apps, jobsData] = await Promise.all([
        api.get("/applications/"),
        api.get("/jobs/"),
      ]);
      setApplications(Array.isArray(apps) ? apps : []);
      setJobs(Array.isArray(jobsData) ? jobsData : []);
    } catch {
      showNotif("Failed to load application pipeline.", "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const openAdd = () => {
    setEditApp(null);
    setForm(EMPTY_FORM);
    setShowModal(true);
  };

  const openEdit = (app) => {
    setEditApp(app);
    setForm({
      job_id: app.job_id,
      status: app.status,
      application_date: app.application_date?.split("T")[0] || "",
      resume_version: app.resume_version || "",
      notes: app.notes || "",
    });
    setShowModal(true);
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      if (editApp) {
        await api.put(`/applications/${editApp.id}`, form);
        showNotif("Application status updated.");
      } else {
        if (!form.job_id) {
          showNotif("Please select a target job opportunity.", "error");
          setSaving(false);
          return;
        }
        await api.post("/applications/", form);
        showNotif("Job added to application pipeline.");
      }
      setShowModal(false);
      await fetchData();
    } catch {
      showNotif("Failed to save application.", "error");
    } finally {
      setSaving(false);
    }
  };

  const handleQuickStatusChange = async (appId, newStatus) => {
    try {
      await api.put(`/applications/${appId}`, { status: newStatus });
      setApplications((prev) =>
        prev.map((a) => (a.id === appId ? { ...a, status: newStatus } : a))
      );
      showNotif(`Status moved to ${newStatus}`);
    } catch {
      showNotif("Failed to update status", "error");
    }
  };

  const handleDelete = async (appId) => {
    if (!window.confirm("Remove this application from your pipeline?")) return;
    try {
      await api.delete(`/applications/${appId}`);
      showNotif("Application removed.");
      await fetchData();
    } catch {
      showNotif("Failed to delete application.", "error");
    }
  };

  const statusCounts = STATUSES.reduce((acc, s) => {
    acc[s] = applications.filter((a) => a.status === s).length;
    return acc;
  }, {});

  const filtered = statusFilter
    ? applications.filter((a) => a.status === statusFilter)
    : applications;

  if (loading) {
    return (
      <div className="page">
        <div className="page-header">
          <div className="skeleton skeleton-title" style={{ width: 220, height: 32 }} />
        </div>
        <div className="grid-2">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      {/* === Page Header === */}
      <header className="page-header">
        <div className="page-header-row">
          <div>
            <h1>Application Pipeline</h1>
            <p>Track your submission stages, interview rounds, and offers</p>
          </div>
          <div className="page-header-actions">
            <button className="btn btn-primary btn-sm" onClick={openAdd}>
              <Plus size={14} />
              <span>Track Application</span>
            </button>
          </div>
        </div>
      </header>

      {notification && (
        <div className={`alert alert-${notification.type}`} role="alert">
          {notification.type === "error" ? <AlertCircle size={16} /> : <CheckCircle2 size={16} />}
          <span>{notification.msg}</span>
        </div>
      )}

      {/* === Filter Pills Bar === */}
      <div className="pipeline-filter-bar">
        <button
          className={`pipeline-filter-pill ${!statusFilter ? "active" : ""}`}
          onClick={() => setStatusFilter("")}
          type="button"
        >
          <span>All Stages</span>
          <span className="pipeline-pill-count">{applications.length}</span>
        </button>

        {STATUSES.map((s) => (
          <button
            key={s}
            className={`pipeline-filter-pill ${statusFilter === s ? "active" : ""}`}
            onClick={() => setStatusFilter(statusFilter === s ? "" : s)}
            type="button"
          >
            <span>{s.charAt(0).toUpperCase() + s.slice(1)}</span>
            <span className="pipeline-pill-count">{statusCounts[s] || 0}</span>
          </button>
        ))}
      </div>

      {/* === Applications Grid / List === */}
      {filtered.length > 0 ? (
        <div className="pipeline-cards-list">
          {filtered.map((app) => (
            <div key={app.id} className="pipeline-card">
              <div className="pipeline-card-main">
                <div className="pipeline-card-header">
                  <div>
                    <span className="pipeline-company-tag">
                      <Building2 size={13} />
                      <span>{app.job_company || "Target Company"}</span>
                    </span>
                    <Link to={`/discover/${app.job_id}`} className="pipeline-job-title">
                      {app.job_title || "Unknown Job"}
                    </Link>
                  </div>
                  <div className="pipeline-status-dropdown-wrap">
                    <StatusBadge status={app.status} />
                  </div>
                </div>

                <div className="pipeline-meta-chips">
                  {app.application_date && (
                    <span className="pipeline-meta-item">
                      <Calendar size={13} />
                      <span>Applied {new Date(app.application_date).toLocaleDateString()}</span>
                    </span>
                  )}
                  {app.resume_version && (
                    <span className="pipeline-meta-item">
                      <FileText size={13} />
                      <span>Resume: {app.resume_version}</span>
                    </span>
                  )}
                </div>

                {app.notes && (
                  <div className="pipeline-notes-box">
                    <p>{app.notes}</p>
                  </div>
                )}
              </div>

              <div className="pipeline-card-actions">
                <div className="stage-quick-select-wrap">
                  <select
                    className="form-select form-select-sm"
                    value={app.status}
                    onChange={(e) => handleQuickStatusChange(app.id, e.target.value)}
                    aria-label="Update application stage"
                  >
                    {STATUSES.map((s) => (
                      <option key={s} value={s}>
                        Move to: {s.charAt(0).toUpperCase() + s.slice(1)}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="pipeline-action-btns">
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={() => openEdit(app)}
                    type="button"
                  >
                    <Edit3 size={14} />
                    <span>Edit</span>
                  </button>
                  <button
                    className="btn btn-ghost btn-sm btn-danger"
                    onClick={() => handleDelete(app.id)}
                    type="button"
                    title="Delete Application"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={Layers}
          title={statusFilter ? `No ${statusFilter} applications` : "No applications in pipeline"}
          text={
            statusFilter
              ? `You do not have any applications in the '${statusFilter}' stage.`
              : "Track your first application submission to monitor your interview progress."
          }
          action={
            <button className="btn btn-primary btn-sm" onClick={openAdd}>
              <Plus size={14} /> Track Application
            </button>
          }
        />
      )}

      {/* === Add / Edit Application Modal === */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{editApp ? "Edit Application Stage" : "Track New Application"}</h3>
              <button
                className="btn btn-ghost btn-icon btn-sm"
                onClick={() => setShowModal(false)}
                aria-label="Close"
              >
                <X size={18} />
              </button>
            </div>
            <form onSubmit={handleSave} className="modal-body">
              {!editApp && (
                <div className="form-group">
                  <label className="form-label" htmlFor="app-job-id">Opportunity *</label>
                  <select
                    id="app-job-id"
                    className="form-select"
                    value={form.job_id}
                    onChange={(e) => setForm({ ...form, job_id: e.target.value })}
                    required
                  >
                    <option value="">Select an opportunity...</option>
                    {jobs.map((j) => (
                      <option key={j.id} value={j.id}>
                        {j.title} — {j.company}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">Current Stage</label>
                  <select
                    className="form-select"
                    value={form.status}
                    onChange={(e) => setForm({ ...form, status: e.target.value })}
                  >
                    {STATUSES.map((s) => (
                      <option key={s} value={s}>
                        {s.charAt(0).toUpperCase() + s.slice(1)}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="app-date">Application Date</label>
                  <input
                    id="app-date"
                    className="form-input"
                    type="date"
                    value={form.application_date}
                    onChange={(e) => setForm({ ...form, application_date: e.target.value })}
                  />
                </div>
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="app-resume-version">Resume Version Used</label>
                <input
                  id="app-resume-version"
                  className="form-input"
                  value={form.resume_version}
                  onChange={(e) => setForm({ ...form, resume_version: e.target.value })}
                  placeholder="e.g. Software_Architect_v3.pdf"
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="app-notes">Interview Notes & Next Steps</label>
                <textarea
                  id="app-notes"
                  className="form-textarea"
                  rows={3}
                  value={form.notes}
                  onChange={(e) => setForm({ ...form, notes: e.target.value })}
                  placeholder="Recruiter contact, interview rounds, prep questions..."
                />
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-outline"
                  onClick={() => setShowModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={saving}
                >
                  {saving ? (
                    <>
                      <span className="spinner-inline" />
                      <span>Saving...</span>
                    </>
                  ) : editApp ? (
                    "Save Changes"
                  ) : (
                    "Track Opportunity"
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
