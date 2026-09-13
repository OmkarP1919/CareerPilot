import { useState, useEffect } from "react";
import { Search, X, Loader2 } from "lucide-react";

export default function JobSearchBar({
  query = "",
  onSearch,
  onClear,
  loading = false,
  placeholder = "Search jobs, skills, or companies...",
}) {
  const [draft, setDraft] = useState(query);

  // Synchronize draft when committed query changes externally (e.g. Back/Forward/Clear)
  useEffect(() => {
    setDraft(query || "");
  }, [query]);

  const handleSubmit = (e) => {
    e.preventDefault();
    onSearch?.(draft.trim());
  };

  const handleClear = () => {
    setDraft("");
    onClear?.();
  };

  return (
    <form
      role="search"
      className="job-search-bar"
      onSubmit={handleSubmit}
      aria-label="Job search"
    >
      <div className="job-search-input-wrap">
        <Search size={18} className="job-search-icon" aria-hidden="true" />
        <input
          id="unified-job-search-input"
          type="text"
          className="job-search-input"
          placeholder={placeholder}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          autoComplete="off"
          spellCheck="false"
          aria-label="Search jobs by title, skill, company, or intent"
        />
        {draft && (
          <button
            type="button"
            className="job-search-clear-btn"
            onClick={handleClear}
            aria-label="Clear search input"
            title="Clear search"
          >
            <X size={16} />
          </button>
        )}
      </div>
      <button
        type="submit"
        className="btn btn-primary job-search-submit-btn"
        disabled={loading}
        aria-label={loading ? "Searching..." : "Search"}
      >
        {loading ? (
          <>
            <Loader2 size={16} className="spinner-inline" />
            <span>Searching...</span>
          </>
        ) : (
          <span>Search</span>
        )}
      </button>
    </form>
  );
}
