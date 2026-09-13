import { Link } from "react-router-dom";
import { Layers, Plus, Compass, SearchX, AlertCircle, RefreshCw } from "lucide-react";
import PipelineCard from "./PipelineCard";

export default function PipelineCardGrid({
  applications = [],
  jobs = [],
  loading = false,
  error = null,
  onRetry,
  searchQuery = "",
  activeTab = "all",
  onClearSearch,
  onResetTab,
  onOpenDetail,
  onUpdateStatus,
  onDelete,
  onOpenAddModal,
  updatingAppId = null,
}) {
  // Helper to find associated job
  const getJobForApp = (app) => {
    if (!app.job_id) return null;
    return jobs.find((j) => j.id === app.job_id) || null;
  };

  // Loading skeleton state
  if (loading) {
    return (
      <div className="pipeline-grid-loading" aria-label="Loading applications" aria-busy="true">
        {[1, 2, 3, 4, 5, 6].map((idx) => (
          <div key={idx} className="pipeline-card-skeleton">
            <div className="skeleton-line-sm" style={{ width: "40%" }} />
            <div className="skeleton-line-md" style={{ width: "75%", margin: "8px 0" }} />
            <div className="skeleton-line-sm" style={{ width: "50%" }} />
            <div className="skeleton-line-sm" style={{ width: "30%", marginTop: "16px" }} />
          </div>
        ))}
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="pipeline-error-state card" role="alert">
        <AlertCircle size={32} className="text-danger" aria-hidden="true" />
        <h3 className="pipeline-error-title">Unable to load your applications</h3>
        <p className="pipeline-error-desc">{error}</p>
        {onRetry && (
          <button type="button" className="btn btn-secondary btn-sm" onClick={onRetry}>
            <RefreshCw size={14} aria-hidden="true" />
            <span>Try Again</span>
          </button>
        )}
      </div>
    );
  }

  // Empty pipeline (user has 0 applications in entire database)
  if (applications.length === 0 && !searchQuery && activeTab === "all") {
    return (
      <div className="pipeline-empty-state card">
        <div className="pipeline-empty-icon-wrap">
          <Layers size={36} aria-hidden="true" />
        </div>
        <h3 className="pipeline-empty-title">Your career pipeline is empty</h3>
        <p className="pipeline-empty-desc">
          Track, organize, and advance your active opportunities in one calm place.
          Add external roles or discover tailored matches to start your pipeline.
        </p>
        <div className="pipeline-empty-actions">
          <button
            type="button"
            className="btn btn-primary"
            onClick={onOpenAddModal}
            aria-label="Add external application to pipeline"
          >
            <Plus size={16} aria-hidden="true" />
            <span>Add Application</span>
          </button>
          <Link to="/discover" className="btn btn-secondary">
            <Compass size={16} aria-hidden="true" />
            <span>Browse Matching Jobs</span>
          </Link>
        </div>
      </div>
    );
  }

  // Empty search state (query produced 0 results)
  if (applications.length === 0 && searchQuery) {
    return (
      <div className="pipeline-empty-state card">
        <div className="pipeline-empty-icon-wrap text-muted">
          <SearchX size={32} aria-hidden="true" />
        </div>
        <h3 className="pipeline-empty-title">No applications found</h3>
        <p className="pipeline-empty-desc">
          No tracked applications matched &ldquo;{searchQuery}&rdquo;. Check for typos or try clearing your search query.
        </p>
        <div className="pipeline-empty-actions">
          <button type="button" className="btn btn-secondary btn-sm" onClick={onClearSearch}>
            Clear Search Filter
          </button>
        </div>
      </div>
    );
  }

  // Empty filter state (stage tab produced 0 results)
  if (applications.length === 0 && activeTab !== "all") {
    return (
      <div className="pipeline-empty-state card">
        <div className="pipeline-empty-icon-wrap text-muted">
          <Layers size={32} aria-hidden="true" />
        </div>
        <h3 className="pipeline-empty-title">No applications in this stage</h3>
        <p className="pipeline-empty-desc">
          You currently do not have any applications marked as &ldquo;{activeTab}&rdquo;.
        </p>
        <div className="pipeline-empty-actions">
          <button type="button" className="btn btn-secondary btn-sm" onClick={onResetTab}>
            View All Applications
          </button>
        </div>
      </div>
    );
  }

  // Responsive Grid
  return (
    <div id="pipeline-applications-list" className="pipeline-card-grid" role="region" aria-label="Applications list">
      {applications.map((app) => (
        <PipelineCard
          key={app.id}
          application={app}
          job={getJobForApp(app)}
          onOpenDetail={onOpenDetail}
          onUpdateStatus={onUpdateStatus}
          onDelete={onDelete}
          isUpdating={updatingAppId === app.id}
        />
      ))}
    </div>
  );
}
