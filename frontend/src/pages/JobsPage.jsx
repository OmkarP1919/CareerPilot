import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import { useTranslation } from "../context/LanguageContext";
import ScoreBadge from "../components/ScoreBadge";
import EmptyState from "../components/EmptyState";
import { SkeletonCard } from "../components/Skeleton";
import Modal from "../components/Modal";
import {
  Search,
  Compass,
  Sparkles,
  Plus,
  Bookmark,
  BookmarkCheck,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  X,
  ChevronDown,
  ChevronUp,
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
  const { t } = useTranslation();
  const [myJobs, setMyJobs] = useState([]);
  const [recommendedJobs, setRecommendedJobs] = useState([]);
  const [savedJobIds, setSavedJobIds] = useState(new Set());
  const [loading, setLoading] = useState(true);

  // Search & Filters
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [levelFilter, setLevelFilter] = useState("");
  const [activeTab, setActiveTab] = useState("recommended"); // "recommended" | "all"

  // Discovery state
  const [discovering, setDiscovering] = useState(false);
  const [discoveryResult, setDiscoveryResult] = useState(null);
  const [showSearchTerms, setShowSearchTerms] = useState(false);

  // Custom Job Modal
  const [showAddModal, setShowAddModal] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [savingJob, setSavingJob] = useState(false);
  const [notification, setNotification] = useState(null);

  const notify = (msg, type = "success") => {
    setNotification({ msg, type });
    setTimeout(() => setNotification(null), 3500);
  };

  const fetchJobs = useCallback(async () => {
    try {
      const [allJobsRes, recsRes, appsRes] = await Promise.all([
        api.get("/jobs/"),
        api.get("/jobs/recommended").catch(() => []),
        api.get("/applications/").catch(() => []),
      ]);

      const jobsList = Array.isArray(allJobsRes) ? allJobsRes : [];
      const rawRecs = Array.isArray(recsRes) ? recsRes : [];
      const appsList = Array.isArray(appsRes) ? appsRes : [];

      const normalizedRecs = rawRecs.map((item) => {
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

      setMyJobs(jobsList);
      setRecommendedJobs(normalizedRecs);
      setSavedJobIds(new Set(appsList.map((a) => a.job_id)));
    } catch (err) {
      notify("Could not load opportunities. Please try again.", "error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  const handlePersonalizedDiscovery = async () => {
    if (discovering) return;
    setDiscovering(true);
    setDiscoveryResult(null);

    try {
      const res = await api.discoverPersonalizedJobs();
      const count = res?.added_count ?? 0;
      const queries = res?.queries_used || [];

      setDiscoveryResult({
        count,
        queries,
        message: count > 0 ? `${count} new opportunities found` : "Your recommendations are up to date.",
      });

      await fetchJobs();
      setActiveTab("recommended");
    } catch (err) {
      notify("We couldn't fetch new recommendations right now. Please try again.", "error");
    } finally {
      setDiscovering(false);
    }
  };

  const handleToggleSave = async (job) => {
    const isSaved = savedJobIds.has(job.id);
    try {
      if (isSaved) {
        // Find application ID and remove
        const apps = await api.get("/applications/");
        const app = Array.isArray(apps) ? apps.find((a) => a.job_id === job.id) : null;
        if (app) {
          await api.delete(`/applications/${app.id}`);
          setSavedJobIds((prev) => {
            const next = new Set(prev);
            next.delete(job.id);
            return next;
          });
          notify("Removed from saved applications.");
        }
      } else {
        await api.post("/applications/", { job_id: job.id, status: "Saved" });
        setSavedJobIds((prev) => new Set([...prev, job.id]));
        notify("Job saved to your applications pipeline.");
      }
    } catch (err) {
      notify("Failed to update application status.", "error");
    }
  };

  const handleCreateCustomJob = async (e) => {
    e.preventDefault();
    if (!form.title.trim() || !form.company.trim()) {
      notify("Please provide both job title and company.", "error");
      return;
    }

    setSavingJob(true);
    try {
      const skillsArray = form.required_skills
        ? form.required_skills.split(",").map((s) => s.trim()).filter(Boolean)
        : [];

      await api.post("/jobs/", {
        ...form,
        required_skills: skillsArray,
      });

      notify("Custom opportunity added successfully.");
      setShowAddModal(false);
      setForm(EMPTY_FORM);
      await fetchJobs();
    } catch (err) {
      notify("Failed to create custom opportunity.", "error");
    } finally {
      setSavingJob(false);
    }
  };

  // Filter list
  const currentList = activeTab === "recommended" ? recommendedJobs : myJobs;

  const filteredJobs = currentList.filter((job) => {
    const matchSearch =
      !search ||
      job.title?.toLowerCase().includes(search.toLowerCase()) ||
      job.company?.toLowerCase().includes(search.toLowerCase()) ||
      (Array.isArray(job.required_skills) &&
        job.required_skills.some((s) => s.toLowerCase().includes(search.toLowerCase())));

    const matchType = !typeFilter || job.employment_type === typeFilter;
    const matchLevel = !levelFilter || job.experience_level === levelFilter;

    return matchSearch && matchType && matchLevel;
  });

  return (
    <div className="page jobs-page">
      {/* Toast notification */}
      {notification && (
        <div className={`toast toast-${notification.type}`} role="status">
          {notification.msg}
        </div>
      )}

      {/* Header */}
      <header className="page-header">
        <div className="page-header-row">
          <div>
            <h1>{t("jobs.title", "Find Jobs")}</h1>
            <p>{t("jobs.subtitle", "Discover opportunities that fit your skills and career goals.")}</p>
          </div>

          <div className="page-header-actions">
            <button
              className="btn btn-secondary"
              onClick={() => setShowAddModal(true)}
              type="button"
            >
              <Plus size={16} />
              <span>Add Target Role</span>
            </button>

            <button
              className="btn btn-primary"
              onClick={handlePersonalizedDiscovery}
              disabled={discovering}
              type="button"
            >
              {discovering ? (
                <>
                  <span className="spinner-inline" />
                  <span>Finding opportunities...</span>
                </>
              ) : (
                <>
                  <Compass size={16} />
                  <span>{t("action.findJobsForMe", "Find Jobs for Me")}</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Discovery feedback banner */}
        {discoveryResult && (
          <div className="discovery-feedback-banner" role="status">
            <div className="feedback-content">
              <Sparkles size={16} className="text-accent" />
              <span className="feedback-text">{discoveryResult.message}</span>
            </div>
            {discoveryResult.queries && discoveryResult.queries.length > 0 && (
              <button
                type="button"
                className="feedback-toggle-btn"
                onClick={() => setShowSearchTerms((p) => !p)}
              >
                <span>{t("jobs.seeHowSearched", "See how we searched")}</span>
                {showSearchTerms ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </button>
            )}
          </div>
        )}

        {showSearchTerms && discoveryResult?.queries && (
          <div className="discovery-queries-drawer">
            <span className="queries-label">Target search profiles queried:</span>
            <div className="queries-chips">
              {discoveryResult.queries.map((q, i) => (
                <span key={i} className="query-chip">
                  {q}
                </span>
              ))}
            </div>
          </div>
        )}
      </header>

      {/* Workspace Controls: Tabs, Search & Compact Filters */}
      <section className="jobs-workspace-controls">
        <div className="jobs-controls-top">
          {/* Tabs */}
          <div className="tabs-pill" role="tablist">
            <button
              type="button"
              className={`tab-pill-item ${activeTab === "recommended" ? "active" : ""}`}
              onClick={() => setActiveTab("recommended")}
              role="tab"
              aria-selected={activeTab === "recommended"}
            >
              <span>{t("jobs.recommendedTab", "Recommended for You")}</span>
              <span className="tab-pill-count">{recommendedJobs.length}</span>
            </button>
            <button
              type="button"
              className={`tab-pill-item ${activeTab === "all" ? "active" : ""}`}
              onClick={() => setActiveTab("all")}
              role="tab"
              aria-selected={activeTab === "all"}
            >
              <span>{t("jobs.allTab", "All Opportunities")}</span>
              <span className="tab-pill-count">{myJobs.length}</span>
            </button>
          </div>

          {/* Search bar */}
          <div className="jobs-search-wrap">
            <Search size={16} className="search-icon" />
            <input
              type="text"
              className="jobs-search-input"
              placeholder={t("jobs.searchPlaceholder", "Search by title, skill, or company...")}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            {search && (
              <button
                type="button"
                className="search-clear-btn"
                onClick={() => setSearch("")}
                aria-label="Clear search"
              >
                <X size={14} />
              </button>
            )}
          </div>
        </div>

        {/* Compact Filters row */}
        <div className="jobs-filters-row">
          <div className="filter-group">
            <select
              className="filter-select"
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              aria-label="Filter by employment type"
            >
              <option value="">{t("jobs.allTypes", "All Types")}</option>
              {EMPLOYMENT_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          <div className="filter-group">
            <select
              className="filter-select"
              value={levelFilter}
              onChange={(e) => setLevelFilter(e.target.value)}
              aria-label="Filter by experience level"
            >
              <option value="">{t("jobs.allLevels", "All Levels")}</option>
              {EXPERIENCE_LEVELS.map((l) => (
                <option key={l} value={l}>
                  {l}
                </option>
              ))}
            </select>
          </div>

          {(search || typeFilter || levelFilter) && (
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => {
                setSearch("");
                setTypeFilter("");
                setLevelFilter("");
              }}
            >
              <span>Reset filters</span>
            </button>
          )}
        </div>
      </section>

      {/* Job Cards Grid / List */}
      {loading ? (
        <div className="stack" style={{ gap: "var(--space-4)" }}>
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : filteredJobs.length === 0 ? (
        <EmptyState
          icon={Compass}
          title={t("jobs.noJobsFound", "No opportunities found")}
          description={
            search || typeFilter || levelFilter
              ? "Try adjusting your search criteria or reset filters."
              : t("jobs.noJobsDesc", "Click 'Find Jobs for Me' to discover personalized matches.")
          }
          action={
            <button
              className="btn btn-primary"
              onClick={handlePersonalizedDiscovery}
              disabled={discovering}
              type="button"
            >
              <Compass size={16} />
              <span>{t("action.findJobsForMe", "Find Jobs for Me")}</span>
            </button>
          }
        />
      ) : (
        <div className="jobs-list-stack">
          {filteredJobs.map((job) => {
            const isSaved = savedJobIds.has(job.id);
            const score = job.match_score || 0;
            const skills = Array.isArray(job.required_skills) ? job.required_skills : [];

            return (
              <div key={job.id} className="card job-card-primary">
                <div className="job-card-main-content">
                  <div className="job-card-header">
                    <div className="job-card-title-wrap">
                      <h2 className="job-card-title">
                        <Link to={`/discover/${job.id}`}>{job.title}</Link>
                      </h2>
                      <div className="job-card-meta-line">
                        <span className="company-name">{job.company}</span>
                        {job.location && (
                          <>
                            <span className="meta-sep">•</span>
                            <span className="location-name">{job.location}</span>
                          </>
                        )}
                        {job.employment_type && (
                          <>
                            <span className="meta-sep">•</span>
                            <span>{job.employment_type}</span>
                          </>
                        )}
                        {job.experience_level && (
                          <>
                            <span className="meta-sep">•</span>
                            <span>{job.experience_level}</span>
                          </>
                        )}
                      </div>
                    </div>

                    <div className="job-card-score-col">
                      <ScoreBadge score={score} />
                    </div>
                  </div>

                  {/* Skills tags */}
                  {skills.length > 0 && (
                    <div className="job-card-skills-row">
                      {skills.slice(0, 5).map((sk) => (
                        <span key={sk} className="skill-chip match">
                          {sk}
                        </span>
                      ))}
                      {skills.length > 5 && (
                        <span className="skill-chip-more">+{skills.length - 5} more</span>
                      )}
                    </div>
                  )}

                  {/* Clean match indicators */}
                  <div className="job-card-fit-summary">
                    {score >= 70 ? (
                      <span className="fit-point positive">
                        <CheckCircle2 size={14} className="text-success" />
                        <span>High skill & role alignment with your profile</span>
                      </span>
                    ) : (
                      <span className="fit-point neutral">
                        <AlertTriangle size={14} className="text-warning" />
                        <span>Some skills may need strengthening</span>
                      </span>
                    )}
                  </div>
                </div>

                <div className="job-card-action-bar">
                  <span className="posted-date text-xs text-muted">
                    {job.created_at ? new Date(job.created_at).toLocaleDateString() : "Recently active"}
                  </span>

                  <div className="job-card-buttons">
                    <button
                      type="button"
                      className={`btn btn-sm ${isSaved ? "btn-secondary" : "btn-ghost"}`}
                      onClick={() => handleToggleSave(job)}
                      title={isSaved ? "Saved in applications" : "Save to applications"}
                      aria-label={isSaved ? "Saved" : "Save"}
                    >
                      {isSaved ? (
                        <>
                          <BookmarkCheck size={16} className="text-accent" />
                          <span>Saved</span>
                        </>
                      ) : (
                        <>
                          <Bookmark size={16} />
                          <span>Save</span>
                        </>
                      )}
                    </button>

                    <Link to={`/discover/${job.id}`} className="btn btn-primary btn-sm">
                      <span>{t("action.viewOpportunity", "View Opportunity")}</span>
                      <ArrowRight size={14} />
                    </Link>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Add Target Role Modal */}
      {showAddModal && (
        <Modal
          isOpen={showAddModal}
          onClose={() => setShowAddModal(false)}
          title="Add Target Role"
        >
          <form onSubmit={handleCreateCustomJob} className="stack" style={{ gap: "var(--space-4)" }}>
            <div className="form-group">
              <label className="form-label" htmlFor="custom-title">
                Job Title *
              </label>
              <input
                id="custom-title"
                type="text"
                className="form-input"
                placeholder="e.g. Backend Developer"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="custom-company">
                Company *
              </label>
              <input
                id="custom-company"
                type="text"
                className="form-input"
                placeholder="e.g. Acme Corp"
                value={form.company}
                onChange={(e) => setForm({ ...form, company: e.target.value })}
                required
              />
            </div>

            <div className="grid-2">
              <div className="form-group">
                <label className="form-label" htmlFor="custom-location">
                  Location
                </label>
                <input
                  id="custom-location"
                  type="text"
                  className="form-input"
                  placeholder="e.g. Remote or Pune"
                  value={form.location}
                  onChange={(e) => setForm({ ...form, location: e.target.value })}
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="custom-type">
                  Job Type
                </label>
                <select
                  id="custom-type"
                  className="form-select"
                  value={form.employment_type}
                  onChange={(e) => setForm({ ...form, employment_type: e.target.value })}
                >
                  {EMPLOYMENT_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="custom-skills">
                Required Skills (comma separated)
              </label>
              <input
                id="custom-skills"
                type="text"
                className="form-input"
                placeholder="e.g. Python, FastAPI, PostgreSQL"
                value={form.required_skills}
                onChange={(e) => setForm({ ...form, required_skills: e.target.value })}
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="custom-desc">
                Role Description
              </label>
              <textarea
                id="custom-desc"
                className="form-textarea"
                rows={4}
                placeholder="Paste responsibilities and requirements..."
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
            </div>

            <div className="modal-footer" style={{ marginTop: "var(--space-2)" }}>
              <button
                className="btn btn-ghost"
                type="button"
                onClick={() => setShowAddModal(false)}
              >
                Cancel
              </button>
              <button
                className="btn btn-primary"
                type="submit"
                disabled={savingJob}
              >
                {savingJob ? "Saving..." : "Add Role"}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
