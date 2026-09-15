/**
 * Formats salary data into a clean, human-readable string without fabricating values.
 * Returns null if no authentic salary numbers exist.
 */
export function formatSalary(salary) {
  if (!salary || (salary.min == null && salary.max == null)) return null;

  const min = salary.min != null ? Number(salary.min) : null;
  const max = salary.max != null ? Number(salary.max) : null;
  if ((min != null && isNaN(min)) || (max != null && isNaN(max))) return null;

  const currency = salary.currency || "";
  const period = salary.period ? ` / ${salary.period === "annual" ? "yr" : salary.period}` : "";

  const fmtNum = (val) => {
    if (val == null) return "";
    // Indian Lakh format if currency is INR or value >= 100000 with no currency specified
    if (currency === "INR" || (!currency && val >= 100000)) {
      const lakhs = val / 100000;
      return `₹${lakhs % 1 === 0 ? lakhs : lakhs.toFixed(1)}L`;
    }
    // USD format
    if (currency === "USD" || currency === "$") {
      return `$${val >= 1000 ? `${Math.round(val / 1000)}k` : val.toLocaleString()}`;
    }
    // General formatted number
    return `${currency ? `${currency} ` : ""}${val.toLocaleString()}`;
  };

  if (min != null && max != null) {
    if (min === max) {
      return `${fmtNum(min)}${period}`;
    }
    return `${fmtNum(min)} – ${fmtNum(max)}${period}`;
  }
  if (min != null) {
    return `From ${fmtNum(min)}${period}`;
  }
  return `Up to ${fmtNum(max)}${period}`;
}

/**
 * Calculates ISO timestamp string for jobs posted within the last X days.
 */
export function postedAfterDays(days) {
  if (!days) return null;
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - Number(days));
  return d.toISOString();
}

// Canonical backend vocabulary mirrors the discovery pipeline enums, NOT the
// human-readable UI labels. Employment-type canonical values (lowercase,
// hyphenated) come from pipeline.EMPLOYMENT_TYPES; experience-level canonical
// values come from pipeline.EXPERIENCE_LEVELS.
const EMPLOYMENT_TYPE_CANONICAL = {
  "Full-time": "full-time",
  "Part-time": "part-time",
  "Contract": "contract",
  "Internship": "internship",
  "Freelance": "freelance",
};

const EXPERIENCE_LEVEL_CANONICAL = {
  "Entry Level": "entry",
  "Mid Level": "mid",
  "Senior Level": "senior",
  "Lead": "lead",
  "Executive": "executive",
};

/**
 * Maps a UI employment-type label to the canonical backend value.
 * Returns null when the label is not a recognized option (never guessed).
 */
export function toCanonicalEmploymentType(value) {
  return EMPLOYMENT_TYPE_CANONICAL[value] || null;
}

/**
 * Maps a UI experience-level label to the canonical backend value.
 * Returns null when the label is not a recognized option (never guessed).
 */
export function toCanonicalExperienceLevel(value) {
  return EXPERIENCE_LEVEL_CANONICAL[value] || null;
}

/**
 * Normalizes any raw work mode or location string to a canonical internal value:
 * 'remote' | 'hybrid' | 'onsite' | 'unspecified'
 */
export function normalizeWorkMode(rawVal, location = "") {
  const val = (rawVal != null ? String(rawVal) : "").trim().toLowerCase();
  if (val === "remote" || val === "true") return "remote";
  if (val === "hybrid") return "hybrid";
  if (val === "onsite" || val === "on-site" || val === "in-office" || val === "office" || val === "false") return "onsite";
  if (val === "unspecified") return "unspecified";

  const loc = (location || "").toString().trim().toLowerCase();
  if (loc.includes("remote")) return "remote";
  if (loc.includes("hybrid")) return "hybrid";
  if (loc.includes("onsite") || loc.includes("on-site") || loc.includes("in-office")) return "onsite";

  return "unspecified";
}

/**
 * Returns a user-friendly display label for a work mode:
 * 'Remote' | 'Hybrid' | 'Onsite' | ''
 */
export function formatWorkMode(workMode) {
  const canonical = normalizeWorkMode(workMode);
  switch (canonical) {
    case "remote":
      return "Remote";
    case "hybrid":
      return "Hybrid";
    case "onsite":
      return "Onsite";
    default:
      return "";
  }
}

/**
 * Builds discovery filtered search request payload from filter criteria.
 *
 * employment_type / experience_level are sent in canonical backend form so the
 * pipeline performs the authoritative filtering. `remote` is a best-effort
 * superset hint (Remote/Hybrid -> true, Onsite -> false); exact work-mode
 * filtering happens on the client after retrieval using the hit `work_mode`.
 */
export function buildDiscoveryPayload(criteria = {}) {
  const query = (criteria.query || criteria.q || "").trim();
  const location = (criteria.location || "").trim();

  const employmentType = toCanonicalEmploymentType(criteria.type);
  const experienceLevel = toCanonicalExperienceLevel(criteria.level);

  const rawRemote = (criteria.remote || "").toString().trim().toLowerCase();
  const isRemote = rawRemote === "remote" || rawRemote === "true";
  const isHybrid = rawRemote === "hybrid";
  const isOnsite = rawRemote === "onsite" || rawRemote === "false";

  const payload = {
    queries: query ? [query] : [],
    locations: location ? [location] : [],
    remote:
      isRemote || isHybrid
        ? true
        : isOnsite
        ? false
        : null,
    salary_min: criteria.smin ? Number(criteria.smin) : criteria.salary_min ? Number(criteria.salary_min) : null,
    salary_max: criteria.smax ? Number(criteria.smax) : criteria.salary_max ? Number(criteria.salary_max) : null,
    salary_period: "annual",
    posted_after: postedAfterDays(criteria.posted),
    sort: criteria.sort === "newest" ? "newest" : "relevance",
    sources: Array.isArray(criteria.sources) ? criteria.sources : [],
    page_size: 30,
    include_profile_alignment: true,
  };
  if (employmentType) payload.employment_type = employmentType;
  if (experienceLevel) payload.experience_level = experienceLevel;
  return payload;
}

/**
 * Normalizes both local database jobs and external discovery hits into ONE canonical Job shape.
 * NEVER fabricates match scores, fit text, or salaries.
 */
export function normalizeJob(item, sessionCache = new Map()) {
  if (!item) return null;

  // Case 1: External Discovery Hit
  if (item.canonical_key) {
    const localId = item.id || sessionCache.get?.(item.canonical_key) || null;
    const match = item.match || null;

    // Match score ONLY if real positive number from API
    let score = null;
    if (match && typeof match.overall_score === "number" && match.overall_score > 0) {
      score = match.overall_score;
    } else if (typeof item.match_score === "number" && item.match_score > 0) {
      score = item.match_score;
    }

    // Fit summary ONLY if genuine reasons or alignment data exist
    let fitSummary = null;
    if (match?.reasons && Array.isArray(match.reasons) && match.reasons.length > 0) {
      fitSummary = match.reasons[0];
    } else if (score && score >= 70) {
      fitSummary = "Strong alignment with your profile and skills";
    }

    const primaryUrl = item.application_urls?.[0] || item.source_urls?.[0] || item.application_url || null;

    return {
      id: localId,
      canonical_key: item.canonical_key,
      title: item.title || "Untitled Role",
      company: item.company || "Company",
      location: item.location || "",
      work_mode: normalizeWorkMode(item.work_mode, item.location),
      employment_type: item.employment_type || "",
      experience_level: item.experience_level || "",
      description: item.description || "",
      salary: formatSalary(item.salary),
      raw_salary: item.salary || null,
      skills: Array.isArray(item.skills) ? item.skills : [],
      match_score: score,
      fit_summary: fitSummary,
      source: item.primary_source || item.sources?.[0] || item.source || "Discovery",
      sources: Array.isArray(item.sources) ? item.sources : [],
      application_url: primaryUrl,
      posted_at: item.posted_at || item.first_seen_at || null,
      freshness: item.freshness || null,
      is_external: !localId,
    };
  }

  // Case 2: Local Job (from /jobs/ or /jobs/recommended)
  const jobObj = item.job ? item.job : item;
  const localId = jobObj.id;

  let score = null;
  if (typeof item.match_score === "number" && item.match_score > 0) {
    score = item.match_score;
  } else if (typeof jobObj.match_score === "number" && jobObj.match_score > 0) {
    score = jobObj.match_score;
  }

  let skills = [];
  if (Array.isArray(item.matched_skills) && item.matched_skills.length > 0) {
    skills = item.matched_skills;
  } else if (Array.isArray(jobObj.required_skills)) {
    skills = jobObj.required_skills;
  } else if (typeof jobObj.required_skills === "string") {
    skills = jobObj.required_skills.split(",").map((s) => s.trim()).filter(Boolean);
  }

  let fitSummary = null;
  if (item.explanation) {
    fitSummary = item.explanation;
  } else if (score && score >= 70) {
    fitSummary = "Strong alignment with your profile and skills";
  }

  return {
    id: localId,
    canonical_key: jobObj.canonical_key || `local-${localId}`,
    title: jobObj.title || "Untitled Role",
    company: jobObj.company || "Company",
    location: jobObj.location || "",
    work_mode: normalizeWorkMode(jobObj.work_mode, jobObj.location),
    employment_type: jobObj.employment_type || "",
    experience_level: jobObj.experience_level || "",
    description: jobObj.description || "",
    salary: null,
    raw_salary: null,
    skills,
    match_score: score,
    fit_summary: fitSummary,
    source: jobObj.source || "Direct",
    sources: jobObj.source ? [jobObj.source] : [],
    application_url: jobObj.application_url || null,
    posted_at: jobObj.created_at || jobObj.posted_at || null,
    freshness: null,
    is_external: false,
  };
}
