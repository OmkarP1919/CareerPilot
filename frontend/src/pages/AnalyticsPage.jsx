import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import EmptyState from "../components/EmptyState";
import { SkeletonCard } from "../components/Skeleton";
import {
  BarChart3,
  Briefcase,
  Target,
  FileText,
  TrendingUp,
  AlertCircle,
  CheckCircle2,
  Sparkles,
  Compass,
  ArrowRight,
} from "lucide-react";

export default function AnalyticsPage() {
  const [dashboard, setDashboard] = useState(null);
  const [funnel, setFunnel] = useState(null);
  const [skills, setSkills] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const [d, f, s] = await Promise.all([
          api.get("/analytics/dashboard").catch(() => null),
          api.get("/analytics/application-funnel").catch(() => null),
          api.get("/analytics/skills").catch(() => null),
        ]);
        setDashboard(d);
        setFunnel(f);
        setSkills(s);
      } catch (err) {
        console.error("Failed to load analytics:", err);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

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

  const hasData = dashboard && (dashboard.total_jobs > 0 || dashboard.total_applications > 0);
  const hasFunnel = funnel && funnel.funnel?.length > 0;
  const hasSkills = skills && skills.total_analyses > 0;

  if (!hasData && !hasFunnel && !hasSkills) {
    return (
      <div className="page">
        <header className="page-header">
          <h1>Career Insights & Analytics</h1>
          <p>Strategic diagnostics across job match health and application velocity</p>
        </header>
        <EmptyState
          icon={BarChart3}
          title="No analytics generated yet"
          text="Run match analyses and track applications to unlock conversion funnel data and skill coaching insights."
          action={
            <Link to="/discover" className="btn btn-primary btn-sm">
              <Compass size={14} /> Discover Opportunities
            </Link>
          }
        />
      </div>
    );
  }

  const maxFunnel = funnel ? Math.max(...funnel.funnel.map((f) => f.count), 1) : 1;

  const statCards = [
    { label: "Tracked Opportunities", value: dashboard?.total_jobs ?? 0, icon: Briefcase },
    { label: "High Fit Matches", value: dashboard?.high_match_jobs ?? 0, icon: Target },
    { label: "Active Submissions", value: dashboard?.total_applications ?? 0, icon: FileText },
    {
      label: "Average Fit Score",
      value: dashboard?.average_match_score != null ? `${dashboard.average_match_score}%` : "—",
      icon: TrendingUp,
    },
  ];

  const distributionItems = [
    { label: "Saved", value: dashboard?.saved_count || 0, color: "var(--slate-400)" },
    { label: "Applied", value: dashboard?.applied_count || 0, color: "var(--accent)" },
    { label: "Interviewing", value: dashboard?.interview_count || 0, color: "var(--purple)" },
    { label: "Offers", value: dashboard?.offer_count || 0, color: "var(--success)" },
    { label: "Rejected", value: dashboard?.rejected_count || 0, color: "var(--danger)" },
  ];

  return (
    <div className="page">
      {/* === Page Header === */}
      <header className="page-header">
        <div className="page-header-row">
          <div>
            <h1>Career Insights & Analytics</h1>
            <p>Strategic intelligence across your applications and skill gaps</p>
          </div>
          <div className="page-header-actions">
            <Link to="/pipeline" className="btn btn-outline btn-sm">
              <span>View Pipeline</span>
              <ArrowRight size={14} />
            </Link>
          </div>
        </div>
      </header>

      {/* === Executive Summary Callout === */}
      {skills && skills.total_analyses > 0 && (
        <section className="card card-highlight">
          <div className="card-header">
            <h3 style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <Sparkles size={16} className="text-accent" />
              <span>Skill Intelligence Diagnostic</span>
            </h3>
          </div>
          <div className="card-body">
            <p className="analytics-summary-text">
              Based on <strong>{skills.total_analyses}</strong> evaluated {skills.total_analyses === 1 ? "role" : "roles"}:
              {skills.frequent_matched?.length > 0 && (
                <> Your highest converting core strength is <strong>{skills.frequent_matched[0].skill}</strong>.</>
              )}
              {skills.frequent_missing?.length > 0 && (
                <> Your most frequent skill gap is <strong>{skills.frequent_missing[0].skill}</strong> (missing across target roles).</>
              )}
            </p>
          </div>
        </section>
      )}

      {/* === Strategic Key Metrics Row === */}
      <div className="analytics-stats-grid">
        {statCards.map((card) => (
          <div key={card.label} className="stat-card">
            <div className="stat-card-icon">
              <card.icon size={20} />
            </div>
            <div className="stat-card-info">
              <span className="stat-card-value font-mono">{card.value}</span>
              <span className="stat-card-label">{card.label}</span>
            </div>
          </div>
        ))}
      </div>

      {/* === Funnel & Distribution Grid === */}
      <div className="analytics-charts-grid">
        {/* Application Conversion Funnel */}
        <div className="card">
          <div className="card-header">
            <h2>Application Conversion Funnel</h2>
          </div>
          <div className="card-body">
            {hasFunnel ? (
              <div className="insights-funnel-list">
                {funnel.funnel.map((stage) => {
                  const pct = Math.round((stage.count / maxFunnel) * 100);
                  return (
                    <div key={stage.stage} className="funnel-stage-row">
                      <div className="funnel-stage-header">
                        <span className="funnel-stage-name">{stage.stage}</span>
                        <span className="funnel-stage-count font-mono">{stage.count}</span>
                      </div>
                      <div className="score-bar-track">
                        <div
                          className="score-bar-fill"
                          style={{
                            width: `${pct}%`,
                            background:
                              stage.stage === "offer" || stage.stage === "Offer"
                                ? "var(--success)"
                                : stage.stage === "interview" || stage.stage === "Interview"
                                ? "var(--purple)"
                                : "var(--accent)",
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <EmptyState icon={FileText} title="No funnel data" text="Track applications to see conversion milestones." />
            )}
          </div>
        </div>

        {/* Application Stage Distribution */}
        <div className="card">
          <div className="card-header">
            <h2>Stage Distribution</h2>
          </div>
          <div className="card-body">
            {dashboard && dashboard.total_applications > 0 ? (
              <div className="insights-distribution-list">
                {distributionItems.map((item) => {
                  const pct = Math.round((item.value / dashboard.total_applications) * 100);
                  return (
                    <div key={item.label} className="insights-dist-row">
                      <div className="insights-dist-label">
                        <span className="distribution-dot" style={{ background: item.color }} />
                        <span>{item.label}</span>
                      </div>
                      <div className="score-bar-track">
                        <div
                          className="score-bar-fill"
                          style={{ width: `${pct}%`, background: item.color }}
                        />
                      </div>
                      <span className="insights-dist-val font-mono">{item.value}</span>
                    </div>
                  );
                })}
              </div>
            ) : (
              <EmptyState icon={FileText} title="No distribution data" text="Track applications to inspect stage breakdown." />
            )}
          </div>
        </div>
      </div>

      {/* === Skills Gap Coach & Top Strengths Grid === */}
      <div className="analytics-skills-grid">
        {/* Frequently Missing Skills */}
        <div className="card">
          <div className="card-header">
            <h2 className="text-warning" style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <AlertCircle size={18} />
              <span>Skill Gap Coach (Missing in Roles)</span>
            </h2>
          </div>
          <div className="card-body">
            {hasSkills && skills.frequent_missing?.length > 0 ? (
              <div className="skill-frequency-list">
                {skills.frequent_missing.map((s) => {
                  const pct = Math.round((s.count / skills.total_analyses) * 100);
                  return (
                    <div key={s.skill} className="skill-frequency-item">
                      <div className="skill-frequency-header">
                        <span className="skill-tag skill-missing">{s.skill}</span>
                        <span className="skill-frequency-count font-mono">
                          Missing in {s.count} of {skills.total_analyses} roles ({pct}%)
                        </span>
                      </div>
                      <div className="score-bar-track">
                        <div
                          className="score-bar-fill"
                          style={{ width: `${pct}%`, background: "var(--warning)" }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <EmptyState
                icon={AlertCircle}
                title="No skill gap data"
                text="Run match analyses on target jobs to identify frequently requested missing skills."
              />
            )}
          </div>
        </div>

        {/* Top Strengths */}
        <div className="card">
          <div className="card-header">
            <h2 className="text-success" style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <CheckCircle2 size={18} />
              <span>Top Competitive Strengths</span>
            </h2>
          </div>
          <div className="card-body">
            {hasSkills && skills.frequent_matched?.length > 0 ? (
              <div className="skill-frequency-list">
                {skills.frequent_matched.map((s) => {
                  const pct = Math.round((s.count / skills.total_analyses) * 100);
                  return (
                    <div key={s.skill} className="skill-frequency-item">
                      <div className="skill-frequency-header">
                        <span className="skill-tag skill-matched">{s.skill}</span>
                        <span className="skill-frequency-count font-mono">
                          Matched in {s.count} of {skills.total_analyses} roles ({pct}%)
                        </span>
                      </div>
                      <div className="score-bar-track">
                        <div
                          className="score-bar-fill"
                          style={{ width: `${pct}%`, background: "var(--success)" }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <EmptyState
                icon={CheckCircle2}
                title="No strength data"
                text="Run match analyses to identify your highest-converting skills."
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
