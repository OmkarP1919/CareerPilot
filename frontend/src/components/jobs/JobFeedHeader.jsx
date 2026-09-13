import { Sparkles, ArrowDownUp } from "lucide-react";

export default function JobFeedHeader({
  count = 0,
  hasProfileContext = false,
  sort = "match",
  onSortChange,
}) {
  return (
    <div className="job-feed-header">
      <div className="job-feed-header-left">
        <span className="job-feed-count">
          {count} {count === 1 ? "opportunity" : "opportunities"}
        </span>

        {hasProfileContext && (
          <span className="job-feed-ai-pill">
            <Sparkles size={12} className="ai-pill-icon" aria-hidden="true" />
            <span>Based on your profile</span>
          </span>
        )}
      </div>

      <div className="job-feed-header-right">
        <label htmlFor="job-sort-select" className="job-sort-label">
          <ArrowDownUp size={13} aria-hidden="true" />
          <span>Sort by:</span>
        </label>
        <select
          id="job-sort-select"
          className="job-sort-select"
          value={sort}
          onChange={(e) => onSortChange?.(e.target.value)}
          aria-label="Sort job opportunities"
        >
          <option value="match">Best Match</option>
          <option value="newest">Newest</option>
        </select>
      </div>
    </div>
  );
}
