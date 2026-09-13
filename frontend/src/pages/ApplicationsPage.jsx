import { useState, useEffect, useCallback } from "react";
import { Plus, Compass } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import { useTranslation } from "../context/LanguageContext";
import ConfirmDialog from "../components/ConfirmDialog";
import CoverLetterModal from "../components/CoverLetterModal";

// Modular Pipeline Components
import PipelineSummaryStrip from "../components/pipeline/PipelineSummaryStrip";
import PipelineFilters from "../components/pipeline/PipelineFilters";
import PipelineCardGrid from "../components/pipeline/PipelineCardGrid";
import ApplicationDetailDrawer from "../components/pipeline/ApplicationDetailDrawer";
import AddApplicationModal from "../components/pipeline/AddApplicationModal";
import { filterApplications, sortApplications } from "../components/pipeline/pipelineUtils";

export default function ApplicationsPage() {
  const { t } = useTranslation();

  // Core data states
  const [applications, setApplications] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [coverLetters, setCoverLetters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filter & Search states
  const [activeTab, setActiveTab] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [sortKey, setSortKey] = useState("recent");

  // Interaction states
  const [selectedApp, setSelectedApp] = useState(null);
  const [updatingAppId, setUpdatingAppId] = useState(null);
  const [isSavingNotes, setIsSavingNotes] = useState(false);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isSubmittingAdd, setIsSubmittingAdd] = useState(false);
  const [deleteAppId, setDeleteAppId] = useState(null);
  const [isDeletingApp, setIsDeletingApp] = useState(false);
  const [viewCoverLetter, setViewCoverLetter] = useState(null);
  const [notification, setNotification] = useState(null);

  const notify = useCallback((msg, type = "success") => {
    setNotification({ msg, type });
    setTimeout(() => setNotification(null), 3500);
  }, []);

  // Fetch initial pipeline data
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [apps, jobsData, letters] = await Promise.all([
        api.get("/applications/"),
        api.get("/jobs/"),
        api.getCoverLetters().catch(() => []),
      ]);
      setApplications(Array.isArray(apps) ? apps : []);
      setJobs(Array.isArray(jobsData) ? jobsData : []);
      setCoverLetters(Array.isArray(letters) ? letters : []);
    } catch (err) {
      setError(err?.message || "Failed to load applications. Please check your network.");
      notify("Failed to load applications.", "error");
    } finally {
      setLoading(false);
    }
  }, [notify]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Helper to retrieve associated job
  const getJobForApp = useCallback((app) => {
    if (!app?.job_id) return null;
    return jobs.find((j) => j.id === app.job_id) || null;
  }, [jobs]);

  // Helper to retrieve cover letter for a job
  const getCoverLetterForJob = useCallback((jobId) => {
    if (!jobId) return null;
    const numeric = parseInt(jobId, 10);
    return coverLetters.find((cl) => cl.job_id === jobId || cl.job_id === numeric) || null;
  }, [coverLetters]);

  // Update Status mutation
  const handleUpdateStatus = async (appId, newStatus) => {
    setUpdatingAppId(appId);
    try {
      const updated = await api.put(`/applications/${appId}`, { status: newStatus });
      setApplications((prev) =>
        prev.map((a) => (a.id === appId ? { ...a, status: newStatus, updated_at: updated?.updated_at || new Date().toISOString() } : a))
      );
      if (selectedApp?.id === appId) {
        setSelectedApp((prev) => ({
          ...prev,
          status: newStatus,
          updated_at: updated?.updated_at ?? prev.updated_at,
        }));
      }
      notify(`Status updated to ${newStatus}`);
    } catch (err) {
      notify(err?.message || "Failed to update status.", "error");
    } finally {
      setUpdatingAppId(null);
    }
  };

  // Save Notes mutation
  const handleSaveNotes = async (notes) => {
    if (!selectedApp) return;
    setIsSavingNotes(true);
    try {
      const updated = await api.put(`/applications/${selectedApp.id}`, { notes });
      setApplications((prev) =>
        prev.map((a) => (a.id === selectedApp.id ? { ...a, notes, updated_at: updated?.updated_at || prev.updated_at } : a))
      );
      setSelectedApp((prev) => ({ ...prev, notes, updated_at: updated?.updated_at || prev.updated_at }));
      notify("Notes updated successfully.");
    } catch (err) {
      notify(err?.message || "Failed to save notes.", "error");
    } finally {
      setIsSavingNotes(false);
    }
  };

  // Delete Application
  const handleDeleteApp = (appId) => {
    setDeleteAppId(appId);
  };

  const confirmDeleteApp = async () => {
    if (!deleteAppId) return;
    setIsDeletingApp(true);
    try {
      await api.delete(`/applications/${deleteAppId}`);
      setApplications((prev) => prev.filter((a) => a.id !== deleteAppId));
      if (selectedApp?.id === deleteAppId) setSelectedApp(null);
      notify("Application removed from pipeline.");
      setDeleteAppId(null);
    } catch (err) {
      notify(err?.message || "Failed to delete application.", "error");
    } finally {
      setIsDeletingApp(false);
    }
  };

  // Create external/manual Application
  const handleAddApplication = async (newAppData) => {
    setIsSubmittingAdd(true);
    try {
      // 1. Materialize a user job record for this external role
      const jobPayload = {
        title: newAppData.title,
        company: newAppData.company,
        location: newAppData.location || null,
        application_url: newAppData.application_url || null,
        source: "Manual Entry",
      };

      const createdJob = await api.post("/jobs/", jobPayload);

      // 2. Create the associated application with user-selected status
      const appPayload = {
        job_id: createdJob.id,
        status: newAppData.status || "Applied",
        notes: newAppData.notes || null,
        application_date: new Date().toISOString(),
      };

      const createdApp = await api.post("/applications/", appPayload);

      // 3. Update local state
      setJobs((prev) => [createdJob, ...prev]);
      const enrichedApp = {
        ...createdApp,
        job_title: createdJob.title,
        job_company: createdJob.company,
        location: createdJob.location,
      };
      setApplications((prev) => [enrichedApp, ...prev]);

      notify(`Application for ${newAppData.company} added to pipeline.`);
      return enrichedApp;
    } catch (err) {
      throw new Error(err?.message || "Could not create application. Please verify details.");
    } finally {
      setIsSubmittingAdd(false);
    }
  };

  // Derived filtered & sorted applications
  const filtered = filterApplications(applications, activeTab, searchQuery);
  const displayedApplications = sortApplications(filtered, sortKey);

  const activeJob = selectedApp ? getJobForApp(selectedApp) : null;
  const activeCoverLetter = selectedApp ? getCoverLetterForJob(selectedApp.job_id) : null;

  return (
    <div className="page applications-page pipeline-page-unified">
      {/* Toast Notification */}
      {notification && (
        <div className={`toast toast-${notification.type}`} role="status" aria-live="polite">
          {notification.msg}
        </div>
      )}

      {/* Page Header */}
      <header className="page-header pipeline-page-header">
        <div className="page-header-row">
          <div className="pipeline-header-title-block">
            <h1 className="pipeline-page-title">{t("app.title", "Application Pipeline")}</h1>
            <p className="pipeline-page-subtitle">
              Track, organize, and advance your active career pursuits in one calm workspace.
            </p>
          </div>

          <div className="page-header-actions pipeline-header-actions">
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => setIsAddModalOpen(true)}
              aria-label="Add application"
            >
              <Plus size={16} aria-hidden="true" />
              <span>Add Application</span>
            </button>
            <Link to="/discover" className="btn btn-secondary">
              <Compass size={16} aria-hidden="true" />
              <span>Browse Jobs</span>
            </Link>
          </div>
        </div>
      </header>

      {/* Overview Metrics Strip */}
      <PipelineSummaryStrip
        applications={applications}
        activeTab={activeTab}
        onSelectTab={setActiveTab}
      />

      {/* Search, Filter & Sort Controls */}
      <PipelineFilters
        applications={applications}
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        sortKey={sortKey}
        onSortChange={setSortKey}
      />

      {/* Main Applications Feed Grid */}
      <PipelineCardGrid
        applications={displayedApplications}
        jobs={jobs}
        loading={loading}
        error={error}
        onRetry={fetchData}
        searchQuery={searchQuery}
        activeTab={activeTab}
        onClearSearch={() => setSearchQuery("")}
        onResetTab={() => setActiveTab("all")}
        onOpenDetail={(app) => setSelectedApp(app)}
        onUpdateStatus={handleUpdateStatus}
        onDelete={handleDeleteApp}
        onOpenAddModal={() => setIsAddModalOpen(true)}
        updatingAppId={updatingAppId}
      />

      {/* Application Detail Slide-Over Drawer */}
      <ApplicationDetailDrawer
        isOpen={Boolean(selectedApp)}
        onClose={() => setSelectedApp(null)}
        application={selectedApp}
        job={activeJob}
        onUpdateStatus={handleUpdateStatus}
        onSaveNotes={handleSaveNotes}
        isSavingNotes={isSavingNotes}
        coverLetter={activeCoverLetter}
        onViewCoverLetter={(letter) => setViewCoverLetter(letter)}
        notify={notify}
      />

      {/* Add External Application Modal */}
      <AddApplicationModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onSubmit={handleAddApplication}
        isSubmitting={isSubmittingAdd}
      />

      {/* Cover Letter Modal View */}
      {viewCoverLetter && selectedApp && (
        <CoverLetterModal
          isOpen={Boolean(viewCoverLetter)}
          onClose={() => setViewCoverLetter(null)}
          job={{ title: selectedApp.job_title, company: selectedApp.company_name }}
          viewOnly
          initialLetter={viewCoverLetter}
        />
      )}

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        isOpen={Boolean(deleteAppId)}
        onClose={() => !isDeletingApp && setDeleteAppId(null)}
        onConfirm={confirmDeleteApp}
        title={t("app.deleteTitle", "Remove Application")}
        message={t(
          "app.deleteConfirm",
          "Remove this application from your pipeline? This action cannot be undone."
        )}
        confirmLabel={t("action.remove", "Remove")}
        cancelLabel={t("action.cancel", "Cancel")}
        destructive
        loading={isDeletingApp}
      />
    </div>
  );
}