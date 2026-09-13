import { useState, useEffect, useCallback, useMemo } from "react";
import { useAuth } from "../context/AuthContext";
import { useTranslation } from "../context/LanguageContext";
import { api } from "../services/api";
import { normalizeJob } from "../components/jobs/jobUtils";
import { SkeletonCard } from "../components/Skeleton";

// Clean Home Subcomponents
import HomeNextAction from "../components/dashboard/HomeNextAction";
import HomeRecommendedJobs from "../components/dashboard/HomeRecommendedJobs";
import HomePipelineSummary from "../components/dashboard/HomePipelineSummary";
import { determineNextAction } from "../components/dashboard/dashboardUtils";

export default function DashboardPage() {
  const { currentUser } = useAuth();
  const { t } = useTranslation();

  const [recommended, setRecommended] = useState([]);
  const [profileData, setProfileData] = useState(null);
  const [resumes, setResumes] = useState([]);
  const [applications, setApplications] = useState([]);
  const [interviews, setInterviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [savedJobIds, setSavedJobIds] = useState(() => new Set());

  const loadData = useCallback(async () => {
    try {
      const [recsResult, profResult, resResult, appsResult] = await Promise.all([
        api.get("/jobs/recommended").catch(() => []),
        api.get("/profile/").catch(() => null),
        api.get("/resumes").catch(() => []),
        api.get("/applications/").catch(() => []),
      ]);

      const normalizedRecs = (Array.isArray(recsResult) ? recsResult : [])
        .map((item) => normalizeJob(item))
        .filter(Boolean);

      const appsList = Array.isArray(appsResult) ? appsResult : [];

      setRecommended(normalizedRecs);
      setProfileData(profResult);
      setResumes(Array.isArray(resResult) ? resResult : []);
      setApplications(appsList);

      // Track saved job ids
      const savedIds = new Set(
        appsList
          .filter((a) => a.job_id)
          .map((a) => a.job_id)
      );
      setSavedJobIds(savedIds);

      // Fetch active interviews for first 5 applications to check for upcoming interviews
      const appSubset = appsList.slice(0, 5);
      if (appSubset.length > 0) {
        const interviewArrays = await Promise.all(
          appSubset.map((app) =>
            api.getApplicationInterviews(app.id).catch(() => [])
          )
        );
        const allInterviews = interviewArrays.flat().filter(Boolean);
        setInterviews(allInterviews);
      }
    } catch (err) {
      console.error("Home data load error:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Handle Save / Unsave from Home job cards
  const handleToggleSave = async (job) => {
    if (!job?.id) return;
    const isSaved = savedJobIds.has(job.id);

    try {
      if (isSaved) {
        const app = applications.find((a) => a.job_id === job.id);
        if (app?.id) {
          await api.delete(`/applications/${app.id}`);
          setApplications((prev) => prev.filter((a) => a.id !== app.id));
          setSavedJobIds((prev) => {
            const next = new Set(prev);
            next.delete(job.id);
            return next;
          });
        }
      } else {
        const createdApp = await api.post("/applications/", {
          job_id: job.id,
          status: "Saved",
        });
        setApplications((prev) => [createdApp, ...prev]);
        setSavedJobIds((prev) => new Set([...prev, job.id]));
      }
    } catch {
      // Keep UI resilient on failure
    }
  };

  const displayName = currentUser?.displayName || currentUser?.email?.split("@")[0] || "there";

  // Time-aware greeting
  const hour = new Date().getHours();
  const greeting =
    hour < 12
      ? t("dash.greetingMorning", "Good morning")
      : hour < 18
      ? t("dash.greetingAfternoon", "Good afternoon")
      : t("dash.greetingEvening", "Good evening");

  // Determine single dominant next action
  const nextAction = useMemo(() => {
    return determineNextAction({
      resumes,
      profile: profileData,
      applications,
      recommendedJobs: recommended,
      interviews,
    });
  }, [resumes, profileData, applications, recommended, interviews]);

  if (loading) {
    return (
      <div className="page home-page-unified" aria-busy="true">
        <header className="page-header home-header">
          <div className="skeleton" style={{ height: "32px", width: "220px" }} />
          <div className="skeleton" style={{ height: "16px", width: "160px", marginTop: "8px" }} />
        </header>
        <div className="stack" style={{ gap: "var(--space-6)" }}>
          <SkeletonCard />
          <div className="grid-2">
            <SkeletonCard />
            <SkeletonCard />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page dashboard-page home-page-unified">
      {/* 1. Greeting Header */}
      <header className="page-header home-header">
        <h1 className="home-greeting">
          {greeting}, {displayName}
        </h1>
        <p className="home-subtitle">Here is your next recommended step.</p>
      </header>

      {/* 2. Dominant Next Action Card */}
      <HomeNextAction action={nextAction} />

      {/* 3. For You: Curated Opportunities (Max 2-3) */}
      <HomeRecommendedJobs
        jobs={recommended}
        savedJobIds={savedJobIds}
        onToggleSave={handleToggleSave}
      />

      {/* 4. Small Compact Application Status */}
      <HomePipelineSummary applications={applications} />
    </div>
  );
}
