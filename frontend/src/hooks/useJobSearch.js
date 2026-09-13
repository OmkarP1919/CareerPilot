import { useState, useCallback, useEffect, useRef } from "react";
import { api } from "../services/api";
import { buildDiscoveryPayload } from "../components/jobs/jobUtils";

export const DEFAULT_FILTERS = {
  query: "",
  location: "",
  remote: "",
  type: "",
  level: "",
  salary_min: "",
  salary_max: "",
  posted: "",
  sources: [],
};

export function useJobSearch() {
  const [availableSources, setAvailableSources] = useState([]);
  const [savedSearches, setSavedSearches] = useState([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchReport, setSearchReport] = useState(null);
  const [searchError, setSearchError] = useState(null);

  // Request cancellation / race prevention
  const activeRequestRef = useRef(0);

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

  const executeSearch = useCallback(async (criteria = {}) => {
    const requestId = ++activeRequestRef.current;
    setSearchLoading(true);
    setSearchError(null);

    try {
      const payload = buildDiscoveryPayload(criteria);
      const res = await api.discoverFiltered(payload);

      // Prevent race conditions: ignore response if a newer request was dispatched
      if (requestId === activeRequestRef.current) {
        setSearchReport(res);
        return res;
      }
      return null;
    } catch (err) {
      if (requestId === activeRequestRef.current) {
        const msg = "We couldn't complete the search right now. Please try again.";
        setSearchError(msg);
        setSearchReport(null);
        throw err;
      }
      return null;
    } finally {
      if (requestId === activeRequestRef.current) {
        setSearchLoading(false);
      }
    }
  }, []);

  const handleSaveSearch = useCallback(
    async (name, criteria = {}) => {
      const trimmedName = (name || "").trim();
      if (!trimmedName) return false;
      try {
        const payload = buildDiscoveryPayload(criteria);
        await api.createSavedSearch(trimmedName, payload);
        await loadSavedSearches();
        return true;
      } catch {
        return false;
      }
    },
    [loadSavedSearches]
  );

  const handleRunSaved = useCallback(
    async (id) => {
      try {
        const res = await api.runSavedSearch(id);
        setSearchReport(res.report);
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

  return {
    availableSources,
    savedSearches,
    searchLoading,
    searchReport,
    setSearchReport,
    searchError,
    setSearchError,
    executeSearch,
    handleSaveSearch,
    handleRunSaved,
    handleDeleteSaved,
    loadSavedSearches,
  };
}
