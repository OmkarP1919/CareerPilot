import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import { useTranslation } from "../context/LanguageContext";
import EmptyState from "../components/EmptyState";
import { SkeletonCard } from "../components/Skeleton";
import {
  TrendingUp,
  Compass,
  ArrowRight,
  Layers,
  Timer,
  ShieldCheck,
  Award,
  AlertTriangle,
} from "lucide-react";

const RANGES = [
  { id: "4w", weeks: 4, labelKey: "insights.range4w" },
  { id: "12w", weeks: 12, labelKey: "insights.range12w" },
  { id: "6m", weeks: 26, labelKey: "insights.range6m" },
];

function addDays(date, days) {
  const d = new Date(date.getTime());
  d.setUTCDate(d.getUTCDate() + days);
  return d;
}

function toISODate(date) {
  return date.toISOString().slice(0, 10);
}

function rangeStart(weeks) {
  // Backend resolves the exact week; we only need an anchor in the past.
  return addDays(new Date(), -(weeks * 7) + 1);
}

function formatWeekLabel(iso) {
  const d = new Date(`${iso}T00:00:00Z`);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function formatDays(days) {
  if (days === null || days === undefined) return "—";
  const rounded = Math.round(days * 10) / 10;
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1);
}

function hasAnyRealData({ dashboard, funnel, skills, velocity, activity }) {
  const dash =
    dashboard &&
    (dashboard.total_applications > 0 ||
      dashboard.saved_count > 0 ||
      dashboard.applied_count > 0 ||
      dashboard.interview_count > 0 ||
      dashboard.offer_count > 0 ||
      dashboard.rejected_count > 0 ||
      dashboard.high_match_jobs > 0 ||
      dashboard.average_match_score !== null);
  const fun = funnel && funnel.total > 0;
  const ski = skills && skills.total_analyses > 0;
  const vel =
    velocity &&
    (velocity.applied_to_interview?.sample_size > 0 ||
      velocity.applied_to_offer?.sample_size > 0);
  const act =
    Array.isArray(activity?.buckets) &&
    activity.buckets.some(
      (b) => b.events > 0 || b.applications > 0 || b.interviews > 0 || b.documents > 0
    );
  return Boolean(dash || fun || ski || vel || act);
}

async function fetchOptional(promise) {
  try {
    return { data: await promise, ok: true };
  } catch {
    return { data: null, ok: false };
  }
}

export default function AnalyticsPage() {
  const { t } = useTranslation();

  const [groups, setGroups] = useState({
    dashboard: null,
    funnel: null,
    skills: null,
    velocity: null,
  });
  const [groupErrors, setGroupErrors] = useState({});
  const [loading, setLoading] = useState(true);

  const [activity, setActivity] = useState(null);
  const [activityError, setActivityError] = useState(false);
  const [activityLoading, setActivityLoading] = useState(true);
  const [range, setRange] = useState("12w");

  useEffect(() => {
    let alive = true;
    (async () => {
      const [d, f, s, v] = await Promise.all([
        fetchOptional(api.get("/analytics/dashboard")),
        fetchOptional(api.get("/analytics/application-funnel")),
        fetchOptional(api.get("/analytics/skills")),
        fetchOptional(api.getAnalyticsVelocity()),
      ]);
      if (!alive) return;
      setGroups({
        dashboard: d.data,
        funnel: f.data,
        skills: s.data,
        velocity: v.data,
      });
      setGroupErrors({
        dashboard: !d.ok,
        funnel: !f.ok,
        skills: !s.ok,
        velocity: !v.ok,
      });
      setLoading(false);
    })();
    return () => {
      alive = false;
    };
  }, []);

  const loadActivity = useCallback(async () => {
    const rangeObj = RANGES.find((r) => r.id === range) || RANGES[1];
    setActivityLoading(true);
    setActivityError(false);
    const { data, ok } = await fetchOptional(
      api.getAnalyticsActivity({ start_date: toISODate(rangeStart(rangeObj.weeks)) })
    );
    setActivity(ok ? data : null);
    setActivityError(!ok);
    setActivityLoading(false);
  }, [range]);

  useEffect(() => {
    loadActivity();
  }, [loadActivity]);

  if (loading) {
    return (
      <div className="page analytics-page">
        <div className="skeleton" style={{ height: "28px", width: "220px", marginBottom: "var(--space-4)" }} />
        <div className="grid-2">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      </div>
    );
  }

  const hasData = hasAnyRealData({ ...groups, activity });

  if (!hasData) {
    return (
      <div className="page analytics-page">
        <header className="page-header">
          <div>
            <h1>{t("insights.title", "Career Insights")}</h1>
            <p>{t("insights.subtitle", "Meaningful trends and actionable patterns across your job search.")}</p>
          </div>
        </header>

        <div className="trust-note">
          <ShieldCheck size={15} />
          <span>{t("insights.trustNote", "All insights are calculated only from your actual application activity.")}</span>
        </div>

        <EmptyState
          icon={TrendingUp}
          title={t("insights.noActivity", "No application activity yet")}
          description={t(
            "insights.noActivityDesc",
            "Apply to a job from any opportunity page to start building your pipeline."
          )}
          action={
            <Link to="/discover" className="btn btn-primary">
              <Compass size={16} />
              <span>Explore Opportunities</span>
            </Link>
          }
        />
      </div>
    );
  }

  const dashboard = groups.dashboard;
  const funnel = groups.funnel;
  const skills = groups.skills;
  const velocity = groups.velocity;

  const totalApps = dashboard?.total_applications || 0;
  const interviewCount = dashboard?.interview_count || 0;
  const offerCount = dashboard?.offer_count || 0;
  const avgScore = dashboard?.average_match_score ?? null;

  const funnelStages = Array.isArray(funnel?.funnel) ? funnel.funnel : [];
  const funnelMax = Math.max(1, ...funnelStages.map((st) => st.count));
  const funnelTotal = funnel?.total ?? 0;

  const velocityInterview = velocity?.applied_to_interview || null;
  const velocityOffer = velocity?.applied_to_offer || null;

  const buckets = Array.isArray(activity?.buckets) ? activity.buckets : [];
  const activityMax = Math.max(
    1,
    ...buckets.flatMap((b) => [b.events, b.applications, b.interviews, b.documents])
  );

  const missingSkills = Array.isArray(skills?.frequent_missing) ? skills.frequent_missing : [];
  const matchedSkills = Array.isArray(skills?.frequent_matched) ? skills.frequent_matched : [];
  const totalAnalyses = skills?.total_analyses ?? 0;

  return (
    <div className="page analytics-page">
      {/* Page Header */}
      <header className="page-header">
        <div className="page-header-row">
          <div>
            <h1>{t("insights.title", "Career Insights")}</h1>
            <p>{t("insights.subtitle", "Meaningful trends and actionable patterns across your job search.")}</p>
          </div>

          <div className="page-header-actions">
            <Link to="/discover" className="btn btn-primary">
              <span>Find More Opportunities</span>
              <ArrowRight size={14} />
            </Link>
          </div>
        </div>

        <div className="trust-note">
          <ShieldCheck size={15} />
          <span>
            {t("insights.trustNote", "All insights are calculated only from your actual application activity.")}
          </span>
        </div>
      </header>

      {/* Stats Row */}
      <section className="card insights-stats-card">
        <div className="section-label-row">
          <span className="section-eyebrow">{t("insights.stats", "Your numbers")}</span>
        </div>
        {groupErrors.dashboard ? (
          <div className="alert alert-error">Couldn't load your application numbers.</div>
        ) : (
          <div className="insights-stats-row">
            <div className="insights-stat">
              <span className="insights-stat-value font-mono">{totalApps}</span>
              <span className="insights-stat-label">{t("insights.statApplications", "Applications")}</span>
            </div>
            <div className="insights-stat">
              <span className="insights-stat-value font-mono">{interviewCount}</span>
              <span className="insights-stat-label">{t("insights.statInterviews", "Interviews")}</span>
            </div>
            <div className="insights-stat">
              <span className="insights-stat-value font-mono text-success">{offerCount}</span>
              <span className="insights-stat-label">{t("insights.statOffers", "Offers")}</span>
            </div>
            <div className="insights-stat">
              <span className="insights-stat-value font-mono">
                {avgScore !== null ? `${avgScore}%` : "—"}
              </span>
              <span className="insights-stat-label">{t("insights.statAvgMatch", "Average match")}</span>
              {avgScore === null && (
                <span className="insights-stat-note">{t("insights.noAnalyses", "No analyses yet")}</span>
              )}
            </div>
          </div>
        )}
      </section>

      <div className="grid-2">
        {/* Application Funnel */}
        <section className="card chart-card">
          <div className="card-header">
            <h3 style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <Layers size={18} className="text-accent" />
              <span>{t("insights.funnel", "Application Funnel")}</span>
            </h3>
          </div>
          {groupErrors.funnel ? (
            <div className="alert alert-error">Couldn't load the application funnel.</div>
          ) : funnelStages.length === 0 || funnelTotal === 0 ? (
            <p className="text-secondary text-sm">
              {t("insights.noActivityPeriod", "No application activity in this period.")}
            </p>
          ) : (
            <div className="card-body stack" style={{ gap: "var(--space-4)" }}>
              {funnelStages.map((st) => (
                <div className="funnel-bar-item" key={st.stage}>
                  <div className="funnel-bar-head">
                    <span>{st.stage}</span>
                    <span className="font-mono">{st.count}</span>
                  </div>
                  <div className="score-bar-track">
                    <div
                      className="score-bar-fill"
                      style={{ width: `${(st.count / funnelMax) * 100}%`, background: "var(--accent)" }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Velocity */}
        <section className="card chart-card">
          <div className="card-header">
            <h3 style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <Timer size={18} className="text-accent" />
              <span>{t("insights.velocity", "Application velocity")}</span>
            </h3>
          </div>
          <div className="card-body stack" style={{ gap: "var(--space-4)" }}>
            {groupErrors.velocity ? (
              <div className="alert alert-error">Couldn't load application velocity.</div>
            ) : (
              <>
                <p className="text-secondary text-sm">
                  {t("insights.velocitySub", "Median time between milestones, based on your status-change records.")}
                </p>
                {velocityInterview && velocityOffer ? (
                  <div className="grid-2">
                    <div className="velocity-card">
                      <span className="velocity-label">{t("insights.appliedToInterview", "Applied → Interview")}</span>
                      {velocityInterview.median_days !== null ? (
                        <>
                          <span className="velocity-value font-mono">{formatDays(velocityInterview.median_days)} <span className="velocity-unit">days</span></span>
                          <span className="velocity-sample">
                            {t("insights.sampleCount", "{count} journeys").replace("{count}", String(velocityInterview.sample_size))}
                          </span>
                        </>
                      ) : (
                        <span className="velocity-none">{t("insights.noJourneys", "No completed application journeys yet.")}</span>
                      )}
                    </div>
                    <div className="velocity-card">
                      <span className="velocity-label">{t("insights.appliedToOffer", "Applied → Offer")}</span>
                      {velocityOffer.median_days !== null ? (
                        <>
                          <span className="velocity-value font-mono">{formatDays(velocityOffer.median_days)} <span className="velocity-unit">days</span></span>
                          <span className="velocity-sample">
                            {t("insights.sampleCount", "{count} journeys").replace("{count}", String(velocityOffer.sample_size))}
                          </span>
                        </>
                      ) : (
                        <span className="velocity-none">{t("insights.noJourneys", "No completed application journeys yet.")}</span>
                      )}
                    </div>
                  </div>
                ) : (
                  <p className="text-secondary text-sm">
                    {t("insights.noJourneys", "No completed application journeys yet.")}
                  </p>
                )}
              </>
            )}
          </div>
        </section>
      </div>

      {/* Activity Over Time */}
      <section className="card chart-card">
        <div className="card-header-row activity-header">
          <div className="card-header-title">
            <h3>{t("insights.activity", "Activity over time")}</h3>
            <p className="text-secondary text-sm">
              {t("insights.activitySub", "Weekly activity across applications, events, interviews, and documents.")}
            </p>
          </div>
          <div className="tabs-pill" role="group" aria-label="Activity range">
            {RANGES.map((r) => (
              <button
                key={r.id}
                type="button"
                className={`tab-pill-item ${range === r.id ? "active" : ""}`}
                onClick={() => setRange(r.id)}
              >
                {t(r.labelKey, r.labelKey === "insights.range4w" ? "4 weeks" : r.labelKey === "insights.range12w" ? "12 weeks" : "6 months")}
              </button>
            ))}
          </div>
        </div>

        {activityError ? (
          <div className="alert alert-error">Couldn't load activity data.</div>
        ) : activityLoading ? (
          <SkeletonCard lines={4} />
        ) : buckets.length === 0 ? (
          <p className="text-secondary text-sm">
            {t("insights.noActivityPeriod", "No application activity in this period.")}
          </p>
        ) : (
          <>
            <div className="activity-legend">
              <span className="legend-item"><span className="legend-swatch event" />Events</span>
              <span className="legend-item"><span className="legend-swatch applications" />Applications</span>
              <span className="legend-item"><span className="legend-swatch interviews" />Interviews</span>
              <span className="legend-item"><span className="legend-swatch documents" />Documents</span>
            </div>
            <div className="activity-chart">
              {buckets.map((b) => {
                const total = b.events + b.applications + b.interviews + b.documents;
                return (
                  <div className="activity-week" key={b.period} title={`${b.period} · ${total} total`}>
                    <span className="activity-week-label">{formatWeekLabel(b.period)}</span>
                    <div className="activity-week-bars">
                      <div className="activity-bar-wrap">
                        <div className="activity-bar-fill events" style={{ height: `${(b.events / activityMax) * 100}%` }} />
                      </div>
                      <div className="activity-bar-wrap">
                        <div className="activity-bar-fill applications" style={{ height: `${(b.applications / activityMax) * 100}%` }} />
                      </div>
                      <div className="activity-bar-wrap">
                        <div className="activity-bar-fill interviews" style={{ height: `${(b.interviews / activityMax) * 100}%` }} />
                      </div>
                      <div className="activity-bar-wrap">
                        <div className="activity-bar-fill documents" style={{ height: `${(b.documents / activityMax) * 100}%` }} />
                      </div>
                    </div>
                    <span className="activity-week-count font-mono">{total}</span>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </section>

      <div className="grid-2">
        {/* Missing skills */}
        <section className="card chart-card">
          <div className="card-header">
            <h3 style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <AlertTriangle size={18} className="text-warning" />
              <span>{t("insights.missingSkills", "Most Common Missing Skills")}</span>
            </h3>
          </div>
          {groupErrors.skills ? (
            <div className="alert alert-error">Couldn't load skill insights.</div>
          ) : totalAnalyses === 0 ? (
            <p className="text-secondary text-sm">
              {t("insights.noSkills", "No match analyses yet. Run a match to see skill insights.")}
            </p>
          ) : (
            <div className="card-body stack" style={{ gap: "var(--space-3)" }}>
              <p className="text-secondary text-sm">
                Skills frequently required by your target jobs that aren't yet in your profile.
              </p>
              {missingSkills.length === 0 ? (
                <p className="text-success text-sm">No missing skills across your analyses.</p>
              ) : (
                <div className="missing-skills-chart-list">
                  {missingSkills.slice(0, 5).map((item) => {
                    const maxMissing = Math.max(1, ...missingSkills.map((i) => i.count));
                    return (
                      <div className="missing-skill-row" key={`${item.type}-${item.skill}`}>
                        <span className="skill-name font-medium">{item.skill}</span>
                        <div className="score-bar-track" style={{ flex: 1, margin: "0 var(--space-3)" }}>
                          <div
                            className="score-bar-fill"
                            style={{ width: `${(item.count / maxMissing) * 100}%`, background: "var(--warning)" }}
                          />
                        </div>
                        <span className="skill-count text-xs text-muted font-mono">{item.count}</span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </section>

        {/* Matched skills */}
        <section className="card chart-card">
          <div className="card-header">
            <h3 style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <Award size={18} className="text-success" />
              <span>Most Common Matched Skills</span>
            </h3>
          </div>
          {groupErrors.skills ? (
            <div className="alert alert-error">Couldn't load skill insights.</div>
          ) : totalAnalyses === 0 ? (
            <p className="text-secondary text-sm">
              {t("insights.noSkills", "No match analyses yet. Run a match to see skill insights.")}
            </p>
          ) : (
            <div className="card-body stack" style={{ gap: "var(--space-3)" }}>
              <p className="text-secondary text-sm">
                Skills from your profile that appeared most often in your match analyses.
              </p>
              {matchedSkills.length === 0 ? (
                <p className="text-secondary text-sm">No matched skills recorded yet.</p>
              ) : (
                <div className="missing-skills-chart-list">
                  {matchedSkills.slice(0, 5).map((item) => {
                    const maxMatched = Math.max(1, ...matchedSkills.map((i) => i.count));
                    return (
                      <div className="missing-skill-row" key={`${item.type}-${item.skill}`}>
                        <span className="skill-name font-medium">{item.skill}</span>
                        <div className="score-bar-track" style={{ flex: 1, margin: "0 var(--space-3)" }}>
                          <div
                            className="score-bar-fill"
                            style={{ width: `${(item.count / maxMatched) * 100}%`, background: "var(--success)" }}
                          />
                        </div>
                        <span className="skill-count text-xs text-muted font-mono">{item.count}</span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}