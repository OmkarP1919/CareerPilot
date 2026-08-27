import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import ScoreBadge from "../components/ScoreBadge";
import EmptyState from "../components/EmptyState";
import { SkeletonCard } from "../components/Skeleton";
import {
  Plus,
  Search,
  RefreshCw,
  Briefcase,
  MapPin,
  Sparkles,
  Filter,
  MoreVertical,
  Edit3,
  Trash2,
  ExternalLink,
  X,
  Building2,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
} from "lucide-react";

const EMPLOYMENT_TYPES = ["Full-time", "Part-time", "Contract", "Internship", "Freelance"];
const EXPERIENCE_LEVELS = ["Entry Level", "Mid Level", "Senior Level", "Lead", "Executive"];

const EMPTY_FORM = {
  title: "",
  company: "",
  location: "",
  employment_type: "Full-time",
  experience_level: "Entry Level",
  required_skills: "",
  description: "",
  url: "",
};

export default function JobsPage() {
  const [myJobs, setMyJobs] = useState([]);
  const [recommendedJobs, setRecommendedJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [levelFilter, setLevelFilter] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [editJob, setEditJob] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [notification, setNotification] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [discovering, setDiscovering] = useState(false);
  const [discoveryFeedback, setDiscoveryFeedback] = useState(null);
  const [showQueriesDetail, setShowQueriesDetail] = useState(false);
  const [activeMenuId, setActiveMenuId] = useState(null);

  const showNotif = (msg, type = "success") => {
    setNotification({ msg, type });
    setTimeout(() => setNotification(null), 4000);
  };

  const fetchJobs = useCallback(async () => {
    try {
      const [jobs, recs] = await Promise.all([
        api.get("/jobs/"),
        api.get("/jobs/recommended").catch(() => []),
      ]);
      setMyJobs(Array.isArray(jobs) ? jobs : []);
      setRecommendedJobs(Array.isArray(recs) ? recs : []);
    } catch {
      showNotif("Failed to load jobs.", "error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  const handlePersonalizedDiscovery = async () => {
    console.log("[DISCOVERY 1] Button clicked");
    if (discovering) {
      console.log("[DISCOVERY 1.1] Already discovering, ignored");
      return;
    }
    console.log("[DISCOVERY 2] Setting loading true");
    setDiscovering(true);
    setDiscoveryFeedback({
      status: "loading",
      title: "Finding jobs that match your profile...",
      desc: "Analyzing your career preferences, skills, and experience to query relevant opportunities.",
    });

    try {
      console.log("[DISCOVERY 3] About to call API");
      const res = await api.discoverPersonalizedJobs();
      console.log("[DISCOVERY 4] API returned", res);

      console.log("[DISCOVERY 5] Refreshing jobs");
      await fetchJobs();
      console.log("[DISCOVERY 6] Jobs refreshed");

      const hasInsufficientData = res.errors?.some(
        (e) => e.toLowerCase().includes("insufficient") || e.toLowerCase().includes("no profile")
      );

      if (hasInsufficientData) {
        setDiscoveryFeedback({
          status: "incomplete",
          title: "Complete your profile for personalized job discovery",
          desc: "Add your preferred job roles or technical skills so we can search tailored opportunities for you.",
          showProfileLink: true,
          queries: [],
        });
      } else if (res.new_jobs > 0) {
        setDiscoveryFeedback({
          status: "success",
          title: `${res.new_jobs} new ${res.new_jobs === 1 ? "opportunity" : "opportunities"} discovered for you`,
          desc: "Matches were automatically evaluated based on your skills, experience, and role preferences.",
          queries: res.queries_used || [],
          warning: res.errors?.length > 0 ? "Some external sources were temporarily unavailable, but we found new opportunities." : null,
        });
      } else if (res.existing_jobs > 0 || res.matches_created > 0) {
        setDiscoveryFeedback({
          status: "success",
          title: "Your personalized matches are up to date",
          desc: "No new external jobs were added, but we refreshed your personalized match scores and rankings.",
          queries: res.queries_used || [],
        });
      } else {
        setDiscoveryFeedback({
          status: "no_results",
          title: "No new matching opportunities right now",
          desc: "Try broadening your preferred locations or adding more technical skills to your profile.",
          queries: res.queries_used || [],
          showProfileLink: true,
        });
      }
    } catch (err) {
      console.error("[DISCOVERY ERROR]", err);
      setDiscoveryFeedback({
        status: "error",
        title: "Could not complete personalized discovery",
        desc: err.message || "An unexpected error occurred. Please try again in a moment.",
      });
    } finally {
      console.log("[DISCOVERY 7] Finally executing");
      setDiscovering(false);
      console.log("[DISCOVERY 8] Loading set to false");
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await api.post("/jobs/discover");
      await fetchJobs();
      showNotif("Aggregated job feed refreshed.");
    } catch {
      showNotif("Failed to sync new jobs.", "error");
    } finally {
      setRefreshing(false);
    }
  };

  const openAdd = () => {
    setEditJob(null);
    setForm(EMPTY_FORM);
    setShowModal(true);
  };

  const openEdit = (job) => {
    setEditJob(job);
    setForm({
      title: job.title,
      company: job.company,
      location: job.location || "",
      employment_type: job.employment_type || "Full-time",
      experience_level: job.experience_level || "Entry Level",
      required_skills: job.required_skills?.join(", ") || "",
      description: job.description || "",
      url: job.url || "",
    });
    setActiveMenuId(null);
    setShowModal(true);
  };

  const handleSave = async (e) => {
    e.preventDefault();
    if (!form.title || !form.company) return;
    setSaving(true);
    try {
      const payload = {
        ...form,
        required_skills: form.required_skills
          ? form.required_skills.split(",").map((s) => s.trim()).filter(Boolean)
          : [],
      };
      if (editJob) {
        await api.put(`/jobs/${editJob.id}`, payload);
        showNotif("Job details updated.");
      } else {
        await api.post("/jobs/", payload);
        showNotif("Job added to workspace.");
      }
      setShowModal(false);
      await fetchJobs();
    } catch {
      showNotif("Failed to save job.", "error");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (jobId) => {
    setActiveMenuId(null);
    if (!window.confirm("Remove this opportunity from your workspace?")) return;
    try {
      await api.delete(`/jobs/${jobId}`);
      showNotif("Job removed.");
      await fetchJobs();
    } catch {
      showNotif("Failed to delete.", "error");
    }
  };

  const filtered = myJobs.filter((job) => {
    const matchSearch =
      !search ||
      job.title.toLowerCase().includes(search.toLowerCase()) ||
      job.company.toLowerCase().includes(search.toLowerCase());
    const matchType = !typeFilter || job.employment_type === typeFilter;
    const matchLevel = !levelFilter || job.experience_level === levelFilter;
    return matchSearch && matchType && matchLevel;
  });

  if (loading) {
    return (
      <div className="page">
        <div className="page-header">
          <div className="skeleton skeleton-title" style={{ width: 200, height: 32 }} />
        </div>
        <div className="grid-3">
          {[...Array(6)].map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="page" onClick={() => setActiveMenuId(null)}>
      {/* === Page Header === */}
      <header className="page-header">
        <div className="page-header-row">
          <div>
            <h1>Discover Opportunities</h1>
            <p>Explore opportunities matched to your profile & career preferences</p>
          </div>
          <div className="page-header-actions">
            <button
              className="btn btn-primary btn-sm"
              onClick={handlePersonalizedDiscovery}
              disabled={discovering || refreshing}
              title="Find and match opportunities tailored to your profile"
            >
              <Sparkles size={14} className={discovering ? "spin" : ""} />
              <span>{discovering ? "Finding Jobs for You..." : "Find Jobs for Me"}</span>
            </button>
            <button
              className="btn btn-secondary btn-sm"
              onClick={handleRefresh}
              disabled={discovering || refreshing}
              title="Sync general external feed"
            >
              <RefreshCw size={14} className={refreshing ? "spin" : ""} />
              <span>{refreshing ? "Syncing..." : "Sync Feed"}</span>
            </button>
            <button className="btn btn-outline btn-sm" onClick={openAdd}>
              <Plus size={14} />
              <span>Add Custom Job</span>
            </button>
          </div>
        </div>
      </header>

      {/* === Personalized Discovery Feedback Banner === */}
      {discoveryFeedback && (
        <div
          className={`personalized-discovery-banner banner-${discoveryFeedback.status}`}
          role="status"
        >
          <div className="discovery-banner-header">
            <div className="discovery-banner-content">
              <div
                className={`discovery-banner-icon ${
                  discoveryFeedback.status === "incomplete"
                    ? "icon-warning"
                    : discoveryFeedback.status === "error"
                    ? "icon-error"
                    : ""
                }`}
              >
                {discoveryFeedback.status === "loading" ? (
                  <Sparkles size={16} className="spin" />
                ) : discoveryFeedback.status === "incomplete" ? (
                  <AlertTriangle size={16} />
                ) : discoveryFeedback.status === "error" ? (
                  <AlertTriangle size={16} />
                ) : (
                  <CheckCircle2 size={16} />
                )}
              </div>

              <div>
                <h3 className="discovery-banner-title">{discoveryFeedback.title}</h3>
                <p className="discovery-banner-desc">{discoveryFeedback.desc}</p>

                {discoveryFeedback.warning && (
                  <p className="discovery-banner-desc" style={{ marginTop: 4, color: "var(--warning-dark, #b45309)" }}>
                    {discoveryFeedback.warning}
                  </p>
                )}

                {discoveryFeedback.showProfileLink && (
                  <div style={{ marginTop: 8 }}>
                    <Link to="/profile" className="btn btn-primary btn-xs">
                      <span>Complete Profile</span>
                      <ArrowRight size={12} />
                    </Link>
                  </div>
                )}

                {discoveryFeedback.queries?.length > 0 && (
                  <div>
                    <button
                      type="button"
                      className="discovery-queries-toggle"
                      onClick={() => setShowQueriesDetail(!showQueriesDetail)}
                    >
                      <span>{showQueriesDetail ? "Hide search details" : "See how we searched"}</span>
                      {showQueriesDetail ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                    </button>

                    {showQueriesDetail && (
                      <div className="discovery-queries-wrap">
                        <span className="discovery-queries-label">Roles searched based on your profile:</span>
                        {discoveryFeedback.queries.map((q) => (
                          <span key={q} className="discovery-query-chip">{q}</span>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>

            {discoveryFeedback.status !== "loading" && (
              <button
                type="button"
                className="discovery-banner-dismiss"
                onClick={() => setDiscoveryFeedback(null)}
                aria-label="Dismiss banner"
              >
                <X size={16} />
              </button>
            )}
          </div>
        </div>
      )}

      {notification && (
        <div className={`alert alert-${notification.type}`} role="alert">
          {notification.msg}
        </div>
      )}

      {/* === Recommended Opportunities Carousel/Grid === */}
      {recommendedJobs.length > 0 && !search && !typeFilter && !levelFilter && (
        <section className="discover-recommended-section">
          <div className="section-header">
            <h2>
              <Sparkles size={18} className="text-accent" />
              <span>Recommended for You</span>
            </h2>
            <span className="section-count">{recommendedJobs.length} Matches</span>
          </div>

          <div className="recommended-jobs-grid">
            {recommendedJobs.map((r) => {
              const job = r.job || r;
              return (
                <div key={job.id} className="recommended-job-card">
                  <div className="recommended-card-top">
                    <div className="recommended-role-wrap">
                      <span className="recommended-company-eyebrow">
                        <Building2 size={13} />
                        <span>{job.company}</span>
                      </span>
                      <Link to={`/discover/${job.id}`} className="recommended-role-title">
                        {job.title}
                      </Link>
                    </div>
                    <ScoreBadge score={r.score} />
                  </div>

                  <div className="recommended-meta-row">
                    <span className="recommended-meta-item">
                      <MapPin size={13} />
                      <span>{job.location || "Remote Friendly"}</span>
                    </span>
                    {job.employment_type && (
                      <span className="recommended-meta-item">
                        • {job.employment_type}
                      </span>
                    )}
                  </div>

                  {r.matched_skills?.length > 0 && (
                    <div className="recommended-skills-preview">
                      <span className="recommended-skills-label">Matched:</span>
                      <div className="skills-tags-wrap">
                        {r.matched_skills.slice(0, 4).map((s) => (
                          <span key={s} className="skill-tag skill-matched">{s}</span>
                        ))}
                        {r.matched_skills.length > 4 && (
                          <span className="skill-tag skill-more">+{r.matched_skills.length - 4}</span>
                        )}
                      </div>
                    </div>
                  )}

                  <div className="recommended-card-footer">
                    <Link to={`/discover/${job.id}`} className="btn btn-outline btn-sm btn-block">
                      View Opportunity
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* === All Opportunities Feed with Scannable Cards === */}
      <section className="discover-all-section">
        <div className="discover-toolbar">
          <div className="discover-search-wrap">
            <Search size={16} className="discover-search-icon" />
            <input
              className="form-input discover-search-input"
              placeholder="Search by job title, company, or keyword..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          <div className="discover-filters-wrap">
            <div className="filter-select-wrap">
              <Filter size={14} className="filter-icon" />
              <select
                className="form-select filter-select"
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                aria-label="Filter by employment type"
              >
                <option value="">All Employment Types</option>
                {EMPLOYMENT_TYPES.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>

            <div className="filter-select-wrap">
              <select
                className="form-select filter-select"
                value={levelFilter}
                onChange={(e) => setLevelFilter(e.target.value)}
                aria-label="Filter by experience level"
              >
                <option value="">All Experience Levels</option>
                {EXPERIENCE_LEVELS.map((l) => (
                  <option key={l} value={l}>{l}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {filtered.length > 0 ? (
          <div className="discover-jobs-list">
            {filtered.map((job) => (
              <div key={job.id} className="discover-job-row">
                <div className="discover-job-main">
                  <div className="discover-job-header">
                    <Link to={`/discover/${job.id}`} className="discover-job-title">
                      {job.title}
                    </Link>
                    <span className="discover-job-company">{job.company}</span>
                  </div>

                  <div className="discover-job-meta">
                    {job.location && (
                      <span className="job-meta-chip">
                        <MapPin size={13} />
                        <span>{job.location}</span>
                      </span>
                    )}
                    {job.employment_type && (
                      <span className="job-meta-chip">{job.employment_type}</span>
                    )}
                    {job.experience_level && (
                      <span className="job-meta-chip">{job.experience_level}</span>
                    )}
                  </div>

                  {job.required_skills?.length > 0 && (
                    <div className="discover-job-skills">
                      {job.required_skills.slice(0, 5).map((s) => (
                        <span key={s} className="skill-tag">{s}</span>
                      ))}
                      {job.required_skills.length > 5 && (
                        <span className="skill-tag skill-more">+{job.required_skills.length - 5}</span>
                      )}
                    </div>
                  )}
                </div>

                <div className="discover-job-actions">
                  <Link to={`/discover/${job.id}`} className="btn btn-outline btn-sm">
                    View Opportunity
                  </Link>

                  <div className="job-menu-wrap" onClick={(e) => e.stopPropagation()}>
                    <button
                      className="btn btn-ghost btn-icon btn-sm"
                      onClick={() => setActiveMenuId(activeMenuId === job.id ? null : job.id)}
                      aria-label="More options"
                      type="button"
                    >
                      <MoreVertical size={16} />
                    </button>

                    {activeMenuId === job.id && (
                      <div className="job-context-menu">
                        <Link to={`/discover/${job.id}/match`} className="job-menu-item">
                          <Sparkles size={14} />
                          <span>Match Analysis</span>
                        </Link>
                        {job.url && (
                          <a
                            href={job.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="job-menu-item"
                          >
                            <ExternalLink size={14} />
                            <span>External Apply</span>
                          </a>
                        )}
                        <button
                          className="job-menu-item"
                          onClick={() => openEdit(job)}
                          type="button"
                        >
                          <Edit3 size={14} />
                          <span>Edit Details</span>
                        </button>
                        <button
                          className="job-menu-item danger"
                          onClick={() => handleDelete(job.id)}
                          type="button"
                        >
                          <Trash2 size={14} />
                          <span>Delete</span>
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            icon={Briefcase}
            title="No opportunities found"
            text={
              search || typeFilter || levelFilter
                ? "Try adjusting your search criteria or filters."
                : "Add your first custom target role or sync the job feed."
            }
            action={
              <button className="btn btn-primary btn-sm" onClick={openAdd}>
                <Plus size={14} /> Add Job
              </button>
            }
          />
        )}
      </section>

      {/* === Add / Edit Custom Job Modal === */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{editJob ? "Edit Job Opportunity" : "Add Custom Job Opportunity"}</h3>
              <button
                className="btn btn-ghost btn-icon btn-sm"
                onClick={() => setShowModal(false)}
                aria-label="Close"
              >
                <X size={18} />
              </button>
            </div>
            <form onSubmit={handleSave} className="modal-body">
              <div className="form-group">
                <label className="form-label" htmlFor="form-job-title">Job Title *</label>
                <input
                  id="form-job-title"
                  className="form-input"
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                  placeholder="e.g. Senior Frontend Engineer"
                  required
                />
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label className="form-label" htmlFor="form-company">Company *</label>
                  <input
                    id="form-company"
                    className="form-input"
                    value={form.company}
                    onChange={(e) => setForm({ ...form, company: e.target.value })}
                    placeholder="e.g. Acme Corp"
                    required
                  />
                </div>
                <div className="form-group">
                  <label className="form-label" htmlFor="form-location">Location</label>
                  <input
                    id="form-location"
                    className="form-input"
                    value={form.location}
                    onChange={(e) => setForm({ ...form, location: e.target.value })}
                    placeholder="e.g. San Francisco, CA (or Remote)"
                  />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">Employment Type</label>
                  <select
                    className="form-select"
                    value={form.employment_type}
                    onChange={(e) => setForm({ ...form, employment_type: e.target.value })}
                  >
                    {EMPLOYMENT_TYPES.map((t) => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">Experience Level</label>
                  <select
                    className="form-select"
                    value={form.experience_level}
                    onChange={(e) => setForm({ ...form, experience_level: e.target.value })}
                  >
                    {EXPERIENCE_LEVELS.map((l) => (
                      <option key={l} value={l}>{l}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="form-skills">Required Skills</label>
                <input
                  id="form-skills"
                  className="form-input"
                  value={form.required_skills}
                  onChange={(e) => setForm({ ...form, required_skills: e.target.value })}
                  placeholder="React, TypeScript, Node.js, GraphQL (comma separated)"
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="form-desc">Role Description</label>
                <textarea
                  id="form-desc"
                  className="form-textarea"
                  rows={4}
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  placeholder="Paste job description or key responsibilities..."
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="form-url">Job Listing / Application URL</label>
                <input
                  id="form-url"
                  className="form-input"
                  type="url"
                  value={form.url}
                  onChange={(e) => setForm({ ...form, url: e.target.value })}
                  placeholder="https://jobs.company.com/..."
                />
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-outline"
                  onClick={() => setShowModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={saving}
                >
                  {saving ? (
                    <>
                      <span className="spinner-inline" />
                      <span>Saving...</span>
                    </>
                  ) : editJob ? (
                    "Update Job"
                  ) : (
                    "Add Opportunity"
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
