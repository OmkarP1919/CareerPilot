import { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { X, Bookmark, ListChecks, Play, Trash2, SlidersHorizontal, ChevronDown, ChevronUp } from "lucide-react";

export const WORK_MODES = ["", "Remote", "Hybrid", "Onsite"];
export const EMPLOYMENT_TYPES = ["Full-time", "Part-time", "Contract", "Internship", "Freelance"];
export const EXPERIENCE_LEVELS = ["Entry Level", "Mid Level", "Senior Level", "Lead", "Executive"];
export const POSTED_OPTIONS = [
  { value: "", label: "Any time" },
  { value: "7", label: "Past week" },
  { value: "14", label: "Past 2 weeks" },
  { value: "30", label: "Past month" },
];

export default function JobFilterDrawer({
  isOpen,
  onClose,
  filters = {},
  onApply,
  onReset,
  availableSources = [],
  savedSearches = [],
  onSaveSearch,
  onRunSavedSearch,
  onDeleteSavedSearch,
}) {
  const [draft, setDraft] = useState({ ...filters });
  const [showSavedSection, setShowSavedSection] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [showSaveInput, setShowSaveInput] = useState(false);
  const [savingSearch, setSavingSearch] = useState(false);
  const drawerRef = useRef(null);

  // Synchronize draft whenever drawer opens or external filters change
  useEffect(() => {
    if (isOpen) {
      setDraft({
        location: filters.location || "",
        remote: filters.remote || "",
        type: filters.type || "",
        level: filters.level || "",
        posted: filters.posted || "",
        smin: filters.smin || "",
        smax: filters.smax || "",
        sources: Array.isArray(filters.sources) ? [...filters.sources] : [],
      });
    }
  }, [isOpen, filters]);

  // Handle ESC key to close drawer
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e) => {
      if (e.key === "Escape") {
        onClose?.();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  // Lock body scroll on mobile bottom sheet when open
  useEffect(() => {
    if (isOpen && window.innerWidth <= 768) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const toggleSource = (sourceName) => {
    setDraft((prev) => {
      const cur = prev.sources || [];
      const updated = cur.includes(sourceName)
        ? cur.filter((s) => s !== sourceName)
        : [...cur, sourceName];
      return { ...prev, sources: updated };
    });
  };

  const handleApply = (e) => {
    e?.preventDefault();
    onApply?.(draft);
    onClose?.();
  };

  const handleResetDraft = () => {
    const emptyFilters = {
      location: "",
      remote: "",
      type: "",
      level: "",
      posted: "",
      smin: "",
      smax: "",
      sources: [],
    };
    setDraft(emptyFilters);
    onReset?.();
  };

  const handleSaveSearchClick = async () => {
    const name = saveName.trim();
    if (!name || savingSearch) return;
    setSavingSearch(true);
    try {
      const ok = await onSaveSearch?.(name, draft);
      if (ok) {
        setSaveName("");
        setShowSaveInput(false);
      }
    } finally {
      setSavingSearch(false);
    }
  };

  const drawerContent = (
    <div
      className="jobs-filter-drawer-backdrop"
      onClick={onClose}
      role="presentation"
    >
      <aside
        ref={drawerRef}
        className="jobs-filter-drawer"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Filter jobs"
      >
        {/* Mobile handle */}
        <div className="drawer-handle" aria-hidden="true" />

        {/* Header */}
        <div className="drawer-header">
          <div className="drawer-header-title-wrap">
            <SlidersHorizontal size={18} className="drawer-title-icon" aria-hidden="true" />
            <h2 className="drawer-title">All Filters</h2>
          </div>
          <div className="drawer-header-actions">
            <button
              type="button"
              className="btn btn-ghost btn-sm drawer-reset-btn"
              onClick={handleResetDraft}
            >
              Reset all
            </button>
            <button
              type="button"
              className="btn btn-ghost btn-icon btn-sm drawer-close-btn"
              onClick={onClose}
              aria-label="Close filters"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Scrollable Body */}
        <form className="drawer-body" onSubmit={handleApply}>
          {/* Location */}
          <div className="form-group">
            <label className="form-label" htmlFor="filter-location">
              Location
            </label>
            <input
              id="filter-location"
              type="text"
              className="form-input"
              placeholder="e.g. Pune, Bengaluru, or Remote"
              value={draft.location}
              onChange={(e) => setDraft({ ...draft, location: e.target.value })}
            />
          </div>

          {/* Work Mode & Date Posted */}
          <div className="drawer-grid-2">
            <div className="form-group">
              <label className="form-label" htmlFor="filter-workmode">
                Work Mode
              </label>
              <select
                id="filter-workmode"
                className="form-select"
                value={draft.remote}
                onChange={(e) => setDraft({ ...draft, remote: e.target.value })}
              >
                <option value="">Any Work Mode</option>
                <option value="Remote">Remote</option>
                <option value="Hybrid">Hybrid</option>
                <option value="Onsite">Onsite</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="filter-posted">
                Date Posted
              </label>
              <select
                id="filter-posted"
                className="form-select"
                value={draft.posted}
                onChange={(e) => setDraft({ ...draft, posted: e.target.value })}
              >
                {POSTED_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Employment Type & Experience Level */}
          <div className="drawer-grid-2">
            <div className="form-group">
              <label className="form-label" htmlFor="filter-type">
                Employment Type
              </label>
              <select
                id="filter-type"
                className="form-select"
                value={draft.type}
                onChange={(e) => setDraft({ ...draft, type: e.target.value })}
              >
                <option value="">All Types</option>
                {EMPLOYMENT_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="filter-level">
                Experience Level
              </label>
              <select
                id="filter-level"
                className="form-select"
                value={draft.level}
                onChange={(e) => setDraft({ ...draft, level: e.target.value })}
              >
                <option value="">All Levels</option>
                {EXPERIENCE_LEVELS.map((lvl) => (
                  <option key={lvl} value={lvl}>
                    {lvl}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Collapsible: Advanced Filters & Salary */}
          <div className="drawer-accordion">
            <button
              type="button"
              className="drawer-accordion-trigger"
              onClick={() => setShowAdvanced((p) => !p)}
              aria-expanded={showAdvanced}
            >
              <span>Salary & Sources</span>
              {showAdvanced ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>

            {showAdvanced && (
              <div className="drawer-accordion-content">
                {/* Salary Range */}
                <div className="drawer-grid-2">
                  <div className="form-group">
                    <label className="form-label" htmlFor="filter-smin">
                      Min Salary (annual)
                    </label>
                    <input
                      id="filter-smin"
                      type="number"
                      className="form-input"
                      placeholder="e.g. 1000000"
                      value={draft.smin}
                      onChange={(e) => setDraft({ ...draft, smin: e.target.value })}
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label" htmlFor="filter-smax">
                      Max Salary (annual)
                    </label>
                    <input
                      id="filter-smax"
                      type="number"
                      className="form-input"
                      placeholder="e.g. 3000000"
                      value={draft.smax}
                      onChange={(e) => setDraft({ ...draft, smax: e.target.value })}
                    />
                  </div>
                </div>

                {/* Job Sources */}
                {availableSources.length > 0 && (
                  <div className="drawer-sources-box">
                    <span className="form-label">Job Sources</span>
                    <div className="source-checkboxes">
                      {availableSources.map((sourceName) => (
                        <label key={sourceName} className="source-checkbox">
                          <input
                            type="checkbox"
                            checked={draft.sources?.includes(sourceName)}
                            onChange={() => toggleSource(sourceName)}
                          />
                          <span>{sourceName}</span>
                        </label>
                      ))}
                    </div>
                    {(!draft.sources || draft.sources.length === 0) && (
                      <span className="source-hint">All sources included</span>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Collapsible: Saved Searches */}
          <div className="drawer-accordion">
            <button
              type="button"
              className="drawer-accordion-trigger"
              onClick={() => setShowSavedSection((p) => !p)}
              aria-expanded={showSavedSection}
            >
              <span className="accordion-label-wrap">
                <ListChecks size={16} />
                <span>Saved Searches</span>
                {savedSearches.length > 0 && (
                  <span className="drawer-count-badge">{savedSearches.length}</span>
                )}
              </span>
              {showSavedSection ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>

            {showSavedSection && (
              <div className="drawer-accordion-content">
                {showSaveInput ? (
                  <div className="drawer-save-input-row">
                    <input
                      type="text"
                      className="form-input"
                      placeholder="Name this search (e.g. Remote Backend)"
                      value={saveName}
                      onChange={(e) => setSaveName(e.target.value)}
                      autoFocus
                    />
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={handleSaveSearchClick}
                      disabled={!saveName.trim() || savingSearch}
                    >
                      {savingSearch ? "Saving..." : "Save"}
                    </button>
                    <button
                      type="button"
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
                    className="btn btn-secondary btn-sm drawer-save-trigger-btn"
                    onClick={() => setShowSaveInput(true)}
                  >
                    <Bookmark size={14} />
                    <span>Save current filter criteria</span>
                  </button>
                )}

                {savedSearches.length === 0 ? (
                  <p className="drawer-empty-hint">
                    No saved searches yet. Save your favorite criteria to run anytime.
                  </p>
                ) : (
                  <ul className="drawer-saved-list">
                    {savedSearches.map((s) => (
                      <li key={s.id} className="drawer-saved-item">
                        <div className="drawer-saved-info">
                          <span className="drawer-saved-name">{s.name}</span>
                          <span className="drawer-saved-meta">
                            {s.last_seen_count > 0
                              ? `${s.last_seen_count} tracked`
                              : "Saved"}
                          </span>
                        </div>
                        <div className="drawer-saved-actions">
                          <button
                            type="button"
                            className="btn btn-ghost btn-sm btn-icon"
                            onClick={() => {
                              onRunSavedSearch?.(s);
                              onClose?.();
                            }}
                            title="Run saved search"
                            aria-label={`Run search: ${s.name}`}
                          >
                            <Play size={14} />
                          </button>
                          <button
                            type="button"
                            className="btn btn-ghost btn-sm btn-icon"
                            onClick={() => onDeleteSavedSearch?.(s.id)}
                            title="Delete saved search"
                            aria-label={`Delete search: ${s.name}`}
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        </form>

        {/* Footer Actions */}
        <div className="drawer-footer">
          <button
            type="button"
            className="btn btn-primary btn-block drawer-apply-btn"
            onClick={handleApply}
          >
            Apply Filters
          </button>
        </div>
      </aside>
    </div>
  );

  if (typeof document === "undefined") {
    return drawerContent;
  }

  return createPortal(drawerContent, document.body);
}
