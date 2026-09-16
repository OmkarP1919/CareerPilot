import { useState, useEffect, useCallback, useMemo } from "react";
import { useParams, useLocation, useSearchParams, Link } from "react-router-dom";
import { api } from "../services/api";
import { useTranslation } from "../context/LanguageContext";
import { SkeletonCard } from "../components/Skeleton";
import TailoringModal from "../components/TailoringModal";
import CoverLetterModal from "../components/CoverLetterModal";
import JobHeroHeader from "../components/job-details/JobHeroHeader";
import JobActionBar from "../components/job-details/JobActionBar";
import JobOverviewPanel from "../components/job-details/JobOverviewPanel";
import JobFitPanel from "../components/job-details/JobFitPanel";
import TailoredResumeDrawer from "../components/job-details/TailoredResumeDrawer";
import AnalyzeResumeModal from "../components/job-details/AnalyzeResumeModal";
import ExternalApplyToast from "../components/jobs/ExternalApplyToast";
import { ArrowLeft, FileText, CheckCircle2 } from "lucide-react";

export default function JobDetailsPage() {
  const { id } = useParams();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const { t } = useTranslation();

  // Core data states
  const [job, setJob] = useState(null);
  const [matchData, setMatchData] = useState(null);
  const [application, setApplication] = useState(null);
  const [loading, setLoading] = useState(true);
  const [recalculating, setRecalculating] = useState(false);
  const [savingApp, setSavingApp] = useState(false);
  const [error, setError] = useState(null);
  const [notification, setNotification] = useState(null);

  // Workflow drawers & modals
  const [tailorModalOpen, setTailorModalOpen] = useState(false);
  const [analyzeModalOpen, setAnalyzeModalOpen] = useState(false);
  const [tailoredResult, setTailoredResult] = useState(null);
  const [coverOpen, setCoverOpen] = useState(false);
  const [externalApplyPromptJob, setExternalApplyPromptJob] = useState(null);

  // Mobile segmented tab ("overview" | "fit")
  const initialTab = searchParams.get("tab") === "fit" ? "fit" : "overview";
  const [mobileTab, setMobileTab] = useState(initialTab);

  const notify = (msg, type = "success") => {
    setNotification({ msg, type });
    setTimeout(() => setNotification(null), 3500);
  };

  // Sync mobile tab changes with search params when explicitly switched
  const handleSelectMobileTab = (tab) => {
    setMobileTab(tab);
    if (tab === "fit") {
      searchParams.set("tab", "fit");
    } else {
      searchParams.delete("tab");
    }
    setSearchParams(searchParams, { replace: true });
  };

  // Fetch job, match analysis, and pipeline status
  const loadJobDetails = useCallback(async () => {
    if (!id || id === ":id") {
      setError("Opportunity details could not be found.");
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const [jobData, appsRes] = await Promise.all([
        api.get(`/jobs/${id}`),
        api.get("/applications/").catch(() => []),
      ]);

      setJob(jobData);

      const appsList = Array.isArray(appsRes) ? appsRes : [];
      const currentApp = appsList.find(
        (a) => a.job_id === parseInt(id, 10) || a.job_id === id
      );
      setApplication(currentApp || null);

      // Attempt to load existing saved analysis
      try {
        const matchRes = await api.get(`/jobs/${id}/analysis`);
        setMatchData(matchRes);
      } catch {
        // If not analyzed yet, run automatic match calculation to give immediate value
        try {
          const autoMatch = await api.post(`/jobs/${id}/match`);
          setMatchData(autoMatch);
        } catch {
          // If profile has no skills yet, gracefully use whatever match score job has
          setMatchData(null);
        }
      }

      // Check if routed with openTailor intent from Dashboard
      if (location.state?.openTailor) {
        setTailorModalOpen(true);
      }
    } catch {
      setError("Opportunity details could not be found.");
    } finally {
      setLoading(false);
    }
  }, [id, location.state]);

  useEffect(() => {
    loadJobDetails();
  }, [loadJobDetails]);

  // Recalculate match explicitly
  const handleRecalculateMatch = async () => {
    if (!id || recalculating) return;
    setRecalculating(true);
    try {
      const freshMatch = await api.post(`/jobs/${id}/match`);
      setMatchData(freshMatch);
      notify("Match score and factors refreshed against your latest profile.");
    } catch {
      notify(
        "Could not calculate match. Ensure your career profile has skills or a resume configured.",
        "error"
      );
    } finally {
      setRecalculating(false);
    }
  };

  // Update pipeline status
  const handleUpdateStatus = async (newStatus) => {
    if (!id) return;
    setSavingApp(true);
    try {
      if (application) {
        const updated = await api.put(`/applications/${application.id}`, {
          status: newStatus,
        });
        setApplication(updated);
      } else {
        const created = await api.post("/applications/", {
          job_id: parseInt(id, 10) || id,
          status: newStatus,
        });
        setApplication(created);
      }
      notify(`Application status updated to "${newStatus}".`);
    } catch {
      notify("Failed to update application status.", "error");
    } finally {
      setSavingApp(false);
    }
  };

  // External Application tracking handler
  const handleExternalApply = (jobData, url) => {
    if (url) {
      window.open(url, "_blank", "noopener,noreferrer");
    }
    setExternalApplyPromptJob(jobData);
  };

  // Tailoring result completion
  const handleTailorSuccess = (result) => {
    setTailorModalOpen(false);
    setTailoredResult(result);
    notify("Resume successfully tailored for this opportunity!");
  };

  const overallScore = useMemo(() => {
    return matchData?.overall_score ?? job?.match_score ?? 0;
  }, [matchData, job]);

  if (loading) {
    return (
      <div className="page job-details-page">
        <div className="details-breadcrumb">
          <Link to="/discover" className="breadcrumb-link">
            <ArrowLeft size={16} />
            <span>Back to Opportunities</span>
          </Link>
        </div>
        <div className="skeleton" style={{ height: "140px", borderRadius: "var(--radius-lg)" }} />
        <div className="skeleton" style={{ height: "64px", marginTop: "var(--space-4)", borderRadius: "var(--radius-md)" }} />
        <div className="grid-2" style={{ marginTop: "var(--space-6)" }}>
          <SkeletonCard lines={6} />
          <SkeletonCard lines={4} />
        </div>
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="page job-details-page">
        <div className="details-breadcrumb">
          <Link to="/discover" className="breadcrumb-link">
            <ArrowLeft size={16} />
            <span>Back to Opportunities</span>
          </Link>
        </div>
        <div className="card text-center" style={{ padding: "var(--space-12)" }}>
          <h2>Opportunity Not Found</h2>
          <p className="text-secondary" style={{ marginTop: "var(--space-2)" }}>
            {error || "This role may have been removed or is no longer accessible in your workspace."}
          </p>
          <div style={{ marginTop: "var(--space-6)" }}>
            <Link to="/discover" className="btn btn-primary">
              <ArrowLeft size={16} />
              <span>Browse All Opportunities</span>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page job-details-page">
      {/* Toast Notification */}
      {notification && (
        <div className={`toast toast-${notification.type}`} role="status">
          {notification.msg}
        </div>
      )}

      {/* 1. Job Hero Header */}
      <JobHeroHeader job={job} score={overallScore} />

      {/* 2. Primary & Secondary Action Bar (Desktop) */}
      <JobActionBar
        job={job}
        application={application}
        savingApp={savingApp}
        onTailor={() => setTailorModalOpen(true)}
        onAnalyzeResume={() => setAnalyzeModalOpen(true)}
        onCoverLetter={() => setCoverOpen(true)}
        onUpdateStatus={handleUpdateStatus}
        onExternalApply={handleExternalApply}
      />

      {/* 3. Mobile Segmented Nav (Visible < 1024px) */}
      <nav className="job-details-mobile-nav" aria-label="Job Details Sections">
        <div className="mobile-nav-pill-group" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={mobileTab === "overview"}
            className={`mobile-nav-pill ${mobileTab === "overview" ? "active" : ""}`}
            onClick={() => handleSelectMobileTab("overview")}
          >
            <FileText size={15} aria-hidden="true" />
            <span>Overview & Skills</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mobileTab === "fit"}
            className={`mobile-nav-pill ${mobileTab === "fit" ? "active" : ""}`}
            onClick={() => handleSelectMobileTab("fit")}
          >
            <CheckCircle2 size={15} aria-hidden="true" />
            <span>
              Fit Analysis {overallScore > 0 ? `(${overallScore}%)` : ""}
            </span>
          </button>
        </div>
      </nav>

      {/* 4. Main 2-Column Content Grid */}
      <main className="job-details-content-grid">
        {/* Left Column: Job Description & Technical Requirements (65%) */}
        <div
          className={`job-overview-col ${
            mobileTab !== "overview" ? "mobile-hidden" : ""
          }`}
        >
          <JobOverviewPanel job={job} />
        </div>

        {/* Right Column: Live Fit Analysis & Skill Alignment (35%) */}
        <div
          className={`job-fit-col ${mobileTab !== "fit" ? "mobile-hidden" : ""}`}
        >
          <JobFitPanel
            matchData={matchData}
            job={job}
            loading={recalculating}
            onRecalculate={handleRecalculateMatch}
            onAnalyzeResume={() => setAnalyzeModalOpen(true)}
            onTailor={() => setTailorModalOpen(true)}
          />
        </div>
      </main>

      {/* 5. Mobile Sticky Bottom Action Bar (< 768px, elevated above BottomNav) */}
      <JobActionBar
        job={job}
        application={application}
        savingApp={savingApp}
        onTailor={() => setTailorModalOpen(true)}
        onCoverLetter={() => setCoverOpen(true)}
        onAnalyzeResume={() => setAnalyzeModalOpen(true)}
        onUpdateStatus={handleUpdateStatus}
        onExternalApply={handleExternalApply}
        isStickyMobile
      />

      {/* 6. In-Context Tailoring Wizard Modal */}
      {tailorModalOpen && (
        <TailoringModal
          isOpen={tailorModalOpen}
          onClose={() => setTailorModalOpen(false)}
          job={job}
          matchData={matchData}
          onSuccess={handleTailorSuccess}
        />
      )}

      {/* 7. In-Context Tailored Resume Preview Drawer */}
      {tailoredResult && (
        <TailoredResumeDrawer
          isOpen={Boolean(tailoredResult)}
          onClose={() => setTailoredResult(null)}
          result={tailoredResult}
          job={job}
          existingScore={overallScore}
          onRegenerate={() => {
            setTailoredResult(null);
            setTailorModalOpen(true);
          }}
        />
      )}

      {/* 8. Cover Letter Modal */}
      {coverOpen && (
        <CoverLetterModal
          isOpen={coverOpen}
          onClose={() => setCoverOpen(false)}
          job={job}
        />
      )}

      {/* 9. In-Context Resume Match Analysis Modal */}
      {analyzeModalOpen && (
        <AnalyzeResumeModal
          isOpen={analyzeModalOpen}
          onClose={() => setAnalyzeModalOpen(false)}
          job={job}
          onTailorResume={() => {
            setAnalyzeModalOpen(false);
            setTailorModalOpen(true);
          }}
        />
      )}

      {/* 10. External Application Follow-up Toast */}
      {externalApplyPromptJob && (
        <ExternalApplyToast
          job={externalApplyPromptJob}
          onConfirm={async () => {
            await handleUpdateStatus("Applied");
            setExternalApplyPromptJob(null);
          }}
          onDismiss={() => setExternalApplyPromptJob(null)}
        />
      )}
    </div>
  );
}
