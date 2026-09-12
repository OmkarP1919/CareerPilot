import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import { useTranslation } from "../context/LanguageContext";
import ScoreBadge from "../components/ScoreBadge";
import EmptyState from "../components/EmptyState";
import { DiscoverCard, WORK_MODES, POSTED_OPTIONS } from "../components/DiscoverPanel";
import { SkeletonCard } from "../components/Skeleton";
import Modal from "../components/Modal";
import { useJobSearch } from "../hooks/useJobSearch";
import {
  Search,
  Compass,
  Sparkles,
  Bookmark,
  BookmarkCheck,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  X,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  MoreHorizontal,
  SlidersHorizontal,
  Play,
  Trash2,
  ListChecks,
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

  // Search input and view state machine: "initial" | "searching" | "external" | "error"
  const [search, setSearch] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [view, setView] = useState("initial");

  // Filters (internal and discovery)
  const [typeFilter, setTypeFilter] = useState("");
  const [levelFilter, setLevelFilter] = useState("");

  // Hook for discovery / external search & saved searches
  const {
    discoverFilters,
    setDiscoverFilters,
    availableSources,
    discoverLoading,
    discoverReport,
    discoverError,
    savedSearches,
    saveName,
    setSaveName,
    showSaveInput,
    setShowSaveInput,
    hasActiveDiscoverFilters,
    handleExternalSearch,
    toggleSource,
    handleSaveSearch,
    handleRunSaved,
    handleDeleteSaved,
    resetDiscoverFilters,
  } = useJobSearch();

  // Progressive disclosure panels
  const [filterOpen, setFilterOpen] = useState(false);
  const [moreMenuOpen, setMoreMenuOpen] = useState(false);
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);
  const [showSavedSearches, setShowSavedSearches] = useState(false);

  // Discovery feedback state
  const [discovering, setDiscovering] = useState(false);
  const [discoveryResult, setDiscoveryResult] = useState(null);
  const [showSearchTerms, setShowSearchTerms] = useState(false);

  // Custom Job Modal
  const [showAddModal, setShowAddModal] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [savingJob, setSavingJob] = useState(false);
  const [notification, setNotification] = useState(null);

  const filterPanelRef = useRef(null);
  const moreMenuRef = useRef(null);
  const savedSearchesSectionRef = useRef(null);

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
    } catch {
      notify("Could not load opportunities. Please try again.", "error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  // Click outside to close dropdowns / Escape key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape") {
        setFilterOpen(false);
        setMoreMenuOpen(false);
      }
    };
    const handleClickOutside = (e) => {
      if (moreMenuRef.current && !moreMenuRef.current.contains(e.target)) {
        setMoreMenuOpen(false);
      }
      if (
        filterOpen &&
        window.innerWidth > 640 &&
        filterPanelRef.current &&
        !filterPanelRef.current.contains(e.target) &&
        !e.target.closest(".jobs-filter-trigger")
      ) {
        setFilterOpen(false);
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("mousedown", handleClickOutside);

    if (filterOpen && window.innerWidth <= 640) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("mousedown", handleClickOutside);
      document.body.style.overflow = "";
    };
  }, [filterOpen]);

  const hasSourceErrors = (errors) =>
    Array.isArray(errors) &&
    errors.some((e) => typeof e === "string" && /unavailable|source/i.test(e));

  const isIncompleteProfile = (errors) =>
    Array.isArray(errors) &&
    errors.some((e) => typeof e === "string" && /complete your profile|career profile/i.test(e));

  const normalizeDiscoveryResult = (res) => {
    if (!res || typeof res !== "object" || Array.isArray(res)) {
      return {
        type: "error",
        message: "We couldn't find jobs right now.",
        queries: [],
        retryable: true,
        refresh: false,
      };
    }

    const newJobs = Number.isFinite(res.new_jobs) ? res.new_jobs : 0;
    const existingJobs = Number.isFinite(res.existing_jobs) ? res.existing_jobs : 0;
    const queries = Array.isArray(res.queries_used) ? res.queries_used : [];
    const errors = Array.isArray(res.errors) ? res.errors : [];
    const partial = hasSourceErrors(errors);

    if (isIncompleteProfile(errors)) {
      return {
        type: "incomplete",
        message: "Complete your profile for personalized job discovery.",
        queries: [],
        retryable: false,
        refresh: false,
      };
    }

    const hint = partial ? "Some job sources were temporarily unavailable." : null;

    if (newJobs > 0) {
      return {
        type: "success",
        message: `${newJobs} new ${newJobs === 1 ? "opportunity" : "opportunities"} found for you.`,
        hint,
        queries,
        retryable: false,
        refresh: true,
      };
    }

    if (existingJobs > 0) {
      return {
        type: "success",
        message: "Your personalized matches are up to date.",
        hint,
        queries,
        retryable: false,
        refresh: true,
      };
    }

    if (errors.length > 0) {
      return {
        type: "error",
        message: "We couldn't find jobs right now.",
        queries,
        retryable: true,
        refresh: false,
      };
    }

    return {
      type: "empty",
      message: "No new matching opportunities right now.",
      queries,
      retryable: true,
      refresh: false,
    };
  };

  const mapDiscoveryError = (err) => {
    const kind = err?.kind;
    if (kind === "timeout") {
      return {
        type: "error",
        message: "Job discovery is taking longer than expected. Please try again.",
        queries: [],
        retryable: true,
      };
    }
    if (kind === "auth") {
      return {
        type: "error",
        message: "Your session has expired. Please sign in again.",
        queries: [],
        retryable: false,
      };
    }
    if (kind === "network") {
      return {
        type: "error",
        message: "We couldn't reach the server. Please try again.",
        queries: [],
        retryable: true,
      };
    }
    return {
      type: "error",
      message: "We couldn't find jobs right now.",
      queries: [],
      retryable: true,
    };
  };

  const handlePersonalizedDiscovery = async () => {
    if (discovering) return;
    setDiscovering(true);
    setDiscoveryResult(null);
    setShowSearchTerms(false);

    try {
      const res = await api.discoverPersonalizedJobs();
      const result = normalizeDiscoveryResult(res);
      setDiscoveryResult(result);

      if (result.refresh) {
        await fetchJobs();
        setView("initial");
      }
    } catch (err) {
      setDiscoveryResult(mapDiscoveryError(err));
    } finally {
      setDiscovering(false);
    }
  };

  // Search submission -> external discovery
  const triggerExternalSearch = async (queryToSearch) => {
    const q = queryToSearch !== undefined ? queryToSearch : search;
    const trimmed = q.trim();
    if (!trimmed && !hasActiveDiscoverFilters) {
      // If blank search and no discover filters, return to initial
      setView("initial");
      setSubmittedQuery("");
      return;
    }

    setSubmittedQuery(trimmed);
    setView("searching");
    try {
      const res = await handleExternalSearch(trimmed);
      if (res) {
        setView("external");
      } else {
        setView("external");
      }
    } catch {
      setView("error");
    }
  };

  const handleSearchSubmit = (e) => {
    e?.preventDefault();
    triggerExternalSearch(search);
  };

  const handleClearSearch = () => {
    setSearch("");
    setSubmittedQuery("");
    setView("initial");
  };

  const handleBackToRecommended = () => {
    setView("initial");
    setSearch("");
    setSubmittedQuery("");
    resetDiscoverFilters();
  };

  const handleToggleSave = async (job) => {
    const isSaved = savedJobIds.has(job.id);
    try {
      if (isSaved) {
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
    } catch {
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
    } catch {
      notify("Failed to create custom opportunity.", "error");
    } finally {
      setSavingJob(false);
    }
  };

  // Internal jobs filtering (when in initial view, responsive client-side filtering while typing)
  const currentInitialList = useMemo(() => {
    return recommendedJobs.length > 0 ? recommendedJobs : myJobs;
  }, [recommendedJobs, myJobs]);

  const filteredInternalJobs = useMemo(() => {
    return currentInitialList.filter((job) => {
      const q = search.toLowerCase();
      const matchSearch =
        !search ||
        job.title?.toLowerCase().includes(q) ||
        job.company?.toLowerCase().includes(q) ||
        (Array.isArray(job.required_skills) &&
          job.required_skills.some((s) => s.toLowerCase().includes(q)));

      const matchType = !typeFilter || job.employment_type === typeFilter;
      const matchLevel = !levelFilter || job.experience_level === levelFilter;

      return matchSearch && matchType && matchLevel;
    });
  }, [currentInitialList, search, typeFilter, levelFilter]);

  // Active filter count for badge
  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (view === "initial") {
      if (typeFilter) count++;
      if (levelFilter) count++;
    }
    if (discoverFilters.location) count++;
    if (discoverFilters.remote) count++;
    if (discoverFilters.posted) count++;
    if (discoverFilters.salary_min) count++;
    if (discoverFilters.salary_max) count++;
    if (discoverFilters.sources.length > 0) count++;
    return count;
  }, [view, typeFilter, levelFilter, discoverFilters]);

  const externalResults = useMemo(() => {
    return Array.isArray(discoverReport?.results) ? discoverReport.results : [];
  }, [discoverReport]);

  const duplicateCount = discoverReport?.duplicate_count || 0;

  const handleOpenSavedSearchesFromMenu = () => {
    setMoreMenuOpen(false);
    setFilterOpen(true);
    setShowSavedSearches(true);
    setTimeout(() => {
      savedSearchesSectionRef.current?.scrollIntoView({ behavior: "smooth" });
    }, 150);
  };

  return (
    <div className="page jobs-page">
      {/* Toast notification */}
      {notification && (
        <div className={`toast toast-${notification.type}`} role="status">
          {notification.msg}
        </div>
      )}

      {/* ZONE A: Page Identity + Primary Actions */}
      <header className="page-header jobs-page-header">
        <div className="page-header-row">
          <div className="jobs-title-wrap">
            <h1 className="jobs-page-title">{t("jobs.title", "Find Jobs")}</h1>
          </div>

          <div className="page-header-actions jobs-header-actions">
            {/* Desktop: Primary personalized action */}
            <div className="jobs-find-for-me-desktop">
              <div className="jobs-find-btn-row">
                <button
                  className="btn btn-primary jobs-find-desktop-btn"
                  onClick={handlePersonalizedDiscovery}
                  disabled={discovering}
                  type="button"
                  aria-label="Find Jobs for Me"
                >
                  {discovering ? (
                    <>
                      <span className="spinner-inline" />
                      <span>Finding matches...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles size={16} />
                      <span>{t("action.findJobsForMe", "Find Jobs for Me")}</span>
                    </>
                  )}
                </button>
              </div>
              <span className="jobs-find-sublabel">Let AI match jobs to your profile</span>
            </div>

            {/* Overflow More Menu (•••) */}
            <div className="jobs-more-menu-wrap" ref={moreMenuRef}>
              <button
                type="button"
                className="btn btn-secondary btn-icon jobs-more-trigger"
                onClick={() => setMoreMenuOpen((p) => !p)}
                aria-label="More options"
                aria-expanded={moreMenuOpen}
                aria-haspopup="true"
              >
                <MoreHorizontal size={18} />
              </button>

              {moreMenuOpen && (
                <div className="jobs-more-dropdown" role="menu">
                  <button
                    type="button"
                    className="jobs-more-menu-item"
                    role="menuitem"
                    onClick={() => {
                      setMoreMenuOpen(false);
                      setShowAddModal(true);
                    }}
                  >
                    Add Target Role
                  </button>
                  <button
                    type="button"
                    className="jobs-more-menu-item"
                    role="menuitem"
                    onClick={handleOpenSavedSearchesFromMenu}
                  >
                    My Saved Searches
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* ZONE B: Search Hero */}
      <section className="jobs-search-hero">
        <form
          role="search"
          className="jobs-search-form"
          onSubmit={handleSearchSubmit}
        >
          <label htmlFor="jobs-search-input" className="sr-only">
            Search jobs by job title, skill, or company
          </label>
          <div className="jobs-search-wrap">
            <Search size={18} className="search-icon" aria-hidden="true" />
            <input
              id="jobs-search-input"
              type="text"
              className="jobs-search-input"
              placeholder={t(
                "jobs.searchPlaceholder",
                "Search by job title, skill, or company..."
              )}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            {search && (
              <button
                type="button"
                className="search-clear-btn"
                onClick={handleClearSearch}
                aria-label="Clear search"
              >
                <X size={15} />
              </button>
            )}
          </div>
          <button
            type="submit"
            className="btn btn-primary jobs-search-submit-btn"
            disabled={discoverLoading}
          >
            {discoverLoading ? "Searching..." : "Search"}
          </button>
        </form>

        {/* Mobile: Full-width Find Jobs for Me button directly under search */}
        <div className="jobs-find-for-me-mobile">
          <button
            className="btn btn-primary btn-block jobs-find-mobile-btn"
            onClick={handlePersonalizedDiscovery}
            disabled={discovering}
            type="button"
          >
            {discovering ? (
              <>
                <span className="spinner-inline" />
                <span>Finding matches...</span>
              </>
            ) : (
              <>
                <Sparkles size={16} />
                <span>{t("action.findJobsForMe", "Find Jobs for Me")}</span>
              </>
            )}
          </button>
        </div>
      </section>

      {/* Discovery feedback banner (if any) */}
      {discoveryResult && (
        <div
          className={`discovery-feedback-banner banner-${discoveryResult.type}`}
          role={discoveryResult.type === "error" ? "alert" : "status"}
        >
          <div className="feedback-content">
            <span className="feedback-icon">
              {discoveryResult.type === "error" ? (
                <AlertTriangle size={16} />
              ) : (
                <Sparkles size={16} />
              )}
            </span>
            <div className="feedback-texts">
              <span className="feedback-text">{discoveryResult.message}</span>
              {discoveryResult.hint && (
                <span className="feedback-hint">{discoveryResult.hint}</span>
              )}
            </div>
          </div>

          {(discoveryResult.retryable ||
            discoveryResult.queries?.length > 0 ||
            discoveryResult.type === "incomplete") && (
            <div className="feedback-actions">
              {discoveryResult.retryable && !discovering && (
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={handlePersonalizedDiscovery}
                >
                  <RefreshCw size={14} />
                  <span>Try Again</span>
                </button>
              )}
              {discoveryResult.type === "incomplete" && (
                <Link to="/profile" className="btn btn-primary btn-sm">
                  <span>Complete Profile</span>
                  <ArrowRight size={14} />
                </Link>
              )}
              {discoveryResult.queries?.length > 0 && (
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

      {/* Back to recommended navigation when viewing search results */}
      {view !== "initial" && (
        <div className="jobs-back-nav">
          <button
            type="button"
            className="jobs-back-link"
            onClick={handleBackToRecommended}
          >
            ← {t("jobs.backToRecommended", "Recommended for you")}
          </button>
        </div>
      )}

      {/* ZONE C: Content Header + Filters */}
      <div className="jobs-content-header">
        <div className="jobs-context-col">
          <h2 className="jobs-context-label">
            {view === "initial" && (
              t("jobs.contextRecommended", "Recommended for you")
            )}
            {view === "searching" && (
              <span>{t("jobs.contextSearching", "Searching for")} &ldquo;{submittedQuery || search}&rdquo;...</span>
            )}
            {view === "external" && (
              <span>
                {t("jobs.contextResults", "Results for")} &ldquo;{submittedQuery}&rdquo;
                {externalResults.length > 0 && (
                  <span className="jobs-count-badge"> ({externalResults.length})</span>
                )}
              </span>
            )}
            {view === "error" && (
              <span>Search results</span>
            )}
          </h2>

          {view === "external" && duplicateCount > 0 && (
            <span className="jobs-merged-note">
              ({duplicateCount} duplicate listings merged across sources)
            </span>
          )}
        </div>

        <div className="jobs-header-filter-wrap">
          <button
            type="button"
            className={`btn btn-secondary jobs-filter-trigger ${
              activeFilterCount > 0 ? "filter-active" : ""
            }`}
            onClick={() => setFilterOpen((p) => !p)}
            aria-expanded={filterOpen}
            aria-label="Filter jobs"
          >
            <SlidersHorizontal size={15} />
            <span>{t("jobs.filtersButton", "Filters")}</span>
            {activeFilterCount > 0 && (
              <span className="jobs-filter-badge">{activeFilterCount}</span>
            )}
          </button>

          {/* Desktop Filter Popover */}
          {filterOpen && (
            <div
              className="jobs-filter-panel desktop-only card"
              ref={filterPanelRef}
              role="dialog"
              aria-label="Filter options"
            >
              <div className="jobs-filter-panel-header">
                <span className="filter-panel-title">Filters</span>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => {
                    setTypeFilter("");
                    setLevelFilter("");
                    resetDiscoverFilters();
                  }}
                >
                  Reset all
                </button>
              </div>

              <div className="jobs-filter-panel-body">
                <div className="jobs-filter-grid">
                  {/* Location - Spans both columns */}
                  <div className="form-group col-span-2">
                    <label className="form-label" htmlFor="fp-location">
                      Location
                    </label>
                    <input
                      id="fp-location"
                      type="text"
                      className="form-input"
                      placeholder="e.g. Pune or Remote"
                      value={discoverFilters.location}
                      onChange={(e) =>
                        setDiscoverFilters((f) => ({ ...f, location: e.target.value }))
                      }
                    />
                  </div>

                  {/* Work Mode */}
                  <div className="form-group">
                    <label className="form-label" htmlFor="fp-workmode">
                      Work Mode
                    </label>
                    <select
                      id="fp-workmode"
                      className="form-select"
                      value={discoverFilters.remote}
                      onChange={(e) =>
                        setDiscoverFilters((f) => ({ ...f, remote: e.target.value }))
                      }
                    >
                      {WORK_MODES.map((m) => (
                        <option key={m} value={m}>
                          {m === "" ? "Any Work Mode" : m}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Posted Date */}
                  <div className="form-group">
                    <label className="form-label" htmlFor="fp-posted">
                      Posted Date
                    </label>
                    <select
                      id="fp-posted"
                      className="form-select"
                      value={discoverFilters.posted}
                      onChange={(e) =>
                        setDiscoverFilters((f) => ({ ...f, posted: e.target.value }))
                      }
                    >
                      {POSTED_OPTIONS.map((o) => (
                        <option key={o.value} value={o.value}>
                          {o.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Job Type (Internal-only truthful limitation) */}
                  <div className="form-group">
                    <label className="form-label" htmlFor="fp-type">
                      Job Type {view === "external" && <span className="text-muted">(internal)</span>}
                    </label>
                    <select
                      id="fp-type"
                      className="form-select"
                      value={typeFilter}
                      disabled={view === "external"}
                      onChange={(e) => setTypeFilter(e.target.value)}
                    >
                      <option value="">{t("jobs.allTypes", "All Types")}</option>
                      {EMPLOYMENT_TYPES.map((tVal) => (
                        <option key={tVal} value={tVal}>
                          {tVal}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Experience Level (Internal-only truthful limitation) */}
                  <div className="form-group">
                    <label className="form-label" htmlFor="fp-level">
                      Experience Level {view === "external" && <span className="text-muted">(internal)</span>}
                    </label>
                    <select
                      id="fp-level"
                      className="form-select"
                      value={levelFilter}
                      disabled={view === "external"}
                      onChange={(e) => setLevelFilter(e.target.value)}
                    >
                      <option value="">{t("jobs.allLevels", "All Levels")}</option>
                      {EXPERIENCE_LEVELS.map((lVal) => (
                        <option key={lVal} value={lVal}>
                          {lVal}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Collapsible: Advanced Criteria & Sources */}
                <div className="jobs-filter-accordion">
                  <button
                    type="button"
                    className="jobs-accordion-trigger"
                    onClick={() => setShowAdvancedFilters((p) => !p)}
                    aria-expanded={showAdvancedFilters}
                  >
                    <span>Advanced criteria & sources</span>
                    {showAdvancedFilters ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                  </button>

                  {showAdvancedFilters && (
                    <div className="jobs-filter-advanced-box">
                      <div className="jobs-filter-grid">
                        <div className="form-group">
                          <label className="form-label" htmlFor="fp-smin">
                            Min Salary (annual)
                          </label>
                          <input
                            id="fp-smin"
                            type="number"
                            className="form-input"
                            placeholder="e.g. 800000"
                            value={discoverFilters.salary_min}
                            onChange={(e) =>
                              setDiscoverFilters((f) => ({ ...f, salary_min: e.target.value }))
                            }
                          />
                        </div>
                        <div className="form-group">
                          <label className="form-label" htmlFor="fp-smax">
                            Max Salary (annual)
                          </label>
                          <input
                            id="fp-smax"
                            type="number"
                            className="form-input"
                            placeholder="e.g. 2500000"
                            value={discoverFilters.salary_max}
                            onChange={(e) =>
                              setDiscoverFilters((f) => ({ ...f, salary_max: e.target.value }))
                            }
                          />
                        </div>
                      </div>

                      {availableSources.length > 0 && (
                        <div className="discover-source-select" style={{ marginTop: "var(--space-3)" }}>
                          <span className="form-label">Job Sources</span>
                          <div className="source-checkboxes">
                            {availableSources.map((s) => (
                              <label key={s} className="source-checkbox">
                                <input
                                  type="checkbox"
                                  checked={discoverFilters.sources.includes(s)}
                                  onChange={() => toggleSource(s)}
                                />
                                <span>{s}</span>
                              </label>
                            ))}
                            {discoverFilters.sources.length === 0 && (
                              <span className="source-hint">All sources selected</span>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Collapsible: Saved Searches */}
                <div
                  className="jobs-filter-accordion"
                  ref={savedSearchesSectionRef}
                >
                  <button
                    type="button"
                    className="jobs-accordion-trigger"
                    onClick={() => setShowSavedSearches((p) => !p)}
                    aria-expanded={showSavedSearches}
                  >
                    <span className="accordion-label-wrap">
                      <ListChecks size={15} />
                      <span>Saved Searches</span>
                      {savedSearches.length > 0 && (
                        <span className="jobs-count-pill">{savedSearches.length}</span>
                      )}
                    </span>
                    {showSavedSearches ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                  </button>

                  {showSavedSearches && (
                    <div className="jobs-filter-saved-box">
                      {showSaveInput ? (
                        <div className="discover-save-input">
                          <input
                            type="text"
                            className="form-input"
                            placeholder="Name this search..."
                            value={saveName}
                            onChange={(e) => setSaveName(e.target.value)}
                            autoFocus
                          />
                          <button
                            className="btn btn-primary btn-sm"
                            onClick={async () => {
                              const ok = await handleSaveSearch(search);
                              if (ok) notify("Search saved. You can re-run it any time.");
                            }}
                            disabled={!saveName.trim()}
                          >
                            Save
                          </button>
                          <button
                            className="btn btn-ghost btn-sm"
                            onClick={() => {
                              setShowSaveInput(false);
                              setSaveName("");
                            }}
                          >
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm save-trigger-btn"
                          onClick={() => setShowSaveInput(true)}
                        >
                          <Bookmark size={14} />
                          <span>Save current search criteria</span>
                        </button>
                      )}

                      {savedSearches.length > 0 && (
                        <ul className="discover-saved-list" style={{ marginTop: "var(--space-2)" }}>
                          {savedSearches.map((s) => (
                            <li key={s.id} className="discover-saved-item">
                              <div className="discover-saved-info">
                                <span className="discover-saved-name">{s.name}</span>
                                <span className="discover-saved-meta text-muted">
                                  {s.last_seen_count > 0
                                    ? `${s.last_seen_count} results`
                                    : "Saved"}
                                </span>
                              </div>
                              <div className="discover-saved-actions">
                                <button
                                  type="button"
                                  className="btn btn-ghost btn-sm"
                                  onClick={async () => {
                                    try {
                                      await handleRunSaved(s.id);
                                      setView("external");
                                      setSubmittedQuery(s.name);
                                      setFilterOpen(false);
                                      notify(`Loaded results for "${s.name}".`);
                                    } catch {
                                      notify("Failed to run saved search.", "error");
                                    }
                                  }}
                                  title="Run now"
                                >
                                  <Play size={13} />
                                  <span>Run</span>
                                </button>
                                <button
                                  type="button"
                                  className="btn btn-ghost btn-sm"
                                  onClick={async () => {
                                    await handleDeleteSaved(s.id);
                                    notify("Saved search deleted.");
                                  }}
                                  title="Delete"
                                >
                                  <Trash2 size={13} />
                                </button>
                              </div>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}
                </div>
              </div>

              <div className="jobs-filter-panel-actions">
                <button
                  type="button"
                  className="btn btn-primary btn-block"
                  onClick={() => {
                    setFilterOpen(false);
                    triggerExternalSearch(search);
                  }}
                >
                  Apply Filters
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Mobile Bottom Sheet Drawer for Filters */}
      {filterOpen && (
        <div className="jobs-filter-drawer-backdrop mobile-only" onClick={() => setFilterOpen(false)}>
          <div
            className="jobs-filter-drawer"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-label="Filter jobs"
          >
            <div className="drawer-handle" />
            <div className="jobs-filter-panel-header">
              <span className="filter-panel-title">Filters</span>
              <div className="drawer-header-actions">
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => {
                    setTypeFilter("");
                    setLevelFilter("");
                    resetDiscoverFilters();
                  }}
                >
                  Reset
                </button>
                <button
                  type="button"
                  className="btn btn-ghost btn-icon btn-sm drawer-close-btn"
                  onClick={() => setFilterOpen(false)}
                  aria-label="Close filters"
                >
                  <X size={18} />
                </button>
              </div>
            </div>

            <div className="jobs-drawer-body">
              {/* Location */}
              <div className="form-group">
                <label className="form-label" htmlFor="mob-location">Location</label>
                <input
                  id="mob-location"
                  type="text"
                  className="form-input"
                  placeholder="e.g. Pune or Remote"
                  value={discoverFilters.location}
                  onChange={(e) =>
                    setDiscoverFilters((f) => ({ ...f, location: e.target.value }))
                  }
                />
              </div>

              {/* Work Mode & Posted Date */}
              <div className="jobs-filter-grid">
                <div className="form-group">
                  <label className="form-label" htmlFor="mob-workmode">Work Mode</label>
                  <select
                    id="mob-workmode"
                    className="form-select"
                    value={discoverFilters.remote}
                    onChange={(e) =>
                      setDiscoverFilters((f) => ({ ...f, remote: e.target.value }))
                    }
                  >
                    {WORK_MODES.map((m) => (
                      <option key={m} value={m}>
                        {m === "" ? "Any Work Mode" : m}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="mob-posted">Posted Date</label>
                  <select
                    id="mob-posted"
                    className="form-select"
                    value={discoverFilters.posted}
                    onChange={(e) =>
                      setDiscoverFilters((f) => ({ ...f, posted: e.target.value }))
                    }
                  >
                    {POSTED_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Job Type & Experience Level */}
              <div className="jobs-filter-grid">
                <div className="form-group">
                  <label className="form-label" htmlFor="mob-type">
                    Job Type {view === "external" && <span className="text-muted">(internal)</span>}
                  </label>
                  <select
                    id="mob-type"
                    className="form-select"
                    value={typeFilter}
                    disabled={view === "external"}
                    onChange={(e) => setTypeFilter(e.target.value)}
                  >
                    <option value="">{t("jobs.allTypes", "All Types")}</option>
                    {EMPLOYMENT_TYPES.map((tVal) => (
                      <option key={tVal} value={tVal}>
                        {tVal}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="mob-level">
                    Experience Level {view === "external" && <span className="text-muted">(internal)</span>}
                  </label>
                  <select
                    id="mob-level"
                    className="form-select"
                    value={levelFilter}
                    disabled={view === "external"}
                    onChange={(e) => setLevelFilter(e.target.value)}
                  >
                    <option value="">{t("jobs.allLevels", "All Levels")}</option>
                    {EXPERIENCE_LEVELS.map((lVal) => (
                      <option key={lVal} value={lVal}>
                        {lVal}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Collapsible Advanced Criteria */}
              <div className="jobs-filter-accordion">
                <button
                  type="button"
                  className="jobs-accordion-trigger"
                  onClick={() => setShowAdvancedFilters((p) => !p)}
                  aria-expanded={showAdvancedFilters}
                >
                  <span>Advanced criteria & sources</span>
                  {showAdvancedFilters ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                </button>

                {showAdvancedFilters && (
                  <div className="jobs-filter-advanced-box">
                    <div className="jobs-filter-grid">
                      <div className="form-group">
                        <label className="form-label" htmlFor="mob-smin">Min Salary</label>
                        <input
                          id="mob-smin"
                          type="number"
                          className="form-input"
                          placeholder="e.g. 800000"
                          value={discoverFilters.salary_min}
                          onChange={(e) =>
                            setDiscoverFilters((f) => ({ ...f, salary_min: e.target.value }))
                          }
                        />
                      </div>
                      <div className="form-group">
                        <label className="form-label" htmlFor="mob-smax">Max Salary</label>
                        <input
                          id="mob-smax"
                          type="number"
                          className="form-input"
                          placeholder="e.g. 2500000"
                          value={discoverFilters.salary_max}
                          onChange={(e) =>
                            setDiscoverFilters((f) => ({ ...f, salary_max: e.target.value }))
                          }
                        />
                      </div>
                    </div>
                    {availableSources.length > 0 && (
                      <div className="discover-source-select" style={{ marginTop: "var(--space-3)" }}>
                        <span className="form-label">Job Sources</span>
                        <div className="source-checkboxes">
                          {availableSources.map((s) => (
                            <label key={s} className="source-checkbox">
                              <input
                                type="checkbox"
                                checked={discoverFilters.sources.includes(s)}
                                onChange={() => toggleSource(s)}
                              />
                              <span>{s}</span>
                            </label>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Collapsible Saved Searches */}
              <div className="jobs-filter-accordion">
                <button
                  type="button"
                  className="jobs-accordion-trigger"
                  onClick={() => setShowSavedSearches((p) => !p)}
                  aria-expanded={showSavedSearches}
                >
                  <span className="accordion-label-wrap">
                    <ListChecks size={15} />
                    <span>Saved Searches</span>
                    {savedSearches.length > 0 && (
                      <span className="jobs-count-pill">{savedSearches.length}</span>
                    )}
                  </span>
                  {showSavedSearches ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                </button>

                {showSavedSearches && (
                  <div className="jobs-filter-saved-box">
                    {showSaveInput ? (
                      <div className="discover-save-input">
                        <input
                          type="text"
                          className="form-input"
                          placeholder="Name this search..."
                          value={saveName}
                          onChange={(e) => setSaveName(e.target.value)}
                          autoFocus
                        />
                        <button
                          className="btn btn-primary btn-sm"
                          onClick={async () => {
                            const ok = await handleSaveSearch(search);
                            if (ok) notify("Search saved.");
                          }}
                          disabled={!saveName.trim()}
                        >
                          Save
                        </button>
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={() => {
                            setShowSaveInput(false);
                            setSaveName("");
                          }}
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm save-trigger-btn"
                        onClick={() => setShowSaveInput(true)}
                      >
                        <Bookmark size={14} />
                        <span>Save current search criteria</span>
                      </button>
                    )}

                    {savedSearches.length > 0 && (
                      <ul className="discover-saved-list" style={{ marginTop: "var(--space-2)" }}>
                        {savedSearches.map((s) => (
                          <li key={s.id} className="discover-saved-item">
                            <div className="discover-saved-info">
                              <span className="discover-saved-name">{s.name}</span>
                            </div>
                            <div className="discover-saved-actions">
                              <button
                                type="button"
                                className="btn btn-ghost btn-sm"
                                onClick={async () => {
                                  try {
                                    await handleRunSaved(s.id);
                                    setView("external");
                                    setSubmittedQuery(s.name);
                                    setFilterOpen(false);
                                    notify(`Loaded results for "${s.name}".`);
                                  } catch {
                                    notify("Failed to run search.", "error");
                                  }
                                }}
                              >
                                Run
                              </button>
                              <button
                                type="button"
                                className="btn btn-ghost btn-sm"
                                onClick={async () => {
                                  await handleDeleteSaved(s.id);
                                  notify("Search deleted.");
                                }}
                              >
                                <Trash2 size={13} />
                              </button>
                            </div>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </div>
            </div>

            <div className="jobs-filter-panel-actions">
              <button
                type="button"
                className="btn btn-primary btn-block"
                onClick={() => {
                  setFilterOpen(false);
                  triggerExternalSearch(search);
                }}
              >
                Apply Filters
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ZONE D: Job Results Feed */}
      {view === "searching" || (view === "initial" && loading) ? (
        <div className="stack" style={{ gap: "var(--space-4)" }}>
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : view === "error" || discoverError ? (
        <div className="discovery-feedback-banner banner-error" role="alert">
          <div className="feedback-content">
            <span className="feedback-icon">
              <AlertTriangle size={16} />
            </span>
            <div className="feedback-texts">
              <span className="feedback-text">
                {discoverError || "We couldn't complete the search right now."}
              </span>
              <span className="feedback-hint">
                Please check your network connection and try again.
              </span>
            </div>
          </div>
          <div className="feedback-actions">
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => triggerExternalSearch(submittedQuery || search)}
            >
              <RefreshCw size={14} />
              <span>Retry Search</span>
            </button>
          </div>
        </div>
      ) : view === "external" ? (
        externalResults.length === 0 ? (
          <EmptyState
            icon={Search}
            title={`No results for "${submittedQuery}"`}
            description="Try a different keyword, broaden your location, or adjust filters."
            action={
              <div className="empty-state-actions">
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={handleClearSearch}
                  type="button"
                >
                  Clear search
                </button>
                <button
                  className="btn btn-primary btn-sm"
                  onClick={() => setFilterOpen(true)}
                  type="button"
                >
                  Adjust Filters
                </button>
              </div>
            }
          />
        ) : (
          <div className="jobs-list-stack">
            {externalResults.map((job) => (
              <DiscoverCard key={job.canonical_key} job={job} />
            ))}
          </div>
        )
      ) : (
        /* INITIAL VIEW: Internal / Recommended Jobs Feed */
        filteredInternalJobs.length === 0 ? (
          <EmptyState
            icon={Compass}
            title={
              search || typeFilter || levelFilter
                ? "No jobs match your current filters"
                : "Your personalized matches will appear here"
            }
            description={
              search || typeFilter || levelFilter
                ? "Try adjusting your search criteria or resetting filters."
                : "Find jobs based on your skills and career profile."
            }
            action={
              search || typeFilter || levelFilter ? (
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => {
                    setSearch("");
                    setTypeFilter("");
                    setLevelFilter("");
                  }}
                  type="button"
                >
                  Clear Filters
                </button>
              ) : (
                <div className="empty-state-actions">
                  <button
                    className="btn btn-primary"
                    onClick={handlePersonalizedDiscovery}
                    disabled={discovering}
                    type="button"
                  >
                    <Compass size={16} />
                    <span>{t("action.findJobsForMe", "Find Jobs for Me")}</span>
                  </button>
                  <button
                    className="btn btn-ghost"
                    onClick={() => {
                      const input = document.getElementById("jobs-search-input");
                      input?.focus();
                    }}
                    type="button"
                  >
                    <span>{t("jobs.searchNudge", "Search for a role →")}</span>
                  </button>
                </div>
              )
            }
          />
        ) : (
          <div className="jobs-list-stack">
            {filteredInternalJobs.map((job) => {
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

                      {score > 0 && (
                        <div className="job-card-score-col">
                          <ScoreBadge score={score} />
                        </div>
                      )}
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

                    {/* Match indicator only when backed by genuine data */}
                    {score >= 70 && (
                      <div className="job-card-fit-summary">
                        <span className="fit-point positive">
                          <CheckCircle2 size={14} className="text-success" />
                          <span>High skill & role alignment with your profile</span>
                        </span>
                      </div>
                    )}
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
                        <span>{t("jobs.viewDetails", "View Details")}</span>
                        <ArrowRight size={14} />
                      </Link>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )
      )}

      {/* Add Target Role Modal (Zone E - Secondary modal, unchanged API) */}
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
                  {EMPLOYMENT_TYPES.map((tVal) => (
                    <option key={tVal} value={tVal}>
                      {tVal}
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
