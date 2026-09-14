/**
 * Phase 7.0C.3 Resume Tailoring Curation Utilities
 * Deterministic matching and intelligent defaults without heuristics.
 */

export function normalizeMatchStr(str) {
  return typeof str === "string" ? str.trim().toLowerCase() : "";
}

/**
 * Deterministically match an experience against existing matchData.relevant_experience objects.
 * Compares actual object fields (job_title, company) with safe normalization.
 * NO heuristics (skills, description, technologies, or title keywords).
 */
export function isExperienceMatched(exp, matchData) {
  if (!exp || !Array.isArray(matchData?.relevant_experience) || matchData.relevant_experience.length === 0) {
    return false;
  }
  const expTitle = normalizeMatchStr(exp.role || exp.title || exp.job_title || exp.position);
  const expComp = normalizeMatchStr(exp.company || exp.employer);

  return matchData.relevant_experience.some((re) => {
    if (!re || typeof re !== "object") return false;
    const reTitle = normalizeMatchStr(re.job_title || re.title || re.role);
    const reComp = normalizeMatchStr(re.company || re.employer);

    // If both title and company are provided on match object, require both to match (if present on exp)
    if (reTitle && reComp) {
      if (expTitle && expComp) {
        return expTitle === reTitle && expComp === reComp;
      }
      return (expTitle && expTitle === reTitle) || (expComp && expComp === reComp);
    }
    if (reTitle && expTitle) {
      return expTitle === reTitle;
    }
    if (reComp && expComp) {
      return expComp === reComp;
    }
    return false;
  });
}

/**
 * Deterministically match a project against existing matchData.relevant_projects objects.
 * Compares rp.name with proj.name using safe normalization.
 * NO heuristics (skills, description, technologies).
 */
export function isProjectMatched(proj, matchData) {
  if (!proj || !Array.isArray(matchData?.relevant_projects) || matchData.relevant_projects.length === 0) {
    return false;
  }
  const projName = normalizeMatchStr(proj.name || proj.title || proj.project_name);
  if (!projName) return false;

  return matchData.relevant_projects.some((rp) => {
    if (!rp || typeof rp !== "object") return false;
    const rpName = normalizeMatchStr(rp.name || rp.title || rp.project_name);
    return Boolean(rpName && projName === rpName);
  });
}

/**
 * Derive intelligent default selections:
 * - If deterministic match evidence identifies one or more source records:
 *   select ONLY those identified records.
 * - If deterministic match evidence is unavailable OR identifies no usable source records:
 *   select ALL records.
 * Never silently exclude content with heuristics.
 */
export function deriveInitialSelections(parsedData, matchData) {
  const experiences = Array.isArray(parsedData?.experience) ? parsedData.experience : [];
  const projects = Array.isArray(parsedData?.projects) ? parsedData.projects : [];

  const matchedExp = [];
  experiences.forEach((exp, idx) => {
    if (isExperienceMatched(exp, matchData)) {
      matchedExp.push(idx);
    }
  });

  const matchedProj = [];
  projects.forEach((proj, idx) => {
    if (isProjectMatched(proj, matchData)) {
      matchedProj.push(idx);
    }
  });

  return {
    selectedExpIndices: matchedExp.length > 0 ? matchedExp : experiences.map((_, i) => i),
    selectedProjIndices: matchedProj.length > 0 ? matchedProj : projects.map((_, i) => i),
  };
}
