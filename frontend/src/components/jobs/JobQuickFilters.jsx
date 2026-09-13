import { SlidersHorizontal, RotateCcw, Check } from "lucide-react";

export default function JobQuickFilters({
  filters = {},
  onFilterChange,
  onOpenAllFilters,
  activeFilterCount = 0,
  onResetAll,
}) {
  const isRemote = filters.remote === "Remote";
  const isFullTime = filters.type === "Full-time";
  const hasSalary = Boolean(filters.smin || filters.smax);
  const activeLevel = filters.level || "";

  const toggleRemote = () => {
    onFilterChange?.("remote", isRemote ? "" : "Remote");
  };

  const toggleFullTime = () => {
    onFilterChange?.("type", isFullTime ? "" : "Full-time");
  };

  return (
    <div className="job-quick-filters-bar" role="toolbar" aria-label="Quick filters">
      <div className="job-quick-filters-scroll">
        {/* Remote toggle chip */}
        <button
          type="button"
          className={`quick-filter-chip ${isRemote ? "active" : ""}`}
          onClick={toggleRemote}
          aria-pressed={isRemote}
          aria-label="Filter by Remote work"
        >
          {isRemote && <Check size={13} className="chip-check-icon" />}
          <span>Remote</span>
        </button>

        {/* Full-time toggle chip */}
        <button
          type="button"
          className={`quick-filter-chip ${isFullTime ? "active" : ""}`}
          onClick={toggleFullTime}
          aria-pressed={isFullTime}
          aria-label="Filter by Full-time roles"
        >
          {isFullTime && <Check size={13} className="chip-check-icon" />}
          <span>{filters.type && !isFullTime ? filters.type : "Full-time"}</span>
        </button>

        {/* Experience chip: opens drawer or displays active level */}
        <button
          type="button"
          className={`quick-filter-chip ${activeLevel ? "active" : ""}`}
          onClick={onOpenAllFilters}
          aria-label={activeLevel ? `Experience level: ${activeLevel}` : "Filter by experience level"}
        >
          {activeLevel && <Check size={13} className="chip-check-icon" />}
          <span>{activeLevel || "Experience"}</span>
        </button>

        {/* Salary chip */}
        <button
          type="button"
          className={`quick-filter-chip ${hasSalary ? "active" : ""}`}
          onClick={onOpenAllFilters}
          aria-label="Filter by salary"
        >
          {hasSalary && <Check size={13} className="chip-check-icon" />}
          <span>{hasSalary ? "Salary Filtered" : "Salary"}</span>
        </button>

        {/* More Filters button */}
        <button
          type="button"
          className={`quick-filter-chip all-filters-chip ${activeFilterCount > 0 ? "has-active" : ""}`}
          onClick={onOpenAllFilters}
          aria-label={`All filters (${activeFilterCount} active)`}
        >
          <SlidersHorizontal size={14} />
          <span>All Filters</span>
          {activeFilterCount > 0 && (
            <span className="quick-filter-badge">{activeFilterCount}</span>
          )}
        </button>

        {/* Reset all button when filters active */}
        {activeFilterCount > 0 && (
          <button
            type="button"
            className="quick-filter-reset-btn"
            onClick={onResetAll}
            title="Reset all filters"
            aria-label="Reset all filters"
          >
            <RotateCcw size={13} />
            <span>Reset</span>
          </button>
        )}
      </div>
    </div>
  );
}
