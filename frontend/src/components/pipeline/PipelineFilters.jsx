import { Search, X, ArrowUpDown } from "lucide-react";
import { FILTER_TABS, STATUS_GROUPS } from "./pipelineUtils";

export default function PipelineFilters({
  applications = [],
  activeTab = "all",
  onSelectTab,
  searchQuery = "",
  onSearchChange,
  sortKey = "recent",
  onSortChange,
}) {
  // Compute badge counts for tabs
  const getTabCount = (tabId) => {
    if (tabId === "all") return applications.length;
    if (tabId === "active") {
      return applications.filter((a) => STATUS_GROUPS.Active.includes(a.status || "Saved")).length;
    }
    if (tabId === "interview") {
      return applications.filter((a) => (a.status || "Saved") === "Interview").length;
    }
    if (tabId === "offer") {
      return applications.filter((a) => (a.status || "Saved") === "Offer").length;
    }
    if (tabId === "saved") {
      return applications.filter((a) => (a.status || "Saved") === "Saved").length;
    }
    if (tabId === "archived") {
      return applications.filter((a) => STATUS_GROUPS.Archived.includes(a.status || "Saved")).length;
    }
    return 0;
  };

  return (
    <div className="pipeline-controls-panel" aria-label="Pipeline search and stage filters">
      <div className="pipeline-search-sort-row">
        {/* Search Bar */}
        <div className="pipeline-search-input-wrap">
          <Search size={16} className="pipeline-search-icon" aria-hidden="true" />
          <input
            type="search"
            className="pipeline-search-input"
            placeholder="Search by company, role, location, or notes..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            aria-label="Search applications"
          />
          {searchQuery && (
            <button
              type="button"
              className="pipeline-search-clear"
              onClick={() => onSearchChange("")}
              aria-label="Clear search input"
            >
              <X size={14} aria-hidden="true" />
            </button>
          )}
        </div>

        {/* Sort Dropdown */}
        <div className="pipeline-sort-wrap">
          <ArrowUpDown size={14} className="pipeline-sort-icon" aria-hidden="true" />
          <label htmlFor="pipeline-sort-select" className="sr-only">
            Sort applications by
          </label>
          <select
            id="pipeline-sort-select"
            className="pipeline-sort-select"
            value={sortKey}
            onChange={(e) => onSortChange(e.target.value)}
            aria-label="Sort applications"
          >
            <option value="recent">Recently Updated</option>
            <option value="applied_date">Applied Date</option>
            <option value="company_asc">Company (A–Z)</option>
            <option value="match_score">Match Score (where available)</option>
          </select>
        </div>
      </div>

      {/* Segmented Stage Filter Chips */}
      <div className="pipeline-stage-tabs-row" role="tablist" aria-label="Filter applications by stage">
        {FILTER_TABS.map((tab) => {
          const isSelected = activeTab === tab.id;
          const count = getTabCount(tab.id);

          return (
            <button
              key={tab.id}
              type="button"
              className={`pipeline-stage-chip ${isSelected ? "active" : ""}`}
              onClick={() => onSelectTab(tab.id)}
              role="tab"
              aria-selected={isSelected}
              aria-controls="pipeline-applications-list"
            >
              <span>{tab.label}</span>
              <span className="pipeline-chip-count font-mono">{count}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
