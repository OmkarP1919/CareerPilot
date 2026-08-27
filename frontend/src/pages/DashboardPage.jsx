import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { api } from "../services/api";
import StatusBadge from "../components/StatusBadge";
import ScoreBadge from "../components/ScoreBadge";
import EmptyState from "../components/EmptyState";
import { SkeletonCard } from "../components/Skeleton";
import {
  Compass,
  Briefcase,
  Target,
  FileText,
  TrendingUp,
  ArrowRight,
  Sparkles,
  CheckCircle2,
  Calendar,
  Zap,
  User,
  Upload,
} from "lucide-react";

export default function DashboardPage() {
  const { currentUser } = useAuth();
  const [data, setData] = useState(null);
  const [recommended, setRecommended] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      try {
        const [dashResult, recsResult] = await Promise.all([
          api.get("/analytics/dashboard").catch(() => null),
          api.get("/jobs/recommended").catch(() => []),
        ]);
        setData(dashResult);
        setRecommended(Array.isArray(recsResult) ? recsResult.slice(0, 3) : []);
      } catch (err) {
        console.error("Failed to load dashboard data:", err);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  const displayName = currentUser?.displayName || currentUser?.email?.split("@")[0] || "there";

  // Determine intelligent greeting based on local time
  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";

  // Compute the single highest priority "Next Best Action"
  const getNextBestAction = () => {
    if (!data) {
      return {
        title: "Build your professional career profile",
        desc: "Add your technical skills, projects, and work experience to start generating precision match scores.",
        link: "/profile",
        cta: "Complete Profile",
        icon: User,
        variant: "accent",
      };
    }

    if (data.offer_count > 0) {
      return {
        title: `You have ${data.offer_count} active job offer${data.offer_count > 1 ? "s" : ""}!`,
        desc: "Review your offer details, milestones, and compensation notes in your application pipeline.",
        link: "/pipeline",
        cta: "View Pipeline",
        icon: CheckCircle2,
        variant: "success",
      };
    }

    if (data.interview_count > 0) {
      return {
        title: `${data.interview_count} interview round${data.interview_count > 1 ? "s" : ""} in progress`,
        desc: "Keep momentum high. Review role requirements and prepare your project talking points.",
        link: "/pipeline",
        cta: "Prepare Interviews",
        icon: Calendar,
        variant: "accent",
      };
    }

    if (data.high_match_jobs > 0 || recommended.length > 0) {
      return {
        title: `${data.high_match_jobs || recommended.length} high-fit opportunities available`,
        desc: "New roles closely align with your technical skills. Review match breakdowns and submit applications.",
        link: "/discover",
        cta: "Review Opportunities",
        icon: Sparkles,
        variant: "accent",
      };
    }

    if (data.total_jobs === 0) {
      return {
        title: "Discover your first opportunities",
        desc: "Search aggregated job boards or add custom target roles to calculate transparent match scores.",
        link: "/discover",
        cta: "Discover Jobs",
        icon: Compass,
        variant: "accent",
      };
    }

    return {
      title: "Keep your application pipeline active",
      desc: "Track submissions, follow up on pending reviews, and inspect frequently missing skills.",
      link: "/pipeline",
      cta: "Open Pipeline",
      icon: Zap,
      variant: "neutral",
    };
  };

  const nextAction = getNextBestAction();

  if (loading) {
    return (
      <div className="page">
        <div className="page-header">
          <div className="skeleton skeleton-title" style={{ width: 280, height: 32 }} />
          <div className="skeleton skeleton-text" style={{ width: 400, marginTop: 8 }} />
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
      {/* === Executive Briefing Header === */}
      <header className="page-header">
        <div className="page-header-row">
          <div>
            <h1>{greeting}, {displayName}</h1>
            <p>Welcome to your personal career command center</p>
          </div>
          <div className="page-header-actions">
            <Link to="/discover" className="btn btn-primary btn-sm">
              <Compass size={14} />
              <span>Discover Roles</span>
            </Link>
          </div>
        </div>
      </header>

      {/* === Next Best Action Banner === */}
      <section className={`command-action-banner banner-${nextAction.variant}`} aria-label="Next best action">
        <div className="command-action-icon">
          <nextAction.icon size={24} />
        </div>
        <div className="command-action-content">
          <div className="command-action-eyebrow">Recommended Next Step</div>
          <h2 className="command-action-title">{nextAction.title}</h2>
          <p className="command-action-desc">{nextAction.desc}</p>
        </div>
        <div className="command-action-cta">
          <Link to={nextAction.link} className="btn btn-primary">
            <span>{nextAction.cta}</span>
            <ArrowRight size={16} />
          </Link>
        </div>
      </section>

      {/* === Workspace Content Grid === */}
      <div className="command-workspace-grid">
        {/* Left Column: Top Opportunities Spotlight & Active Pipeline */}
        <div className="command-main-column">
          {/* Top Opportunities Spotlight */}
          <div className="command-section">
            <div className="section-header">
              <h2>
                <Sparkles size={18} className="text-accent" />
                <span>Top Opportunities Spotlight</span>
              </h2>
              <Link to="/discover" className="btn btn-ghost btn-sm">
                <span>View all</span>
                <ArrowRight size={14} />
              </Link>
            </div>

            {recommended.length > 0 ? (
              <div className="command-opportunities-list">
                {recommended.map((r) => {
                  const job = r.job || r;
                  return (
                    <div key={job.id} className="command-opportunity-card">
                      <div className="opportunity-card-top">
                        <div>
                          <Link to={`/discover/${job.id}`} className="opportunity-role-title">
                            {job.title}
                          </Link>
                          <span className="opportunity-company">{job.company}</span>
                        </div>
                        <ScoreBadge score={r.score} />
                      </div>

                      {r.matched_skills?.length > 0 && (
                        <div className="opportunity-skills-row">
                          <span className="opportunity-skills-label">Matched:</span>
                          {r.matched_skills.slice(0, 4).map((s) => (
                            <span key={s} className="skill-tag skill-matched">{s}</span>
                          ))}
                          {r.matched_skills.length > 4 && (
                            <span className="skill-tag skill-more">+{r.matched_skills.length - 4}</span>
                          )}
                        </div>
                      )}

                      <div className="opportunity-card-footer">
                        <span className="opportunity-location">
                          {job.location || "Remote friendly"}
                        </span>
                        <Link to={`/discover/${job.id}`} className="btn btn-outline btn-sm">
                          View Opportunity
                        </Link>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : data?.recent_jobs?.length > 0 ? (
              <div className="command-opportunities-list">
                {data.recent_jobs.slice(0, 3).map((job) => (
                  <div key={job.id} className="command-opportunity-card">
                    <div className="opportunity-card-top">
                      <div>
                        <Link to={`/discover/${job.id}`} className="opportunity-role-title">
                          {job.title}
                        </Link>
                        <span className="opportunity-company">{job.company}</span>
                      </div>
                    </div>
                    <div className="opportunity-card-footer">
                      <span className="opportunity-location">
                        {job.location || "Location not specified"}
                      </span>
                      <Link to={`/discover/${job.id}`} className="btn btn-outline btn-sm">
                        View Opportunity
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState
                icon={Briefcase}
                title="No opportunities tracked yet"
                text="Discover matching roles from top tech boards or add your own target positions."
                action={
                  <Link to="/discover" className="btn btn-primary btn-sm">
                    <Compass size={14} /> Discover Jobs
                  </Link>
                }
              />
            )}
          </div>

          {/* Active Application Pipeline Momentum */}
          <div className="command-section">
            <div className="section-header">
              <h2>
                <FileText size={18} className="text-accent" />
                <span>Application Momentum</span>
              </h2>
              <Link to="/pipeline" className="btn btn-ghost btn-sm">
                <span>Open Pipeline</span>
                <ArrowRight size={14} />
              </Link>
            </div>

            {data?.recent_applications?.length > 0 ? (
              <div className="command-pipeline-list">
                {data.recent_applications.slice(0, 4).map((app) => (
                  <div key={app.id} className="command-pipeline-row">
                    <div className="pipeline-row-info">
                      <Link to={`/discover/${app.job_id}`} className="pipeline-row-role">
                        {app.job_title || "Target Role"}
                      </Link>
                      <span className="pipeline-row-company">{app.job_company || "Company"}</span>
                    </div>
                    <StatusBadge status={app.status} />
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState
                icon={FileText}
                title="No applications in pipeline"
                text="Track your first submitted application to monitor your interview progress."
                action={
                  <Link to="/pipeline" className="btn btn-secondary btn-sm">
                    Track Application
                  </Link>
                }
              />
            )}
          </div>
        </div>

        {/* Right Column: Career Health & Shortcuts */}
        <div className="command-side-column">
          {/* Match Score Health */}
          <div className="card">
            <div className="card-header">
              <h3>Match Intelligence Health</h3>
            </div>
            <div className="card-body">
              {data?.average_match_score != null ? (
                <div className="health-score-widget">
                  <div className="health-score-ring">
                    <ScoreBadge score={data.average_match_score} size="large" />
                  </div>
                  <p className="health-score-desc">
                    Average fit across all evaluated positions. Roles above 80% have the highest interview likelihood.
                  </p>
                </div>
              ) : (
                <div className="health-score-empty">
                  <p>Run your first match analysis on any job to view your fit score.</p>
                  <Link to="/discover" className="btn btn-outline btn-sm">
                    Find a job to match
                  </Link>
                </div>
              )}
            </div>
          </div>

          {/* Pipeline Funnel Snapshot */}
          <div className="card">
            <div className="card-header">
              <h3>Pipeline Snapshot</h3>
              <Link to="/insights" className="btn-link" style={{ fontSize: "var(--text-xs)" }}>
                Insights
              </Link>
            </div>
            <div className="card-body">
              <div className="snapshot-stat-rows">
                <div className="snapshot-stat-item">
                  <span className="snapshot-stat-label">Saved</span>
                  <span className="snapshot-stat-value">{data?.saved_count || 0}</span>
                </div>
                <div className="snapshot-stat-item">
                  <span className="snapshot-stat-label">Applied</span>
                  <span className="snapshot-stat-value">{data?.applied_count || 0}</span>
                </div>
                <div className="snapshot-stat-item">
                  <span className="snapshot-stat-label">Interviews</span>
                  <span className="snapshot-stat-value text-accent font-bold">{data?.interview_count || 0}</span>
                </div>
                <div className="snapshot-stat-item">
                  <span className="snapshot-stat-label">Offers</span>
                  <span className="snapshot-stat-value text-success font-bold">{data?.offer_count || 0}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Quick Workspace Shortcuts */}
          <div className="card">
            <div className="card-header">
              <h3>Workspace Shortcuts</h3>
            </div>
            <div className="card-body">
              <nav className="shortcuts-nav">
                <Link to="/profile" className="shortcut-link">
                  <User size={16} />
                  <span>Update Career Profile</span>
                </Link>
                <Link to="/resumes" className="shortcut-link">
                  <Upload size={16} />
                  <span>Upload or Set Master Resume</span>
                </Link>
                <Link to="/insights" className="shortcut-link">
                  <TrendingUp size={16} />
                  <span>Inspect Skill Gaps & Trends</span>
                </Link>
              </nav>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
