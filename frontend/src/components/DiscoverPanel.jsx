import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../services/api";
import ScoreBadge from "./ScoreBadge";
import EmptyState from "./EmptyState";
import {
  Search,
  Compass,
  Sparkles,
  Bookmark,
  ListChecks,
  Trash2,
  Play,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Layers,
  Clock,
} from "lucide-react";

const WORK_MODES = ["", "Remote", "Hybrid", "Onsite"];
const POSTED_OPTIONS = [
  { value: "", label: "Any time" },
  { value: "7", label: "Past week" },
  { value: "14", label: "Past 2 weeks" },
  { value: "30", label: "Past month" },
];

const DEFAULT_FILTERS = {
  query: "",
  location: "",
  remote: "",
  salary_min: "",
  salary_max: "",
  posted: "",
  sources: [],
};

function postedAfterDays(days) {
  if (!days) return null;
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - Number(days));
  return d.toISOString();
}

export default function DiscoverPanel() {
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [availableSources, setAvailableSources] = useState([]);
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);
  const [savedSearches, setSavedSearches] = useState([]);
  const [saveName, setSaveName] = useState("");
  const [showSaveInput, setShowSaveInput] = useState(false);
  const [notification, setNotification] = useState(null);

  const notify = (msg, type = "success") => {
    setNotification({ msg, type });
    setTimeout(() => setNotification(null), 3200);
  };

  const loadSources = useCallback(async () => {
    try {
      const res = await api.getDiscoverSources();
      setAvailableSources(Array.isArray(res?.sources) ? res.sources : []);
    } catch {
      setAvailableSources([]);
    }
  }, []);

  const loadSavedSearches = useCallback(async () => {
    try {
      const list = await api.getSavedSearches();
      setSavedSearches(Array.isArray(list) ? list : []);
    } catch {
      setSavedSearches([]);
    }
  }, []);

  useEffect(() => {
    loadSources();
    loadSavedSearches();
  }, [loadSources, loadSavedSearches]);

  const hasActiveFilters = useMemo(
    () =>
      filters.query ||
      filters.location ||
      filters.remote ||
      filters.salary_min ||
      filters.salary_max ||
      filters.posted ||
      filters.sources.length > 0,
    [filters]
  );

  const buildRequest = () => ({
    queries: filters.query ? [filters.query] : [],
    locations: filters.location ? [filters.location] : [],
    remote: filters.remote === "Remote" ? true : filters.remote === "Onsite" ? false : null,
    salary_min: filters.salary_min ? Number(filters.salary_min) : null,
    salary_max: filters.salary_max ? Number(filters.salary_max) : null,
    salary_period: "annual",
    posted_after: postedAfterDays(filters.posted),
    sort: "newest",
    sources: filters.sources,
    page_size: 30,
    include_profile_alignment: true,
  });

  const handleSearch = async () => {
    if (loading) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.discoverFiltered(buildRequest());
      setReport(res);
    } catch {
      setError("We couldn't complete the search right now. Please try again.");
      setReport(null);
    } finally {
      setLoading(false);
    }
  };

  const toggleSource = (name) => {
    setFilters((f) => ({
      ...f,
      sources: f.sources.includes(name)
        ? f.sources.filter((s) => s !== name)
        : [...f.sources, name],
    }));
  };

  const handleSaveSearch = async () => {
    const name = saveName.trim();
    if (!name) return;
    try {
      await api.createSavedSearch(name, buildRequest());
      setShowSaveInput(false);
      setSaveName("");
      notify("Search saved. You can re-run it any time.");
      await loadSavedSearches();
    } catch {
      notify("Failed to save the search.", "error");
    }
  };

  const handleRunSaved = async (id) => {
    try {
      const res = await api.runSavedSearch(id);
      setReport(res.report);
      const newCount = res.new_results || 0;
      notify(
        newCount > 0
          ? `${newCount} new result${newCount === 1 ? "" : "s"} since last run.`
          : "No new results since last run."
      );
      await loadSavedSearches();
    } catch {
      notify("Failed to run saved search.", "error");
    }
  };

  const handleDeleteSaved = async (id) => {
    try {
      await api.deleteSavedSearch(id);
      await loadSavedSearches();
      notify("Saved search deleted.");
    } catch {
      notify("Failed to delete saved search.", "error");
    }
  };

  const results = Array.isArray(report?.results) ? report.results : [];
  const duplicateCount = report?.duplicate_count || 0;

  return (
    <div className="discover-panel">
      {notification && (
        <div className={`toast toast-${notification.type}`} role="status">
          {notification.msg}
        </div>
      )}

      {/* Filter panel */}
      <section className="discover-filters card">
        <div className="discover-filters-title">
          <Search size={16} />
          <span>Filtered Job Search</span>
        </div>

        <div className="grid-2">
          <div className="form-group">
            <label className="form-label" htmlFor="disc-query">Job title / keyword</label>
            <input
              id="disc-query"
              type="text"
              className="form-input"
              placeholder="e.g. Backend Developer"
              value={filters.query}
              onChange={(e) => setFilters({ ...filters, query: e.target.value })}
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="disc-location">Location</label>
            <input
              id="disc-location"
              type="text"
              className="form-input"
              placeholder="e.g. Pune or Remote"
              value={filters.location}
              onChange={(e) => setFilters({ ...filters, location: e.target.value })}
            />
          </div>
        </div>

        <div className="grid-2">
          <div className="form-group">
            <label className="form-label" htmlFor="disc-mode">Work mode</label>
            <select
              id="disc-mode"
              className="form-select"
              value={filters.remote}
              onChange={(e) => setFilters({ ...filters, remote: e.target.value })}
            >
              {WORK_MODES.map((m) => (
                <option key={m} value={m}>{m === "" ? "Any" : m}</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="disc-posted">Posted</label>
            <select
              id="disc-posted"
              className="form-select"
              value={filters.posted}
              onChange={(e) => setFilters({ ...filters, posted: e.target.value })}
            >
              {POSTED_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid-2">
          <div className="form-group">
            <label className="form-label" htmlFor="disc-smin">Min salary (annual)</label>
            <input
              id="disc-smin"
              type="number"
              className="form-input"
              placeholder="e.g. 800000"
              value={filters.salary_min}
              onChange={(e) => setFilters({ ...filters, salary_min: e.target.value })}
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="disc-smax">Max salary (annual)</label>
            <input
              id="disc-smax"
              type="number"
              className="form-input"
              placeholder="e.g. 2500000"
              value={filters.salary_max}
              onChange={(e) => setFilters({ ...filters, salary_max: e.target.value })}
            />
          </div>
        </div>

        {availableSources.length > 0 && (
          <div className="discover-source-select">
            <span className="form-label">Sources</span>
            <div className="source-checkboxes">
              {availableSources.map((s) => (
                <label key={s} className="source-checkbox">
                  <input
                    type="checkbox"
                    checked={filters.sources.includes(s)}
                    onChange={() => toggleSource(s)}
                  />
                  <span>{s}</span>
                </label>
              ))}
              {filters.sources.length === 0 && (
                <span className="source-hint">All sources</span>
              )}
            </div>
          </div>
        )}

        <div className="discover-actions">
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleSearch}
            disabled={loading}
          >
            {loading ? (
              <>
                <span className="spinner-inline" />
                <span>Searching...</span>
              </>
            ) : (
              <>
                <Compass size={16} />
                <span>Search</span>
              </>
            )}
          </button>
          {hasActiveFilters && (
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => setFilters(DEFAULT_FILTERS)}
            >
              Reset
            </button>
          )}
        </div>
      </section>

      {/* Results summary + show summary stat */}
      {report && (
        <div className="discover-summary">
          <span>
            {report.unique_results} unique result{report.unique_results === 1 ? "" : "s"}
          </span>
          {duplicateCount > 0 && (
            <span className="discover-dup-note" title="Same listing seen from multiple providers, shown once">
              <Layers size={14} />
              {duplicateCount} duplicate{duplicateCount === 1 ? "" : "s"} merged across sources
            </span>
          )}
          {report.total_fetched > 0 && (
            <span className="discover-total-fetched">{report.total_fetched} fetched</span>
          )}
        </div>
      )}

      {error && (
        <div className="discovery-feedback-banner banner-error" role="alert">
          <div className="feedback-content">
            <span className="feedback-text">{error}</span>
          </div>
        </div>
      )}

      {!loading && report && results.length === 0 && (
        <EmptyState
          icon={Search}
          title="No results found"
          description="Try adjusting your filters or running the personalized discovery."
        />
      )}

      {/* Results */}
      {!loading && results.length > 0 && (
        <div className="jobs-list-stack">
          {results.map((job) => (
            <DiscoverCard key={job.canonical_key} job={job} />
          ))}
        </div>
      )}

      {/* Saved searches */}
      <section className="discover-saved card">
        <div className="discover-filters-title">
          <ListChecks size={16} />
          <span>Saved Searches</span>
        </div>

        {showSaveInput ? (
          <div className="discover-save-input">
            <input
              type="text"
              className="form-input"
              placeholder="Name this search (e.g. Remote backend roles)"
              value={saveName}
              onChange={(e) => setSaveName(e.target.value)}
              autoFocus
            />
            <button className="btn btn-primary btn-sm" onClick={handleSaveSearch} disabled={!saveName.trim()}>
              Save
            </button>
            <button className="btn btn-ghost btn-sm" onClick={() => { setShowSaveInput(false); setSaveName(""); }}>
              Cancel
            </button>
          </div>
        ) : (
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => setShowSaveInput(true)}
          >
            <Bookmark size={16} />
            <span>Save this search</span>
          </button>
        )}

        {savedSearches.length === 0 ? (
          <p className="discover-saved-empty text-muted">
            No saved searches yet. Save a search to re-run it later and see new results.
          </p>
        ) : (
          <ul className="discover-saved-list">
            {savedSearches.map((s) => (
              <li key={s.id} className="discover-saved-item">
                <div className="discover-saved-info">
                  <span className="discover-saved-name">{s.name}</span>
                  <span className="discover-saved-meta text-muted">
                    {s.last_seen_count > 0 ? `${s.last_seen_count} results tracked` : "Not run yet"}
                  </span>
                </div>
                <div className="discover-saved-actions">
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={() => handleRunSaved(s.id)}
                    title="Run now"
                  >
                    <Play size={14} />
                    <span>Run</span>
                  </button>
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={() => handleDeleteSaved(s.id)}
                    title="Delete"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function DiscoverCard({ job }) {
  const match = job.match;
  const score = match?.overall_score || 0;
  const reasons = match?.reasons || [];
  const isNew = match?.is_new;

  const [expanded, setExpanded] = useState(false);
  const primaryUrl = job.application_urls?.[0] || job.source_urls?.[0];

  return (
    <div className="card job-card-primary">
      <div className="job-card-main-content">
        <div className="job-card-header">
          <div className="job-card-title-wrap">
            <h2 className="job-card-title">{job.title}</h2>
            <div className="job-card-meta-line">
              <span className="company-name">{job.company}</span>
              {job.location && (
                <>
                  <span className="meta-sep">•</span>
                  <span className="location-name">{job.location}</span>
                </>
              )}
              {job.work_mode && job.work_mode !== "unspecified" && (
                <>
                  <span className="meta-sep">•</span>
                  <span>{job.work_mode}</span>
                </>
              )}
              {job.freshness && (
                <>
                  <span className="meta-sep">•</span>
                  <span className="freshness-label">
                    <Clock size={12} />
                    {job.freshness}
                  </span>
                </>
              )}
            </div>
          </div>

          <div className="job-card-score-col">
            <ScoreBadge score={score} />
            {isNew && <span className="new-badge">NEW</span>}
          </div>
        </div>

        {/* Source provenance */}
        {job.sources?.length > 0 && (
          <div className="discover-prov-row">
            <span className="discover-prov-label">From:</span>
            {job.sources.map((s) => (
              <span key={s} className="source-chip">{s}</span>
            ))}
            {job.sources.length > 1 && (
              <span className="discover-merged-note">(deduplicated)</span>
            )}
          </div>
        )}

        {/* Salary */}
        {job.salary && (job.salary.min != null || job.salary.max != null) && (
          <div className="job-card-meta-line salary-line">
            <span>
              {job.salary.min != null ? job.salary.min : ""}
              {job.salary.min != null && job.salary.max != null ? " - " : ""}
              {job.salary.max != null ? job.salary.max : ""}
              {job.salary.period ? ` ${job.salary.period}` : ""}
              {job.salary.currency ? ` ${job.salary.currency}` : ""}
            </span>
          </div>
        )}

        {/* Skills */}
        {job.skills?.length > 0 && (
          <div className="job-card-skills-row">
            {job.skills.slice(0, 6).map((sk) => (
              <span key={sk} className="skill-chip match">{sk}</span>
            ))}
            {job.skills.length > 6 && (
              <span className="skill-chip-more">+{job.skills.length - 6} more</span>
            )}
          </div>
        )}

        {/* Match reasons */}
        {match && reasons.length > 0 && (
          <div className="discover-reasons">
            <button
              type="button"
              className="discover-reasons-toggle"
              onClick={() => setExpanded((p) => !p)}
              aria-expanded={expanded}
            >
              <Sparkles size={14} />
              <span>Why this matches</span>
              {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>
            {expanded && (
              <ul className="discover-reasons-list">
                {reasons.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
                {match.matched_skills?.length > 0 && (
                  <li>Matched skills: {match.matched_skills.join(", ")}</li>
                )}
              </ul>
            )}
          </div>
        )}
      </div>

      <div className="job-card-action-bar">
        <span className="text-xs text-muted">
          {job.posted_at ? new Date(job.posted_at).toLocaleDateString() : "Recently active"}
        </span>
        <div className="job-card-buttons">
          {primaryUrl && (
            <a
              href={primaryUrl}
              target="_blank"
              rel="noreferrer"
              className="btn btn-secondary btn-sm"
            >
              <ExternalLink size={14} />
              <span>Apply</span>
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
