import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { api } from "../services/api";
import { useJobSearch } from "../hooks/useJobSearch";
import JobSearchBar from "../components/jobs/JobSearchBar";
import JobQuickFilters from "../components/jobs/JobQuickFilters";
import JobFilterDrawer from "../components/jobs/JobFilterDrawer";
import JobCard from "../components/jobs/JobCard";
import JobFeedHeader from "../components/jobs/JobFeedHeader";
import AddJobModal from "../components/jobs/AddJobModal";
import ExternalApplyToast from "../components/jobs/ExternalApplyToast";
import { normalizeJob, normalizeWorkMode } from "../components/jobs/jobUtils";
import { SkeletonCard } from "../components/Skeleton";
import EmptyState from "../components/EmptyState";
import { Sparkles, Compass, Search, Plus } from "lucide-react";

export default function JobsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  // URL-derived state
  const query = searchParams.get("q") || "";
  const location = searchParams.get("location") || "";
  const remote = searchParams.get("remote") || "";
  const type = searchParams.get("type") || "";
  const level = searchParams.get("level") || "";
  const posted = searchParams.get("posted") || "";
  const smin = searchParams.get("smin") || "";
  const smax = searchParams.get("smax") || "";
  const sourcesParam = searchParams.get("sources") || "";
  const sources = useMemo(
    () => (sourcesParam ? sourcesParam.split(",").filter(Boolean) : []),
    [sourcesParam]
  );
  const sort = searchParams.get("sort") || "match";

  // Feed & application state
  const [feedJobs, setFeedJobs] = useState([]);
  const [savedJobIds, setSavedJobIds] = useState(new Set());
  const [feedLoading, setFeedLoading] = useState(true);
  const [feedError, setFeedError] = useState(null);

  // Materialization & saving loading state
  const [materializingId, setMaterializingId] = useState(null);
  const [savingId, setSavingId] = useState(null);

  // Personalized discovery in-flight state
  const [discovering, setDiscovering] = useState(false);

  // Modals & Drawers
  const [isFilterDrawerOpen, setIsFilterDrawerOpen] = useState(false);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [notification, setNotification] = useState(null);
  const [externalApplyPromptJob, setExternalApplyPromptJob] = useState(null);

  // Session-level materialization cache: canonical_key -> local job ID
  const sessionCacheRef = useRef(new Map());

  // Discovery search hook
  const {
    availableSources,
    savedSearches,
    executeSearch,
    handleSaveSearch,
    handleRunSaved,
    handleDeleteSaved,
  } = useJobSearch();

  const notify = useCallback((msg, type = "success") => {
    setNotification({ msg, type });
    setTimeout(() => setNotification(null), 3500);
  }, []);

  // Compute active filters
  const hasSearchOrFilters = useMemo(() => {
    return Boolean(
      query || location || remote || type || level || posted || smin || smax || sources.length > 0
    );
  }, [query, location, remote, type, level, posted, smin, smax, sources]);

  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (location) count++;
    if (remote) count++;
    if (type) count++;
    if (level) count++;
    if (posted) count++;
    if (smin || smax) count++;
    if (sources.length > 0) count++;
    return count;
  }, [location, remote, type, level, posted, smin, smax, sources]);

  // URL state update helper
  const updateUrlParams = useCallback(
    (newParams, replace = false) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        Object.entries(newParams).forEach(([key, val]) => {
          if (
            val === null ||
            val === undefined ||
            val === "" ||
            (Array.isArray(val) && val.length === 0)
          ) {
            next.delete(key);
          } else if (Array.isArray(val)) {
            next.set(key, val.join(","));
          } else {
            next.set(key, String(val));
          }
        });
        return next;
      }, { replace });
    },
    [setSearchParams]
  );

  // Load user applications (saved jobs)
  const loadSavedJobIds = useCallback(async () => {
    try {
      const apps = await api.get("/applications/").catch(() => []);
      if (Array.isArray(apps)) {
        setSavedJobIds(new Set(apps.map((a) => a.job_id)));
      }
    } catch {
      // Non-blocking
    }
  }, []);

  // Fetch default personalized/recommended feed.
  // Prefer the fast persisted feed (/jobs/feed); fall back to the legacy
  // dual-call path on error or empty feed so manual /role-added jobs still
  // appear when no personalized recommendations exist yet.
  const loadDefaultFeed = useCallback(async () => {
    setFeedLoading(true);
    setFeedError(null);
    try {
      const feedRes = await api.getFeed();
      const feedList = Array.isArray(feedRes?.jobs) ? feedRes.jobs : [];
      if (feedList.length > 0) {
        setFeedJobs(
          feedList.map((item) => normalizeJob(item, sessionCacheRef.current)).filter(Boolean)
        );
        return;
      }
      // Empty personalized feed: fall back to existing dual path so
      // manually added roles (no JobMatch yet) are still visible.
      const [allJobsRes, recsRes] = await Promise.all([
        api.get("/jobs/").catch(() => []),
        api.get("/jobs/recommended").catch(() => []),
      ]);
      const jobsList = Array.isArray(allJobsRes) ? allJobsRes : [];
      const recsList = Array.isArray(recsRes) ? recsRes : [];
      const rawCombined = recsList.length > 0 ? recsList : jobsList;
      setFeedJobs(
        rawCombined.map((item) => normalizeJob(item, sessionCacheRef.current)).filter(Boolean)
      );
    } catch {
      setFeedError("Could not load opportunities right now. Please try again.");
      setFeedJobs([]);
    } finally {
      setFeedLoading(false);
    }
  }, []);

  // Fetch search/filtered feed
  const loadFilteredFeed = useCallback(async () => {
    setFeedLoading(true);
    setFeedError(null);
    try {
      const res = await executeSearch({
        query,
        location,
        remote,
        type,
        level,
        posted,
        smin,
        smax,
        sources,
      });

      const hits = Array.isArray(res?.results) ? res.results : [];
      let normalized = hits
        .map((hit) => normalizeJob(hit, sessionCacheRef.current))
        .filter(Boolean);

      // Exact work-mode filtering. The backend `remote` criterion is a
      // best-effort superset (Remote/Hybrid kept for true, Hybrid/Onsite for
      // false); the authoritative exact filter runs here against the hit's
      // canonical work_mode so "Remote" shows only remote, "Hybrid" only
      // hybrid, and "Onsite" only onsite — never a silent no-op.
      const canonicalFilter = normalizeWorkMode(remote);
      if (canonicalFilter === "remote") {
        normalized = normalized.filter((j) => normalizeWorkMode(j.work_mode, j.location) === "remote");
      } else if (canonicalFilter === "hybrid") {
        normalized = normalized.filter((j) => normalizeWorkMode(j.work_mode, j.location) === "hybrid");
      } else if (canonicalFilter === "onsite") {
        normalized = normalized.filter((j) => normalizeWorkMode(j.work_mode, j.location) === "onsite");
      }

      setFeedJobs(normalized);
    } catch {
      setFeedError("Could not complete the search right now. Please check your connection.");
      setFeedJobs([]);
    } finally {
      setFeedLoading(false);
    }
  }, [executeSearch, query, location, remote, type, level, posted, smin, smax, sources]);

  // Initial load & URL synchronization
  useEffect(() => {
    loadSavedJobIds();
  }, [loadSavedJobIds]);

  useEffect(() => {
    if (hasSearchOrFilters) {
      loadFilteredFeed();
    } else {
      loadDefaultFeed();
    }
  }, [hasSearchOrFilters, loadFilteredFeed, loadDefaultFeed]);

  // Handle Find Jobs for Me
  const handleFindJobsForMe = async () => {
    if (discovering) return;
    setDiscovering(true);
    try {
      const res = await api.discoverPersonalizedJobs();
      const newJobsCount = res?.new_jobs || 0;
      if (newJobsCount > 0) {
        notify(`${newJobsCount} new ${newJobsCount === 1 ? "match" : "matches"} found for you!`);
      } else {
        notify("Your personalized opportunities are up to date.");
      }
      // Refresh feed
      if (hasSearchOrFilters) {
        await loadFilteredFeed();
      } else {
        await loadDefaultFeed();
      }
    } catch {
      notify("Personalized discovery is unavailable right now. Please try again.", "error");
    } finally {
      setDiscovering(false);
    }
  };

  // Materialize external job into DB using only supported JobCreate fields
  const materializeExternalJob = async (job) => {
    const payload = {
      title: job.title,
      company: job.company,
      location: job.location || null,
      employment_type: job.employment_type || null,
      experience_level: job.experience_level || null,
      description: job.description || null,
      required_skills:
        Array.isArray(job.skills) && job.skills.length > 0 ? job.skills.join(", ") : null,
      application_url: job.application_url || null,
      source: job.source || "Discovery",
    };
    const created = await api.post("/jobs/", payload);
    if (created?.id) {
      sessionCacheRef.current.set(job.canonical_key, created.id);
      return created.id;
    }
    throw new Error("Materialization failed");
  };

  // View Details handler
  const handleViewDetails = async (job) => {
    const existingId = job.id || sessionCacheRef.current.get(job.canonical_key);
    if (existingId) {
      navigate(`/discover/${existingId}`);
      return;
    }

    setMaterializingId(job.canonical_key);
    try {
      const newId = await materializeExternalJob(job);
      navigate(`/discover/${newId}`);
    } catch {
      notify("Could not open job details. Please try again.", "error");
    } finally {
      setMaterializingId(null);
    }
  };

  // Save / Bookmark handler
  const handleToggleSave = async (job) => {
    let localId = job.id || sessionCacheRef.current.get(job.canonical_key);

    if (!localId) {
      setSavingId(job.canonical_key);
      try {
        localId = await materializeExternalJob(job);
        setFeedJobs((prev) =>
          prev.map((item) =>
            item.canonical_key === job.canonical_key ? { ...item, id: localId } : item
          )
        );
      } catch {
        notify("Failed to save job. Please try again.", "error");
        setSavingId(null);
        return;
      }
    }

    setSavingId(localId);
    try {
      const isSaved = savedJobIds.has(localId);
      if (isSaved) {
        const apps = await api.get("/applications/").catch(() => []);
        const app = Array.isArray(apps) ? apps.find((a) => a.job_id === localId) : null;
        if (app?.id) {
          await api.delete(`/applications/${app.id}`);
          setSavedJobIds((prev) => {
            const next = new Set(prev);
            next.delete(localId);
            return next;
          });
          notify("Removed from saved opportunities.");
        }
      } else {
        await api.post("/applications/", { job_id: localId, status: "Saved" });
        setSavedJobIds((prev) => new Set([...prev, localId]));
        notify("Job saved to your applications pipeline.");
      }
    } catch {
      notify("Failed to update application status.", "error");
    } finally {
      setSavingId(null);
    }
  };

  // External Application tracking handler
  const handleExternalApply = (job, targetUrl) => {
    if (targetUrl) {
      window.open(targetUrl, "_blank", "noopener,noreferrer");
    }
    setExternalApplyPromptJob(job);
  };

  const handleConfirmMarkApplied = async (job) => {
    if (!job) return;
    let localId = job.id || sessionCacheRef.current.get(job.canonical_key);

    if (!localId) {
      try {
        localId = await materializeExternalJob(job);
        setFeedJobs((prev) =>
          prev.map((item) =>
            item.canonical_key === job.canonical_key ? { ...item, id: localId } : item
          )
        );
      } catch {
        notify("Failed to track application.", "error");
        return;
      }
    }

    try {
      const apps = await api.get("/applications/").catch(() => []);
      const existing = Array.isArray(apps) ? apps.find((a) => a.job_id === localId) : null;
      if (existing?.id) {
        await api.put(`/applications/${existing.id}`, { status: "Applied" });
      } else {
        await api.post("/applications/", { job_id: localId, status: "Applied" });
      }
      setSavedJobIds((prev) => new Set([...prev, localId]));
      notify("Application tracked as Applied in your pipeline.");
    } catch {
      notify("Failed to update application status.", "error");
    }
  };

  // Handle running a saved search
  const handleRunSavedSearchFromDrawer = async (savedSearch) => {
    try {
      const res = await handleRunSaved(savedSearch.id);
      const hits = Array.isArray(res?.report?.results) ? res.report.results : [];
      let normalized = hits
        .map((hit) => normalizeJob(hit, sessionCacheRef.current))
        .filter(Boolean);

      // Replay exact work-mode filtering consistent with discovery filter contract.
      // Prefer preserved UI mode (_remote_mode); safely fall back to legacy boolean remote if absent.
      let canonicalFilter = null;
      if (savedSearch?.criteria?._remote_mode !== undefined) {
        const raw = savedSearch.criteria._remote_mode;
        if (raw) canonicalFilter = normalizeWorkMode(raw);
      } else if (savedSearch?.criteria?.remote !== undefined && savedSearch.criteria.remote !== null) {
        // Legacy fallback for saved searches created before _remote_mode preservation
        canonicalFilter = normalizeWorkMode(savedSearch.criteria.remote);
      }

      if (canonicalFilter === "remote") {
        normalized = normalized.filter((j) => normalizeWorkMode(j.work_mode, j.location) === "remote");
      } else if (canonicalFilter === "hybrid") {
        normalized = normalized.filter((j) => normalizeWorkMode(j.work_mode, j.location) === "hybrid");
      } else if (canonicalFilter === "onsite") {
        normalized = normalized.filter((j) => normalizeWorkMode(j.work_mode, j.location) === "onsite");
      }

      setFeedJobs(normalized);
      notify(`Loaded saved search "${savedSearch.name}".`);
    } catch {
      notify("Failed to run saved search.", "error");
    }
  };

  // Sorted jobs in feed
  const sortedJobs = useMemo(() => {
    const list = [...feedJobs];
    if (sort === "match") {
      return list.sort((a, b) => (b.match_score || 0) - (a.match_score || 0));
    }
    if (sort === "newest") {
      return list.sort((a, b) => {
        const timeA = a.posted_at ? new Date(a.posted_at).getTime() : 0;
        const timeB = b.posted_at ? new Date(b.posted_at).getTime() : 0;
        return timeB - timeA;
      });
    }
    return list; // relevance / default
  }, [feedJobs, sort]);

  const activeFiltersObj = useMemo(
    () => ({
      location,
      remote,
      type,
      level,
      posted,
      smin,
      smax,
      sources,
    }),
    [location, remote, type, level, posted, smin, smax, sources]
  );

  return (
    <div className="jobs-unified-page page">
      {/* Toast feedback */}
      {notification && (
        <div className={`toast toast-${notification.type}`} role="status">
          {notification.msg}
        </div>
      )}

      {/* LEVEL 1: Page Identity & Secondary Action */}
      <header className="jobs-unified-header">
        <div className="jobs-identity-col">
          <h1 className="jobs-unified-title">Find Jobs</h1>
          <p className="jobs-unified-subtitle">
            Search naturally for roles, skills, or companies with AI-aligned matching
          </p>
        </div>

        <div className="jobs-header-actions">
          <button
            type="button"
            className="btn btn-secondary btn-sm jobs-add-target-btn"
            onClick={() => setIsAddModalOpen(true)}
            aria-label="Add target role manually"
          >
            <Plus size={15} />
            <span>Add Role</span>
          </button>

          <button
            type="button"
            className="btn btn-primary btn-sm jobs-find-for-me-btn"
            onClick={handleFindJobsForMe}
            disabled={discovering}
            aria-label="Find Jobs for Me with AI"
          >
            {discovering ? (
              <>
                <span className="spinner-inline" />
                <span>Matching...</span>
              </>
            ) : (
              <>
                <Sparkles size={15} />
                <span>Find Jobs for Me</span>
              </>
            )}
          </button>
        </div>
      </header>

      {/* LEVEL 2: Primary Search Bar */}
      <section className="jobs-search-section">
        <JobSearchBar
          query={query}
          onSearch={(newQuery) => updateUrlParams({ q: newQuery })}
          onClear={() => updateUrlParams({ q: "" })}
          loading={feedLoading}
        />
      </section>

      {/* LEVEL 3: Quick Filter Chips */}
      <section className="jobs-quick-filters-section">
        <JobQuickFilters
          filters={activeFiltersObj}
          onFilterChange={(key, val) => updateUrlParams({ [key]: val })}
          onOpenAllFilters={() => setIsFilterDrawerOpen(true)}
          activeFilterCount={activeFilterCount}
          onResetAll={() => setSearchParams({})}
        />
      </section>

      {/* LEVEL 4 & 5: AI Context + Result Header Controls */}
      <section className="jobs-results-container">
        <JobFeedHeader
          count={sortedJobs.length}
          hasProfileContext={!hasSearchOrFilters || !query}
          sort={sort}
          onSortChange={(newSort) => updateUrlParams({ sort: newSort })}
        />

        {/* LEVEL 6: Unified Feed */}
        {feedLoading ? (
          <div className="stack" style={{ gap: "var(--space-4)" }}>
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </div>
        ) : feedError ? (
          <div className="discovery-feedback-banner banner-error" role="alert">
            <div className="feedback-content">
              <span className="feedback-text">{feedError}</span>
            </div>
            <div className="feedback-actions">
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => (hasSearchOrFilters ? loadFilteredFeed() : loadDefaultFeed())}
              >
                Retry
              </button>
            </div>
          </div>
        ) : sortedJobs.length === 0 ? (
          <EmptyState
            icon={hasSearchOrFilters ? Search : Compass}
            title={hasSearchOrFilters ? "No roles match these filters" : "No recommended opportunities yet"}
            description={
              hasSearchOrFilters
                ? "Try broadening your search terms or clearing some filters to see more results."
                : "Complete your profile or run 'Find Jobs for Me' to discover personalized opportunities."
            }
            action={
              hasSearchOrFilters ? (
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => setSearchParams({})}
                >
                  Clear Filters
                </button>
              ) : (
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  onClick={handleFindJobsForMe}
                  disabled={discovering}
                >
                  <Sparkles size={14} />
                  <span>Find Jobs for Me</span>
                </button>
              )
            }
          />
        ) : (
          <div className="jobs-feed-list">
            {sortedJobs.map((job) => {
              const key = job.canonical_key || job.id;
              const isSaved = (job.id && savedJobIds.has(job.id)) || false;
              const isMaterializing = materializingId === job.canonical_key;
              const isSaving = savingId === job.canonical_key || (job.id && savingId === job.id);

              return (
                <JobCard
                  key={key}
                  job={job}
                  isSaved={isSaved}
                  onToggleSave={handleToggleSave}
                  onViewDetails={handleViewDetails}
                  onExternalApply={handleExternalApply}
                  isMaterializing={isMaterializing}
                  isSaving={isSaving}
                />
              );
            })}
          </div>
        )}
      </section>

      {/* Filter Drawer (Desktop Right Drawer & Mobile Bottom Sheet) */}
      <JobFilterDrawer
        isOpen={isFilterDrawerOpen}
        onClose={() => setIsFilterDrawerOpen(false)}
        filters={activeFiltersObj}
        onApply={(draft) => updateUrlParams(draft)}
        onReset={() => setSearchParams({})}
        availableSources={availableSources}
        savedSearches={savedSearches}
        onSaveSearch={async (name, draft) => {
          const ok = await handleSaveSearch(name, { ...draft, query });
          if (ok) notify("Search saved. You can re-run it anytime.");
          return ok;
        }}
        onRunSavedSearch={handleRunSavedSearchFromDrawer}
        onDeleteSavedSearch={async (id) => {
          await handleDeleteSaved(id);
          notify("Saved search deleted.");
        }}
      />

      {/* Add Target Role Modal */}
      <AddJobModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onJobAdded={() => {
          if (hasSearchOrFilters) {
            loadFilteredFeed();
          } else {
            loadDefaultFeed();
          }
        }}
        notify={notify}
      />

      {/* External Application Follow-up Toast */}
      {externalApplyPromptJob && (
        <ExternalApplyToast
          job={externalApplyPromptJob}
          onConfirm={() => {
            handleConfirmMarkApplied(externalApplyPromptJob);
            setExternalApplyPromptJob(null);
          }}
          onDismiss={() => setExternalApplyPromptJob(null)}
        />
      )}
    </div>
  );
}
