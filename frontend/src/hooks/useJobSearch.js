import { useState, useCallback, useEffect, useMemo } from "react";
import { api } from "../services/api";
import { DEFAULT_FILTERS, postedAfterDays } from "../components/DiscoverPanel";

export function useJobSearch() {
  const [discoverFilters, setDiscoverFilters] = useState(DEFAULT_FILTERS);
  const [availableSources, setAvailableSources] = useState([]);
  const [discoverLoading, setDiscoverLoading] = useState(false);
  const [discoverReport, setDiscoverReport] = useState(null);
  const [discoverError, setDiscoverError] = useState(null);
  const [savedSearches, setSavedSearches] = useState([]);
  const [saveName, setSaveName] = useState("");
  const [showSaveInput, setShowSaveInput] = useState(false);

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

  const hasActiveDiscoverFilters = useMemo(() => {
    return Boolean(
      discoverFilters.location ||
      discoverFilters.remote ||
      discoverFilters.salary_min ||
      discoverFilters.salary_max ||
      discoverFilters.posted ||
      discoverFilters.sources.length > 0
    );
  }, [discoverFilters]);

  const buildRequest = useCallback((queryOverride) => {
    const effectiveQuery = (queryOverride !== undefined ? queryOverride : discoverFilters.query).trim();
    return {
      queries: effectiveQuery ? [effectiveQuery] : [],
      locations: discoverFilters.location ? [discoverFilters.location.trim()] : [],
      remote:
        discoverFilters.remote === "Remote"
          ? true
          : discoverFilters.remote === "Onsite"
          ? false
          : null,
      salary_min: discoverFilters.salary_min ? Number(discoverFilters.salary_min) : null,
      salary_max: discoverFilters.salary_max ? Number(discoverFilters.salary_max) : null,
      salary_period: "annual",
      posted_after: postedAfterDays(discoverFilters.posted),
      sort: "newest",
      sources: discoverFilters.sources,
      page_size: 30,
      include_profile_alignment: true,
    };
  }, [discoverFilters]);

  const handleExternalSearch = useCallback(
    async (queryOverride) => {
      if (discoverLoading) return null;
      setDiscoverLoading(true);
      setDiscoverError(null);
      try {
        const payload = buildRequest(queryOverride);
        const res = await api.discoverFiltered(payload);
        setDiscoverReport(res);
        return res;
      } catch (err) {
        const msg = "We couldn't complete the search right now. Please try again.";
        setDiscoverError(msg);
        setDiscoverReport(null);
        throw err;
      } finally {
        setDiscoverLoading(false);
      }
    },
    [discoverLoading, buildRequest]
  );

  const toggleSource = useCallback((name) => {
    setDiscoverFilters((f) => ({
      ...f,
      sources: f.sources.includes(name)
        ? f.sources.filter((s) => s !== name)
        : [...f.sources, name],
    }));
  }, []);

  const handleSaveSearch = useCallback(
    async (queryOverride) => {
      const name = saveName.trim();
      if (!name) return false;
      try {
        await api.createSavedSearch(name, buildRequest(queryOverride));
        setShowSaveInput(false);
        setSaveName("");
        await loadSavedSearches();
        return true;
      } catch {
        return false;
      }
    },
    [saveName, buildRequest, loadSavedSearches]
  );

  const handleRunSaved = useCallback(
    async (id) => {
      try {
        const res = await api.runSavedSearch(id);
        setDiscoverReport(res.report);
        await loadSavedSearches();
        return res;
      } catch (err) {
        throw err;
      }
    },
    [loadSavedSearches]
  );

  const handleDeleteSaved = useCallback(
    async (id) => {
      try {
        await api.deleteSavedSearch(id);
        await loadSavedSearches();
        return true;
      } catch {
        return false;
      }
    },
    [loadSavedSearches]
  );

  const resetDiscoverFilters = useCallback(() => {
    setDiscoverFilters(DEFAULT_FILTERS);
  }, []);

  return {
    discoverFilters,
    setDiscoverFilters,
    availableSources,
    discoverLoading,
    discoverReport,
    setDiscoverReport,
    discoverError,
    setDiscoverError,
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
    loadSavedSearches,
  };
}
