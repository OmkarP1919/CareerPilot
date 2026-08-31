import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useTranslation } from "../context/LanguageContext";
import { api } from "../services/api";
import ScoreBadge from "../components/ScoreBadge";
import { SkeletonCard } from "../components/Skeleton";
import OnboardingModal from "../components/OnboardingModal";
import {
  Compass,
  Briefcase,
  FileText,
  Layers,
  ArrowRight,
  Sparkles,
  CheckCircle2,
  Upload,
  Clock,
  MapPin,
} from "lucide-react";

export default function DashboardPage() {
  const { currentUser } = useAuth();
  const { t } = useTranslation();

  const [dashData, setDashData] = useState(null);
  const [recommended, setRecommended] = useState([]);
  const [profileData, setProfileData] = useState(null);
  const [resumes, setResumes] = useState([]);
  const [applications, setApplications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showOnboarding, setShowOnboarding] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [dashResult, recsResult, profResult, resResult, appsResult] = await Promise.all([
        api.get("/analytics/dashboard").catch(() => null),
        api.get("/jobs/recommended").catch(() => []),
        api.get("/profile/").catch(() => null),
        api.get("/resumes").catch(() => []),
        api.get("/applications/").catch(() => []),
      ]);

      const normalizedRecs = (Array.isArray(recsResult) ? recsResult : []).map((item) => {
        if (item && item.job) {
          return {
            ...item.job,
            match_score: item.match_score ?? item.job.match_score ?? 0,
            matched_skills: item.matched_skills ?? item.job.matched_skills ?? [],
            missing_skills: item.missing_skills ?? item.job.missing_skills ?? [],
            relevant_projects: item.relevant_projects ?? item.job.relevant_projects ?? [],
          };
        }
        return item;
      });

      setDashData(dashResult);
      setRecommended(normalizedRecs);
      setProfileData(profResult);
      setResumes(Array.isArray(resResult) ? resResult : []);
      setApplications(Array.isArray(appsResult) ? appsResult : []);

      // If user has zero profile skills and zero resumes, auto-prompt onboarding once
      if (
        (!profResult?.skills || profResult.skills.length === 0) &&
        (!resResult || resResult.length === 0) &&
        !sessionStorage.getItem("cp_onboarding_shown")
      ) {
        setShowOnboarding(true);
        sessionStorage.setItem("cp_onboarding_shown", "true");
      }
    } catch (err) {
      console.error("Dashboard data load error:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const displayName = currentUser?.displayName || currentUser?.email?.split("@")[0] || "there";

  // Time-aware greeting
  const hour = new Date().getHours();
  const greeting =
    hour < 12
      ? t("dash.greetingMorning", "Good morning")
      : hour < 18
      ? t("dash.greetingAfternoon", "Good afternoon")
      : t("dash.greetingEvening", "Good evening");

  // Determine user state
  const hasProfile = Boolean(profileData?.skills && profileData.skills.length > 0);
  const hasResumes = resumes.length > 0;
  const hasApplications = applications.length > 0;

  // Profile readiness percentage
  let readiness = 20;
  if (currentUser?.displayName) readiness += 15;
  if (hasResumes) readiness += 25;
  if (hasProfile) readiness += 25;
  if (profileData?.experiences?.length > 0 || profileData?.projects?.length > 0) readiness += 15;
  readiness = Math.min(100, readiness);

  // Highest fit job (State C & D)
  const bestOpportunity = recommended.length > 0 ? recommended[0] : null;

  if (loading) {
    return (
      <div className="page">
        <header className="page-header">
          <div className="skeleton" style={{ height: "36px", width: "260px" }} />
          <div className="skeleton" style={{ height: "20px", width: "340px", marginTop: "8px" }} />
        </header>
        <div className="stack" style={{ gap: "var(--space-6)" }}>
          <SkeletonCard />
          <div className="grid-3">
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page dashboard-page">
      {/* Page Header */}
      <header className="page-header">
        <div className="page-header-row">
          <div>
            <h1>{greeting}, {displayName}</h1>
            <p>{t("dash.subtitle", "Here's what needs your attention.")}</p>
          </div>

          <div className="page-header-actions">
            <Link to="/discover" className="btn btn-primary">
              <Compass size={16} />
              <span>{t("action.findJobsForMe", "Find Jobs for Me")}</span>
            </Link>
          </div>
        </div>
      </header>

      {/* =========================================================================
          STATE A: NEW USER / INCOMPLETE PROFILE
          ========================================================================= */}
      {!hasProfile && !hasResumes && (
        <section className="card state-banner-card">
          <div className="state-banner-inner">
            <div className="state-banner-text">
              <div className="state-badge">
                <Sparkles size={14} />
                <span>Get Started</span>
              </div>
              <h2>Let's get your profile ready for precision job matching</h2>
              <p>
                CareerPilot compares your actual skills and projects against live job listings.
                Complete your profile or upload a resume to unlock tailored recommendations.
              </p>
              <div className="state-progress-row">
                <span className="text-sm font-medium">Profile Readiness: {readiness}%</span>
                <div className="score-bar-track" style={{ flex: 1, maxWidth: "240px" }}>
                  <div
                    className="score-bar-fill"
                    style={{ width: `${readiness}%`, background: "var(--accent)" }}
                  />
                </div>
              </div>
            </div>
            <div className="state-banner-actions">
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => setShowOnboarding(true)}
              >
                <span>Complete Profile</span>
                <ArrowRight size={16} />
              </button>
              <Link to="/resumes" className="btn btn-secondary">
                <Upload size={16} />
                <span>Upload Resume</span>
              </Link>
            </div>
          </div>
        </section>
      )}

      {/* =========================================================================
          YOUR NEXT BEST OPPORTUNITY (Primary Card)
          ========================================================================= */}
      {bestOpportunity && (
        <section className="next-opportunity-section">
          <div className="section-label-row">
            <span className="section-eyebrow">{t("dash.nextBestOpportunity", "Your Next Best Opportunity")}</span>
          </div>

          <div className="card highlight-card">
            <div className="highlight-card-body">
              <div className="highlight-card-main">
                <div className="highlight-header-row">
                  <div>
                    <h2 className="highlight-title">{bestOpportunity.title}</h2>
                    <p className="highlight-company">
                      {bestOpportunity.company}
                      {bestOpportunity.location && ` • ${bestOpportunity.location}`}
                      {bestOpportunity.employment_type && ` • ${bestOpportunity.employment_type}`}
                      {bestOpportunity.experience_level && ` • ${bestOpportunity.experience_level}`}
                    </p>
                  </div>

                  <div className="highlight-score-wrap">
                    <ScoreBadge score={bestOpportunity.match_score || 0} size="large" />
                  </div>
                </div>

                {/* Skills Preview */}
                {Array.isArray(bestOpportunity.required_skills) && bestOpportunity.required_skills.length > 0 && (
                  <div className="highlight-skills-row">
                    {bestOpportunity.required_skills.slice(0, 6).map((sk) => (
                      <span key={sk} className="skill-chip match">
                        {sk}
                      </span>
                    ))}
                  </div>
                )}

                {/* Match Summary points */}
                <div className="highlight-points-row">
                  <span className="point-item positive">
                    <CheckCircle2 size={15} className="text-success" />
                    <span>High alignment with your technical profile</span>
                  </span>
                  {bestOpportunity.created_at && (
                    <span className="point-item neutral">
                      <Clock size={15} className="text-tertiary" />
                      <span>Added recently</span>
                    </span>
                  )}
                </div>
              </div>

              <div className="highlight-card-actions">
                <Link to={`/discover/${bestOpportunity.id}`} className="btn btn-primary btn-block">
                  <span>{t("action.viewOpportunity", "View Opportunity")}</span>
                  <ArrowRight size={16} />
                </Link>
                <Link
                  to={`/discover/${bestOpportunity.id}`}
                  state={{ openTailor: true }}
                  className="btn btn-secondary btn-block"
                >
                  <Sparkles size={16} />
                  <span>{t("action.tailorResume", "Tailor My Resume")}</span>
                </Link>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* =========================================================================
          CONTINUE WHERE YOU LEFT OFF (Actionable Guidance)
          ========================================================================= */}
      <section className="continue-section">
        <div className="section-label-row">
          <span className="section-eyebrow">{t("dash.continueWhereLeftOff", "Continue Where You Left Off")}</span>
        </div>

        <div className="grid-3">
          {/* Resume state card */}
          <div className="card guidance-card">
            <div className="guidance-icon-wrap accent">
              <FileText size={20} />
            </div>
            <div className="guidance-content">
              <h3>{hasResumes ? "Resume is ready" : "Upload your resume"}</h3>
              <p>
                {hasResumes
                  ? `${resumes.length} active resume${resumes.length > 1 ? "s" : ""} uploaded and parsed.`
                  : "Upload a PDF resume to enable AI tailoring and keyword analysis."}
              </p>
              <Link to="/resumes" className="guidance-link">
                <span>{hasResumes ? "Manage Resumes" : "Upload Resume"}</span>
                <ArrowRight size={14} />
              </Link>
            </div>
          </div>

          {/* Applications state card */}
          <div className="card guidance-card">
            <div className="guidance-icon-wrap success">
              <Layers size={20} />
            </div>
            <div className="guidance-content">
              <h3>
                {hasApplications
                  ? `${applications.length} Active Application${applications.length > 1 ? "s" : ""}`
                  : "Track your job submissions"}
              </h3>
              <p>
                {hasApplications
                  ? `${dashData?.interview_count || 0} interviews scheduled · ${dashData?.offer_count || 0} offers received.`
                  : "Move saved roles through Applied, Interview, and Offer milestones."}
              </p>
              <Link to="/pipeline" className="guidance-link">
                <span>View Applications</span>
                <ArrowRight size={14} />
              </Link>
            </div>
          </div>

          {/* Opportunities discovery card */}
          <div className="card guidance-card">
            <div className="guidance-icon-wrap warning">
              <Compass size={20} />
            </div>
            <div className="guidance-content">
              <h3>{dashData?.high_match_jobs ? `${dashData.high_match_jobs} Strong Matches` : "Discover opportunities"}</h3>
              <p>
                {recommended.length > 0
                  ? "Roles closely aligned with your verified background."
                  : "Run personalized job discovery to fetch roles fitting your profile."}
              </p>
              <Link to="/discover" className="guidance-link">
                <span>Explore Jobs</span>
                <ArrowRight size={14} />
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* =========================================================================
          RECOMMENDED FOR YOU (3-4 Job Cards)
          ========================================================================= */}
      {recommended.length > 1 && (
        <section className="recommended-section">
          <div className="section-header-row">
            <div>
              <h2>{t("dash.recommendedForYou", "Recommended For You")}</h2>
              <p>Opportunities matching your technical profile and preferences</p>
            </div>
            <Link to="/discover" className="btn btn-ghost btn-sm">
              <span>{t("dash.viewAllJobs", "View All Opportunities")}</span>
              <ArrowRight size={14} />
            </Link>
          </div>

          <div className="grid-3">
            {recommended.slice(1, 4).map((job) => (
              <div key={job.id} className="card job-card-mini">
                <div className="job-card-mini-top">
                  <div>
                    <h3 className="job-title-compact">{job.title}</h3>
                    <p className="job-company-compact">{job.company}</p>
                  </div>
                  <ScoreBadge score={job.match_score || 0} />
                </div>

                <div className="job-meta-row">
                  {job.location && (
                    <span className="meta-item">
                      <MapPin size={13} />
                      <span>{job.location}</span>
                    </span>
                  )}
                  {job.employment_type && (
                    <span className="meta-item">
                      <Briefcase size={13} />
                      <span>{job.employment_type}</span>
                    </span>
                  )}
                </div>

                {Array.isArray(job.required_skills) && job.required_skills.length > 0 && (
                  <div className="job-skills-compact">
                    {job.required_skills.slice(0, 3).map((s) => (
                      <span key={s} className="skill-chip-sm">
                        {s}
                      </span>
                    ))}
                  </div>
                )}

                <div className="job-card-mini-footer">
                  <Link to={`/discover/${job.id}`} className="btn btn-secondary btn-sm btn-block">
                    <span>{t("action.viewOpportunity", "View Opportunity")}</span>
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* =========================================================================
          APPLICATION ACTIVITY & COMPACT METRICS
          ========================================================================= */}
      <section className="activity-section">
        <div className="section-header-row">
          <div>
            <h2>{t("dash.applicationActivity", "Application Activity")}</h2>
            <p>Your current pipeline velocity and milestone progress</p>
          </div>
          <Link to="/pipeline" className="btn btn-ghost btn-sm">
            <span>View Full Pipeline</span>
            <ArrowRight size={14} />
          </Link>
        </div>

        <div className="card pipeline-summary-card">
          <div className="pipeline-funnel-strip">
            <div className="funnel-step">
              <span className="funnel-label">Saved</span>
              <span className="funnel-count font-mono">
                {applications.filter((a) => a.status?.toLowerCase() === "saved").length}
              </span>
            </div>
            <div className="funnel-divider">→</div>
            <div className="funnel-step">
              <span className="funnel-label">Applied</span>
              <span className="funnel-count font-mono">
                {applications.filter((a) => a.status?.toLowerCase() === "applied").length}
              </span>
            </div>
            <div className="funnel-divider">→</div>
            <div className="funnel-step">
              <span className="funnel-label">Interviewing</span>
              <span className="funnel-count font-mono">
                {applications.filter((a) => a.status?.toLowerCase() === "interview").length}
              </span>
            </div>
            <div className="funnel-divider">→</div>
            <div className="funnel-step">
              <span className="funnel-label">Offers</span>
              <span className="funnel-count font-mono text-success">
                {applications.filter((a) => a.status?.toLowerCase() === "offer").length}
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Onboarding Dialog */}
      <OnboardingModal
        isOpen={showOnboarding}
        onClose={() => setShowOnboarding(false)}
        profileData={profileData}
        resumesCount={resumes.length}
      />
    </div>
  );
}
