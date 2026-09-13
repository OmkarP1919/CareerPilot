/**
 * Profile Autofill & Deduplication Utility — Phase 7.0B.5
 *
 * Safely inspects actual parsed resume data from GET /resumes/{id}/parsed
 * and prepares deduplicated updates for the Profile API.
 * Never fabricates data, URLs, or scores.
 */

/**
 * Compare parsed resume data against existing profile records.
 * Identifies missing records to add without overwriting or duplicating existing entries.
 */
export function buildResumeProfileDiff(parsedData, currentProfile) {
  if (!parsedData || typeof parsedData !== "object") {
    return {
      hasChanges: false,
      toAdd: { location: null, skills: [], education: [], experiences: [], projects: [], certifications: [] },
      counts: { location: 0, skills: 0, education: 0, experiences: 0, projects: 0, certifications: 0 },
      totalItems: 0,
    };
  }

  const existingSkills = new Set(
    (currentProfile?.skills || [])
      .map((s) => (s.skill_name || "").trim().toLowerCase())
      .filter(Boolean)
  );

  const existingExperiences = new Set(
    (currentProfile?.experiences || [])
      .map((e) => `${(e.company || "").trim().toLowerCase()}::${(e.role || "").trim().toLowerCase()}`)
      .filter((k) => k !== "::")
  );

  const existingEducation = new Set(
    (currentProfile?.education || [])
      .map((e) => `${(e.degree || "").trim().toLowerCase()}::${(e.college || "").trim().toLowerCase()}`)
      .filter((k) => k !== "::")
  );

  const existingProjects = new Set(
    (currentProfile?.projects || [])
      .map((p) => (p.name || "").trim().toLowerCase())
      .filter(Boolean)
  );

  const existingCertifications = new Set(
    (currentProfile?.certifications || [])
      .map((c) => (c.name || "").trim().toLowerCase())
      .filter(Boolean)
  );

  // 1. Location (only if profile currently has none)
  const resumeLocation = parsedData.basic_info?.location?.trim();
  const shouldAddLocation = !currentProfile?.profile?.location && Boolean(resumeLocation);

  // 2. Skills (deduplicated by case-insensitive name)
  const rawSkills = Array.isArray(parsedData.skills) ? parsedData.skills : [];
  const skillsToAdd = [];
  const seenNewSkills = new Set();

  for (const raw of rawSkills) {
    if (typeof raw !== "string") continue;
    const trimmed = raw.trim();
    const lower = trimmed.toLowerCase();
    if (!trimmed || existingSkills.has(lower) || seenNewSkills.has(lower)) continue;
    seenNewSkills.add(lower);
    skillsToAdd.push({
      name: trimmed,
      category: "Other Technical Skills",
    });
  }

  // 3. Education (deduplicated by degree + institution)
  const rawEducation = Array.isArray(parsedData.education) ? parsedData.education : [];
  const educationToAdd = [];
  const seenEdu = new Set();

  for (const raw of rawEducation) {
    if (!raw || typeof raw !== "object") continue;
    const degree = (raw.degree || "").trim();
    const college = (raw.institution || "").trim();
    if (!degree || !college) continue;

    const key = `${degree.toLowerCase()}::${college.toLowerCase()}`;
    if (existingEducation.has(key) || seenEdu.has(key)) continue;
    seenEdu.add(key);

    educationToAdd.push({
      degree,
      college,
      branch: (raw.field_of_study || "").trim() || null,
      graduation_year: raw.graduation_year ? String(raw.graduation_year).trim() : null,
      cgpa: raw.gpa ? String(raw.gpa).trim() : null,
    });
  }

  // 4. Experience (deduplicated by company + role)
  const rawExperience = Array.isArray(parsedData.experience) ? parsedData.experience : [];
  const experienceToAdd = [];
  const seenExp = new Set();

  for (const raw of rawExperience) {
    if (!raw || typeof raw !== "object") continue;
    const company = (raw.company || "").trim();
    // Real parser emits job_title; fallback defensively to role/title
    const role = (raw.job_title || raw.role || raw.title || "").trim();
    if (!company || !role) continue;

    const key = `${company.toLowerCase()}::${role.toLowerCase()}`;
    if (existingExperiences.has(key) || seenExp.has(key)) continue;
    seenExp.add(key);

    // Date handling: real parser emits dates: "2024 - Present"
    let startDate = null;
    let endDate = null;
    if (typeof raw.dates === "string") {
      const trimmedDates = raw.dates.trim();
      if (trimmedDates) {
        const dateParts = trimmedDates.split(/\s*(?:[-–—]|\bto\b)\s*/);
        if (dateParts.length >= 2) {
          startDate = dateParts[0].trim() || null;
          endDate = dateParts.slice(1).join(" - ").trim() || null;
        } else {
          startDate = trimmedDates;
          endDate = null;
        }
      }
    } else {
      startDate = (raw.start_date || "").trim() || null;
      endDate = (raw.end_date || "").trim() || null;
    }

    // Tools handling: real parser emits tools_used: [...]
    let technologies = null;
    const rawTools = raw.tools_used !== undefined ? raw.tools_used : (raw.technologies !== undefined ? raw.technologies : null);
    if (Array.isArray(rawTools)) {
      const cleaned = rawTools
        .map((t) => (typeof t === "string" ? t.trim() : String(t || "")).trim())
        .filter(Boolean);
      technologies = cleaned.length > 0 ? cleaned : null;
    } else if (typeof rawTools === "string" && rawTools.trim()) {
      technologies = rawTools.trim();
    }

    // Description handling: real parser emits description: "..."
    let description = null;
    if (typeof raw.description === "string" && raw.description.trim()) {
      description = raw.description.trim();
    } else if (Array.isArray(raw.bullets) && raw.bullets.length > 0) {
      description = raw.bullets
        .map((b) => (typeof b === "string" ? b.trim() : String(b || "")).trim())
        .filter(Boolean)
        .join("\n");
      if (!description) description = null;
    }

    experienceToAdd.push({
      company,
      role,
      start_date: startDate,
      end_date: endDate,
      description,
      technologies,
    });
  }

  // 5. Projects (deduplicated by name/title)
  const rawProjects = Array.isArray(parsedData.projects) ? parsedData.projects : [];
  const projectsToAdd = [];
  const seenProjects = new Set();

  for (const raw of rawProjects) {
    if (!raw || typeof raw !== "object") continue;
    const name = (raw.title || raw.name || "").trim();
    if (!name) continue;

    const key = name.toLowerCase();
    if (existingProjects.has(key) || seenProjects.has(key)) continue;
    seenProjects.add(key);

    const projectUrl = (raw.url || "").trim();
    const isGithub = projectUrl.includes("github.com");

    projectsToAdd.push({
      name,
      description: (raw.description || (Array.isArray(raw.bullets) ? raw.bullets.join("\n") : "")).trim() || null,
      technologies: (raw.technologies || "").trim() || null,
      github_url: isGithub ? projectUrl : null,
      live_url: !isGithub && projectUrl ? projectUrl : null,
    });
  }

  // 6. Certifications (deduplicated by name)
  const rawCerts = Array.isArray(parsedData.certifications) ? parsedData.certifications : [];
  const certificationsToAdd = [];
  const seenCerts = new Set();

  for (const raw of rawCerts) {
    let name = "";
    let organization = null;
    let issue_date = null;
    let credential_url = null;

    if (typeof raw === "string") {
      name = raw.trim();
    } else if (raw && typeof raw === "object") {
      name = (raw.name || "").trim();
      organization = (raw.organization || "").trim() || null;
      issue_date = (raw.issue_date || "").trim() || null;
      credential_url = (raw.credential_url || "").trim() || null;
    }

    if (!name) continue;
    const key = name.toLowerCase();
    if (existingCertifications.has(key) || seenCerts.has(key)) continue;
    seenCerts.add(key);

    certificationsToAdd.push({
      name,
      organization,
      issue_date,
      credential_url,
    });
  }

  const counts = {
    location: shouldAddLocation ? 1 : 0,
    skills: skillsToAdd.length,
    education: educationToAdd.length,
    experiences: experienceToAdd.length,
    projects: projectsToAdd.length,
    certifications: certificationsToAdd.length,
  };

  const totalItems = Object.values(counts).reduce((a, b) => a + b, 0);

  return {
    hasChanges: totalItems > 0,
    toAdd: {
      location: shouldAddLocation ? resumeLocation : null,
      skills: skillsToAdd,
      education: educationToAdd,
      experiences: experienceToAdd,
      projects: projectsToAdd,
      certifications: certificationsToAdd,
    },
    counts,
    totalItems,
  };
}

/**
 * Apply the generated diff to the backend using existing REST endpoints.
 * Returns results and error count.
 */
export async function applyResumeProfileSync(diff, api, currentProfile) {
  if (!diff?.hasChanges) return { success: true, count: 0, errors: [] };

  const errors = [];
  let appliedCount = 0;

  // 1. Update location if new
  if (diff.toAdd.location) {
    try {
      await api.put("/profile", {
        location: diff.toAdd.location,
        preferred_roles: currentProfile?.profile?.preferred_roles || "",
        preferred_locations: currentProfile?.profile?.preferred_locations || "",
      });
      appliedCount += 1;
    } catch (err) {
      errors.push(`Location update failed: ${err.message || "Unknown error"}`);
    }
  }

  // 2. Add skills
  for (const skill of diff.toAdd.skills) {
    try {
      await api.post("/profile/skills", skill);
      appliedCount += 1;
    } catch (err) {
      errors.push(`Failed to add skill "${skill.name}": ${err.message || "Unknown error"}`);
    }
  }

  // 3. Add education
  for (const edu of diff.toAdd.education) {
    try {
      await api.post("/profile/education", edu);
      appliedCount += 1;
    } catch (err) {
      errors.push(`Failed to add education "${edu.degree}": ${err.message || "Unknown error"}`);
    }
  }

  // 4. Add experiences
  for (const exp of diff.toAdd.experiences) {
    try {
      const payload = {
        ...exp,
        technologies: Array.isArray(exp.technologies)
          ? exp.technologies.join(", ")
          : (exp.technologies || null),
      };
      await api.post("/profile/experiences", payload);
      appliedCount += 1;
    } catch (err) {
      errors.push(`Failed to add experience "${exp.role}": ${err.message || "Unknown error"}`);
    }
  }

  // 5. Add projects
  for (const proj of diff.toAdd.projects) {
    try {
      await api.post("/profile/projects", proj);
      appliedCount += 1;
    } catch (err) {
      errors.push(`Failed to add project "${proj.name}": ${err.message || "Unknown error"}`);
    }
  }

  // 6. Add certifications
  for (const cert of diff.toAdd.certifications) {
    try {
      await api.post("/profile/certifications", cert);
      appliedCount += 1;
    } catch (err) {
      errors.push(`Failed to add certification "${cert.name}": ${err.message || "Unknown error"}`);
    }
  }

  return {
    success: errors.length === 0,
    count: appliedCount,
    errors,
  };
}
