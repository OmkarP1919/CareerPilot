import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import { useTranslation } from "../context/LanguageContext";
import EmptyState from "../components/EmptyState";
import { SkeletonCard } from "../components/Skeleton";
import Modal from "../components/Modal";
import {
  Layers,
  Plus,
  Trash2,
  ArrowRight,
} from "lucide-react";

const PIPELINE_STAGES = ["Saved", "Applied", "Interview", "Offer"];

export default function ApplicationsPage() {
  const { t } = useTranslation();
  const [applications, setApplications] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("all");

  // Detail / Edit modal
  const [selectedApp, setSelectedApp] = useState(null);
  const [editNotes, setEditNotes] = useState("");
  const [savingNotes, setSavingNotes] = useState(false);
  const [notification, setNotification] = useState(null);

  const notify = (msg, type = "success") => {
    setNotification({ msg, type });
    setTimeout(() => setNotification(null), 3500);
  };

  const fetchData = useCallback(async () => {
    try {
      const [apps, jobsData] = await Promise.all([
        api.get("/applications/"),
        api.get("/jobs/"),
      ]);
      setApplications(Array.isArray(apps) ? apps : []);
      setJobs(Array.isArray(jobsData) ? jobsData : []);
    } catch {
      notify("Failed to load applications.", "error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

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
        setSelectedApp((prev) => ({ ...prev, status: newStatus }));
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
            <p>{applications.length} {t("app.activeCount", "active applications in your career pipeline")}</p>
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
                    onClick={() => {
                      setSelectedApp(app);
                      setEditNotes(app.notes || "");
                    }}
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
      {selectedApp && (
        <Modal
          isOpen={Boolean(selectedApp)}
          onClose={() => setSelectedApp(null)}
          title={`Application: ${getJobForApp(selectedApp).title}`}
        >
          <div className="app-detail-modal-body">
            <div className="app-detail-company-box">
              <h3>{getJobForApp(selectedApp).title}</h3>
              <p className="text-secondary">{getJobForApp(selectedApp).company}</p>
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
          </div>
        </Modal>
      )}
    </div>
  );
}
