import { useState, useEffect, useRef } from "react";
import { X, Building2, Calendar, FileText, History } from "lucide-react";
import PipelineOverviewTab from "./PipelineOverviewTab";
import PipelineTimelineTab from "./PipelineTimelineTab";
import PipelineInterviewsTab from "./PipelineInterviewsTab";
import PipelineDocumentsTab from "./PipelineDocumentsTab";
import { STATUS_LABELS, STATUS_VARIANTS } from "./pipelineUtils";

export default function ApplicationDetailDrawer({
  isOpen,
  onClose,
  application,
  job,
  onUpdateStatus,
  onSaveNotes,
  isSavingNotes = false,
  coverLetter = null,
  onViewCoverLetter,
  notify,
}) {
  const [activeTab, setActiveTab] = useState("overview");
  const drawerRef = useRef(null);
  const previouslyFocusedElementRef = useRef(null);

  // Capture previous active element and trap escape key
  useEffect(() => {
    if (isOpen) {
      previouslyFocusedElementRef.current = document.activeElement;
      const handleKeyDown = (e) => {
        if (e.key === "Escape") {
          onClose();
        }
      };
      document.addEventListener("keydown", handleKeyDown);
      return () => {
        document.removeEventListener("keydown", handleKeyDown);
        if (previouslyFocusedElementRef.current?.focus) {
          previouslyFocusedElementRef.current.focus();
        }
      };
    }
  }, [isOpen, onClose]);

  if (!isOpen || !application) return null;

  const roleTitle = application.job_title || job?.title || "Application Details";
  const companyName = application.job_company || application.company_name || job?.company || "Company";
  const currentStatus = application.status || "Saved";
  const statusVariant = STATUS_VARIANTS[currentStatus] || "saved";

  const tabs = [
    { id: "overview", label: "Overview", icon: Building2 },
    { id: "timeline", label: "Timeline", icon: History },
    { id: "interviews", label: "Interviews", icon: Calendar },
    { id: "documents", label: "Documents", icon: FileText },
  ];

  return (
    <div
      className="pipeline-drawer-overlay"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="pipeline-drawer-title"
    >
      <aside className="pipeline-drawer-panel" ref={drawerRef}>
        {/* Drawer Header */}
        <header className="pipeline-drawer-header">
          <div className="drawer-header-left">
            <div className="drawer-company-badge">
              <Building2 size={13} aria-hidden="true" />
              <span>{companyName}</span>
            </div>
            <h2 id="pipeline-drawer-title" className="drawer-title">
              {roleTitle}
            </h2>
            <div className="drawer-status-line">
              <span className={`pipeline-status-badge status-${statusVariant}`}>
                {STATUS_LABELS[currentStatus]}
              </span>
            </div>
          </div>

          <button
            type="button"
            className="btn btn-ghost btn-icon drawer-close-btn"
            onClick={onClose}
            aria-label="Close application details drawer"
          >
            <X size={18} aria-hidden="true" />
          </button>
        </header>

        {/* Drawer Navigation Tabs */}
        <nav className="pipeline-drawer-nav" aria-label="Application detail tabs">
          <div className="pipeline-drawer-tabs" role="tablist">
            {tabs.map((t) => {
              const Icon = t.icon;
              const isSelected = activeTab === t.id;

              return (
                <button
                  key={t.id}
                  type="button"
                  className={`pipeline-drawer-tab ${isSelected ? "active" : ""}`}
                  onClick={() => setActiveTab(t.id)}
                  role="tab"
                  aria-selected={isSelected}
                  aria-controls={`pipeline-tab-content-${t.id}`}
                >
                  <Icon size={14} aria-hidden="true" />
                  <span>{t.label}</span>
                </button>
              );
            })}
          </div>
        </nav>

        {/* Drawer Content */}
        <div id={`pipeline-tab-content-${activeTab}`} className="pipeline-drawer-body">
          {activeTab === "overview" && (
            <PipelineOverviewTab
              application={application}
              job={job}
              onUpdateStatus={onUpdateStatus}
              onSaveNotes={onSaveNotes}
              isSavingNotes={isSavingNotes}
              coverLetter={coverLetter}
              onViewCoverLetter={onViewCoverLetter}
            />
          )}

          {activeTab === "timeline" && (
            <PipelineTimelineTab applicationId={application.id} notify={notify} />
          )}

          {activeTab === "interviews" && (
            <PipelineInterviewsTab applicationId={application.id} notify={notify} />
          )}

          {activeTab === "documents" && (
            <PipelineDocumentsTab applicationId={application.id} notify={notify} />
          )}
        </div>
      </aside>
    </div>
  );
}
