import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, "..");

console.log("Starting Profile & Settings Simplification (Phase 7.0B.5) Contract Tests...");

// -----------------------------------------------------------------------------
// 1. Routing Contracts in App.jsx
// -----------------------------------------------------------------------------
const appJsxPath = path.join(ROOT, "src", "App.jsx");
assert.ok(fs.existsSync(appJsxPath), "App.jsx must exist");
const appJsx = fs.readFileSync(appJsxPath, "utf8");

assert.match(
  appJsx,
  /<Route\s+path=["']\/profile["']\s+element=\{<ProfilePage\s*\/>\}/,
  "/profile route must render ProfilePage"
);

assert.match(
  appJsx,
  /<Route\s+path=["']\/settings["']\s+element=\{<SettingsPage\s*\/>\}/,
  "/settings route must render SettingsPage"
);
console.log("  ok   1. Routing contracts (/profile, /settings) verified");

// -----------------------------------------------------------------------------
// 2. Profile Page: Absence of Fake Scores & Presence of Real Actions
// -----------------------------------------------------------------------------
const profilePagePath = path.join(ROOT, "src", "pages", "ProfilePage.jsx");
assert.ok(fs.existsSync(profilePagePath), "ProfilePage.jsx must exist");
const profileSrc = fs.readFileSync(profilePagePath, "utf8");

// No fake percentage formula or badge
assert.ok(
  !profileSrc.includes("profile-completeness-badge"),
  "ProfilePage must not contain profile-completeness-badge"
);
assert.ok(
  !profileSrc.includes("completenessPct"),
  "ProfilePage must not contain completenessPct calculation"
);
assert.ok(
  !profileSrc.includes("Profile Strength:"),
  "ProfilePage must not render fake 'Profile Strength:' percentage"
);

// No fake LinkedIn import claims
assert.ok(
  !profileSrc.includes("Import from LinkedIn"),
  "ProfilePage must not contain fake 'Import from LinkedIn' button"
);
assert.ok(
  !profileSrc.includes("linkedin-scraper"),
  "ProfilePage must not contain fake LinkedIn scraper references"
);

// Preserves real CRUD endpoints
const expectedEndpoints = [
  "/profile",
  "/profile/skills",
  "/profile/experiences",
  "/profile/projects",
  "/profile/education",
  "/profile/certifications",
  "/resumes",
];
for (const ep of expectedEndpoints) {
  assert.ok(profileSrc.includes(`"${ep}"`), `ProfilePage must interface with real endpoint ${ep}`);
}

// Quick-add skill capability
assert.ok(
  profileSrc.includes("handleAddSkill"),
  "ProfilePage must provide inline handleAddSkill without forced modal"
);
assert.ok(
  profileSrc.includes("SkillAutocomplete"),
  "ProfilePage must integrate SkillAutocomplete for smart skill entry"
);

// Reusable modal integration
assert.ok(
  profileSrc.includes("ProfileResumeSyncModal"),
  "ProfilePage must integrate ProfileResumeSyncModal"
);
assert.ok(
  profileSrc.includes("ProfileRecordModal"),
  "ProfilePage must integrate reusable ProfileRecordModal"
);
console.log("  ok   2. Profile Page integrity, absence of fake scores, and real actions verified");

// -----------------------------------------------------------------------------
// 2.5 Skill Suggestions Dataset Integrity
// -----------------------------------------------------------------------------
const skillSuggestionsPath = path.join(
  ROOT,
  "src",
  "components",
  "profile",
  "skillSuggestions.js"
);
assert.ok(fs.existsSync(skillSuggestionsPath), "skillSuggestions.js must exist");

const { SKILL_SUGGESTIONS, SKILL_CATEGORIES } = await import(
  `file://${skillSuggestionsPath}`
);

assert.ok(Array.isArray(SKILL_SUGGESTIONS), "SKILL_SUGGESTIONS must be an array");
assert.ok(SKILL_SUGGESTIONS.length > 30, "SKILL_SUGGESTIONS must contain a reasonable dataset");
const hasPython = SKILL_SUGGESTIONS.some(s => s.name === "Python" && s.category === SKILL_CATEGORIES.PROGRAMMING);
assert.ok(hasPython, "SKILL_SUGGESTIONS must contain categorized Python");

console.log("  ok   2.5. Skill suggestions dataset verified");

// -----------------------------------------------------------------------------
// 2.6 SkillAutocomplete Token Contract & Accessibility
// -----------------------------------------------------------------------------
const skillAutocompletePath = path.join(
  ROOT,
  "src",
  "components",
  "profile",
  "SkillAutocomplete.jsx"
);
assert.ok(fs.existsSync(skillAutocompletePath), "SkillAutocomplete.jsx must exist");
const skillAutocompleteSrc = fs.readFileSync(skillAutocompletePath, "utf8");

// Must NOT use undefined CSS custom properties
const forbiddenTokens = [
  "--color-surface",
  "--color-surface-hover",
  "--color-border",
  "--color-text",
  "--color-secondary",
];
for (const token of forbiddenTokens) {
  assert.ok(
    !skillAutocompleteSrc.includes(token),
    `SkillAutocomplete must not reference undefined token '${token}'`
  );
}

// MUST use existing application tokens
const requiredTokens = [
  "--bg-surface",
  "--bg-surface-hover",
  "--text-primary",
  "--text-secondary",
  "--border",
  "--accent",
];
for (const token of requiredTokens) {
  assert.ok(
    skillAutocompleteSrc.includes(token),
    `SkillAutocomplete must reference application token '${token}'`
  );
}

// Accessibility: combobox input must have an accessible label
assert.ok(
  skillAutocompleteSrc.includes('aria-label="Add a skill"'),
  "SkillAutocomplete input must have aria-label='Add a skill'"
);

// No duplicate marginTop in dropdown styles
assert.ok(
  !skillAutocompleteSrc.includes('marginTop: "4px"'),
  "SkillAutocomplete dropdown must not have duplicate marginTop property"
);

console.log("  ok   2.6. SkillAutocomplete CSS token contract and accessibility verified");

// -----------------------------------------------------------------------------
// 3. Resume Sync & Deduplication Logic in profileAutofillUtils.js
// -----------------------------------------------------------------------------
const autofillUtilsPath = path.join(
  ROOT,
  "src",
  "components",
  "profile",
  "profileAutofillUtils.js"
);
assert.ok(fs.existsSync(autofillUtilsPath), "profileAutofillUtils.js must exist");

const {
  buildResumeProfileDiff,
  applyResumeProfileSync,
  filterProfileDiff,
  formatTechnologies,
  normalizeTechnologies,
} = await import(`file://${autofillUtilsPath}`);

// Test empty / invalid input
const emptyDiff = buildResumeProfileDiff(null, null);
assert.strictEqual(emptyDiff.hasChanges, false, "Empty input must return hasChanges: false");
assert.strictEqual(emptyDiff.totalItems, 0, "Empty input must have 0 total items");

// Test deduplication and mapping
const mockParsedResume = {
  basic_info: {
    location: "San Francisco, CA",
    email: "test@example.com",
    linkedin: "https://linkedin.com/in/test",
  },
  skills: ["Python", "FastAPI", "React", "PostgreSQL", "python"], // note duplicate "python"
  education: [
    { degree: "B.S. Computer Science", institution: "UC Berkeley", graduation_year: "2024", gpa: "3.9" },
    { degree: "High School Diploma", institution: "Lincoln High", graduation_year: "2020" },
  ],
  experience: [
    {
      company: "Stripe",
      job_title: "Backend Engineer",
      dates: "2024 - Present",
      tools_used: ["Ruby", "Go"],
      description: "Built APIs",
    },
    {
      job_title: "Software Engineer",
      company: "Example Corp",
      dates: "2024 - Present",
      tools_used: ["Python", "FastAPI"],
      description: "Built backend services.",
    },
    {
      // Malformed record missing company - must be skipped
      company: "",
      job_title: "Junior Dev",
      dates: "2022 - 2023",
    },
    {
      // Malformed record missing job_title - must be skipped
      company: "Ghost Corp",
      job_title: "",
      dates: "2021",
    },
  ],
  projects: [
    { title: "TaskQueue", description: "Distributed queue", url: "https://github.com/test/taskqueue" },
  ],
  certifications: [
    "AWS Certified Solutions Architect",
  ],
};

const mockExistingProfile = {
  profile: {
    location: "San Francisco, CA", // already has location
    preferred_roles: "Backend Engineer",
  },
  skills: [
    { id: "s-1", skill_name: "Python" }, // Python already exists
  ],
  education: [
    { id: "e-1", degree: "B.S. Computer Science", college: "UC Berkeley" }, // already exists
  ],
  experiences: [
    { id: "x-1", company: "Stripe", role: "Backend Engineer" }, // already exists
  ],
  projects: [],
  certifications: [],
};

const diff = buildResumeProfileDiff(mockParsedResume, mockExistingProfile);

assert.strictEqual(diff.hasChanges, true, "Diff should detect items to add");
assert.strictEqual(diff.counts.location, 0, "Existing location must not be re-added");
// Python was existing and duplicate python in resume ignored -> 3 remaining (FastAPI, React, PostgreSQL)
assert.strictEqual(diff.counts.skills, 3, "Only missing skills should be queued for addition");
assert.deepStrictEqual(
  diff.toAdd.skills.map((s) => s.name),
  ["FastAPI", "React", "PostgreSQL"],
  "Skills must exclude existing 'Python'"
);

// Education: UC Berkeley already exists -> 1 remaining (Lincoln High)
assert.strictEqual(diff.counts.education, 1, "Only missing education should be queued");
assert.strictEqual(diff.toAdd.education[0].college, "Lincoln High");

// Experience: Stripe already exists, malformed records skipped -> exactly 1 remaining (Example Corp)
assert.strictEqual(diff.counts.experiences, 1, "Exactly 1 missing experience should be queued");
assert.deepStrictEqual(diff.toAdd.experiences[0], {
  company: "Example Corp",
  role: "Software Engineer",
  start_date: "2024",
  end_date: "Present",
  technologies: ["Python", "FastAPI"],
  description: "Built backend services.",
});

// Repeated sync dedup check
const profileAfterSync = {
  ...mockExistingProfile,
  experiences: [
    ...mockExistingProfile.experiences,
    { id: "x-2", company: "Example Corp", role: "Software Engineer" },
  ],
};
const diffRepeated = buildResumeProfileDiff(mockParsedResume, profileAfterSync);
assert.strictEqual(diffRepeated.counts.experiences, 0, "Repeated sync must deduplicate and queue 0 experiences");

// Projects: TaskQueue is new
assert.strictEqual(diff.counts.projects, 1, "Project should be queued");
assert.strictEqual(diff.toAdd.projects[0].name, "TaskQueue");
assert.strictEqual(
  diff.toAdd.projects[0].github_url,
  "https://github.com/test/taskqueue",
  "GitHub URL should be mapped"
);

// Certifications: AWS is new
assert.strictEqual(diff.counts.certifications, 1, "Certification should be queued");
assert.strictEqual(diff.toAdd.certifications[0].name, "AWS Certified Solutions Architect");

// -----------------------------------------------------------------------------
// 3.5. Technologies Type Normalization Regression Tests
// -----------------------------------------------------------------------------
// a. String input
assert.strictEqual(formatTechnologies("  Python, FastAPI  "), "Python, FastAPI");
assert.strictEqual(normalizeTechnologies("  Python, FastAPI  "), "Python, FastAPI");
assert.strictEqual(formatTechnologies(""), "");
assert.strictEqual(normalizeTechnologies(""), null);
assert.strictEqual(formatTechnologies("   "), "");
assert.strictEqual(normalizeTechnologies("   "), null);

// b. Array input (string[])
assert.strictEqual(
  formatTechnologies(["Python", " FastAPI ", "Docker"]),
  "Python, FastAPI, Docker",
  "Array of strings must format as comma-separated trimmed string"
);
assert.strictEqual(
  normalizeTechnologies(["Python", " FastAPI ", "Docker"]),
  "Python, FastAPI, Docker",
  "Array of strings must normalize as comma-separated string"
);
assert.strictEqual(
  formatTechnologies([" React ", "", "  ", "Next.js"]),
  "React, Next.js",
  "Empty strings in array must be filtered out"
);
assert.strictEqual(
  normalizeTechnologies([" React ", "", "  ", "Next.js"]),
  "React, Next.js"
);

// c. Null / undefined
assert.strictEqual(formatTechnologies(null), "");
assert.strictEqual(normalizeTechnologies(null), null);
assert.strictEqual(formatTechnologies(undefined), "");
assert.strictEqual(normalizeTechnologies(undefined), null);

// d. Empty array
assert.strictEqual(formatTechnologies([]), "");
assert.strictEqual(normalizeTechnologies([]), null);
assert.strictEqual(formatTechnologies(["", "   "]), "");
assert.strictEqual(normalizeTechnologies(["", "   "]), null);

// e. Unexpected non-string/non-array values (numbers, booleans, objects)
assert.strictEqual(formatTechnologies(123), "123");
assert.strictEqual(normalizeTechnologies(123), "123");
assert.strictEqual(formatTechnologies(true), "true");
assert.strictEqual(normalizeTechnologies(true), "true");
assert.strictEqual(formatTechnologies({}), "");
assert.strictEqual(normalizeTechnologies({}), null);
assert.strictEqual(
  formatTechnologies(["Python", 42, null, undefined, "Go"]),
  "Python, 42, Go",
  "Mixed arrays must format safely"
);

// f. buildResumeProfileDiff with real parser shape (projects having array technologies)
const resumeWithDiverseTech = {
  projects: [
    { title: "Proj Array", technologies: ["Python", "FastAPI"] }, // The exact production crash trigger
    { title: "Proj String", technologies: "React, Node.js" },
    { title: "Proj Null", technologies: null },
    { title: "Proj Empty Array", technologies: [] },
    { title: "Proj Number", technologies: 2026 },
  ],
  experience: [
    { company: "Acme", job_title: "Dev", tools_used: ["TypeScript", "GraphQL"] },
  ],
};

const diffDiverse = buildResumeProfileDiff(resumeWithDiverseTech, { projects: [], experiences: [] });
assert.strictEqual(diffDiverse.counts.projects, 5, "All 5 projects should be queued");
assert.strictEqual(
  diffDiverse.toAdd.projects[0].technologies,
  "Python, FastAPI",
  "Array technologies on projects must normalize to comma-separated string"
);
assert.strictEqual(
  diffDiverse.toAdd.projects[1].technologies,
  "React, Node.js",
  "String technologies on projects must be preserved"
);
assert.strictEqual(diffDiverse.toAdd.projects[2].technologies, null);
assert.strictEqual(diffDiverse.toAdd.projects[3].technologies, null);
assert.strictEqual(diffDiverse.toAdd.projects[4].technologies, "2026");

// Verify experience tools_used array is preserved in diff
assert.deepStrictEqual(
  diffDiverse.toAdd.experiences[0].technologies,
  ["TypeScript", "GraphQL"],
  "Experience technologies must preserve array from tools_used in diff"
);

// g. applyResumeProfileSync ensures string/null payloads to API
const postedPayloads = [];
const mockApi = {
  post: async (endpoint, data) => {
    postedPayloads.push({ endpoint, data });
    return data;
  },
  put: async () => ({}),
};
await applyResumeProfileSync(diffDiverse, mockApi, {});

const expPost = postedPayloads.find((p) => p.endpoint === "/profile/experiences");
assert.strictEqual(
  expPost.data.technologies,
  "TypeScript, GraphQL",
  "applyResumeProfileSync must send normalized string to /profile/experiences"
);

const projPost = postedPayloads.find((p) => p.endpoint === "/profile/projects");
assert.strictEqual(
  projPost.data.technologies,
  "Python, FastAPI",
  "applyResumeProfileSync must send normalized string to /profile/projects"
);

// h. Codebase safety guard: ensure no direct .trim() on .technologies
const autofillUtilsSrc = fs.readFileSync(autofillUtilsPath, "utf8");
const forbiddenTrimPatterns = [
  "technologies.trim",
  'technologies || "").trim',
  "technologies || '').trim",
];
for (const pattern of forbiddenTrimPatterns) {
  assert.ok(
    !autofillUtilsSrc.includes(pattern),
    `autofillUtils must not contain unsafe pattern: ${pattern}`
  );
}

console.log("  ok   3. Resume autofill diff, deduplication, and technologies normalization verified");

// -----------------------------------------------------------------------------
// 3.6 Fill Profile from Resume Feature Contract
// -----------------------------------------------------------------------------
const fillModalPath = path.join(
  ROOT,
  "src",
  "components",
  "profile",
  "FillProfileFromResumeModal.jsx"
);
assert.ok(fs.existsSync(fillModalPath), "FillProfileFromResumeModal.jsx must exist");
const fillSrc = fs.readFileSync(fillModalPath, "utf8");
const pagesCssSrc = fs.readFileSync(path.join(ROOT, "src", "styles", "pages.css"), "utf8");

// a. Action exists in Profile page and opens the flow directly
assert.ok(
  profileSrc.includes("FillProfileFromResumeModal"),
  "ProfilePage must import FillProfileFromResumeModal"
);
assert.ok(
  profileSrc.includes("showFillModal"),
  "ProfilePage must manage showFillModal state"
);
assert.ok(
  profileSrc.includes("Fill Profile from Resume"),
  "ProfilePage must render a 'Fill Profile from Resume' action"
);
assert.ok(
  profileSrc.includes("onClick={() => setShowFillModal(true)}"),
  "Fill action must open the flow directly without requiring a saved resume"
);

// b. Available on desktop and mobile (short label handled by CSS, no JS gating)
assert.ok(
  profileSrc.includes("Fill from Resume"),
  "Mobile short label 'Fill from Resume' must exist"
);
assert.ok(
  pagesCssSrc.includes(".fill-btn-label-short"),
  "pages.css must provide the responsive short label for mobile"
);

// c. Reuses existing parsing infrastructure
assert.ok(
  fillSrc.includes('api.uploadFile("/resumes"'),
  "Fill flow must upload via the existing POST /resumes endpoint"
);
assert.ok(
  fillSrc.includes("/parsed"),
  "Fill flow must read parsed data via the existing /resumes/{id}/parsed endpoint"
);
assert.ok(
  fillSrc.includes('api.delete(`/resumes/${resumeId}`)'),
  "Fill flow must clean up the temporary resume record via DELETE /resumes/{id}"
);

// d. Passes parsed data through the existing mapping
assert.ok(
  fillSrc.includes("buildResumeProfileDiff"),
  "Fill flow must reuse buildResumeProfileDiff"
);
assert.ok(
  fillSrc.includes("applyResumeProfileSync"),
  "Fill flow must reuse applyResumeProfileSync for safe merging"
);
assert.ok(
  fillSrc.includes("filterProfileDiff"),
  "Fill flow must support selective import via filterProfileDiff"
);

// e. Selective import: deselected categories must never be applied
const fullFiltered = filterProfileDiff(diff, Object.keys(diff.counts));
assert.strictEqual(
  fullFiltered.totalItems,
  diff.totalItems,
  "Selecting every category must keep all items"
);

const skillsOnly = filterProfileDiff(diff, ["skills"]);
assert.strictEqual(skillsOnly.counts.skills, diff.counts.skills, "Selected category count must be preserved");
assert.strictEqual(skillsOnly.counts.experiences, 0, "Deselected experiences must be excluded");
assert.strictEqual(skillsOnly.counts.projects, 0, "Deselected projects must be excluded");
assert.strictEqual(skillsOnly.counts.education, 0, "Deselected education must be excluded");
assert.strictEqual(skillsOnly.counts.certifications, 0, "Deselected certifications must be excluded");
assert.strictEqual(skillsOnly.counts.location, 0, "Deselected location must be excluded");
assert.deepStrictEqual(skillsOnly.toAdd.experiences, [], "Deselected experience items must be emptied");
assert.strictEqual(
  skillsOnly.totalItems,
  diff.counts.skills,
  "totalItems must reflect only the selected categories"
);

const onlySkillsPosts = [];
const mockApiOnlySkills = {
  post: async (endpoint, data) => {
    onlySkillsPosts.push(endpoint);
    return data;
  },
  put: async () => ({}),
};
await applyResumeProfileSync(skillsOnly, mockApiOnlySkills, mockExistingProfile);
assert.ok(
  onlySkillsPosts.every((ep) => ep === "/profile/skills"),
  "applyResumeProfileSync must only touch selected categories"
);
assert.strictEqual(onlySkillsPosts.length, skillsOnly.counts.skills, "One skill POST per selected skill");

const emptyFiltered = filterProfileDiff(diff, []);
assert.strictEqual(emptyFiltered.hasChanges, false, "Empty selection must yield hasChanges false");
assert.strictEqual(emptyFiltered.totalItems, 0, "Empty selection must yield 0 items");

// f. Fills only empty scalar fields (location) and preserves existing data
const diffNoLocation = buildResumeProfileDiff(mockParsedResume, {
  ...mockExistingProfile,
  profile: { location: "" },
});
assert.strictEqual(
  diffNoLocation.counts.location,
  1,
  "Empty profile location must be filled from resume"
);
assert.strictEqual(diffNoLocation.toAdd.location, "San Francisco, CA");
const locationOnly = filterProfileDiff(diffNoLocation, ["location"]);
assert.strictEqual(locationOnly.totalItems, 1, "Location-only selection must remain applicable");
assert.strictEqual(locationOnly.toAdd.location, "San Francisco, CA");

// g. Array technologies stay safe through filtering (regression for string[])
const techFiltered = filterProfileDiff(diffDiverse, ["projects", "experiences"]);
assert.strictEqual(
  techFiltered.toAdd.projects[0].technologies,
  "Python, FastAPI",
  "Filtered diff must preserve normalized project technologies"
);
assert.deepStrictEqual(
  techFiltered.toAdd.experiences[0].technologies,
  ["TypeScript", "GraphQL"],
  "Filtered diff must preserve experience tools arrays"
);

// h. Missing sections must never fabricate data
const emptyResumeDiff = buildResumeProfileDiff(
  { basic_info: {}, skills: [], education: [], experience: [], projects: [], certifications: [] },
  {}
);
assert.strictEqual(emptyResumeDiff.hasChanges, false, "Empty parsed resume must produce no changes");
assert.strictEqual(emptyResumeDiff.totalItems, 0, "Empty parsed resume must produce no items");

// i. Upload, parser, and no-usable-info failures handled in the UI
assert.ok(
  fillSrc.includes("Failed to process the resume"),
  "Fill flow must surface upload/parse failures with a retry path"
);
assert.ok(
  fillSrc.includes("No usable information"),
  "Fill flow must handle resumes with no extractable information"
);

// j. Existing saved-resume sync remains present and renamed
assert.ok(
  profileSrc.includes("Sync Saved Resume"),
  "Existing saved-resume sync action must be renamed to 'Sync Saved Resume'"
);
assert.ok(
  profileSrc.includes("ProfileResumeSyncModal"),
  "Existing ProfileResumeSyncModal must remain integrated"
);

console.log("  ok   3.6. Fill Profile from Resume flow contract verified");

// -----------------------------------------------------------------------------
// 4. Settings Page Contract
// -----------------------------------------------------------------------------
const settingsPagePath = path.join(ROOT, "src", "pages", "SettingsPage.jsx");
assert.ok(fs.existsSync(settingsPagePath), "SettingsPage.jsx must exist");
const settingsSrc = fs.readFileSync(settingsPagePath, "utf8");

// Verify 3 genuine groups
assert.ok(
  settingsSrc.includes("settings.account") || settingsSrc.includes("Account Identity"),
  "SettingsPage must include Account Identity group"
);
assert.ok(
  settingsSrc.includes("Job Search Defaults"),
  "SettingsPage must include Job Search Defaults group"
);
assert.ok(
  settingsSrc.includes("settings.appearance") || settingsSrc.includes("Appearance & Accessibility"),
  "SettingsPage must include Appearance & Accessibility group"
);

// Verify absence of dead-end Delete Account modal / button
assert.ok(
  !settingsSrc.includes("Delete Account & Reset Workspace"),
  "SettingsPage must not include non-functional 'Delete Account & Reset Workspace' button"
);
assert.ok(
  !settingsSrc.includes("Account Deletion Request"),
  "SettingsPage must not include non-functional account deletion modal"
);

// Verify absence of fake AI and notification preferences
assert.ok(
  !settingsSrc.includes("AI Preferences"),
  "SettingsPage must not fabricate non-existent AI preference toggles"
);
assert.ok(
  !settingsSrc.includes("Notification Preferences"),
  "SettingsPage must not fabricate non-existent notification channels"
);

// Verify Job Search Defaults persistence via /profile
assert.ok(
  settingsSrc.includes('api.put("/profile"'),
  "SettingsPage must persist job preferences via PUT /profile"
);
assert.ok(
  settingsSrc.includes("preferred_roles"),
  "SettingsPage must manage preferred_roles"
);
assert.ok(
  settingsSrc.includes("preferred_locations"),
  "SettingsPage must manage preferred_locations"
);
console.log("  ok   4. Settings Page 3-group contract and fake-control removal verified");

// -----------------------------------------------------------------------------
// 5. Protected Files & Shell Files Integrity Check
// -----------------------------------------------------------------------------
const shellFiles = [
  path.join(ROOT, "src", "components", "Sidebar.jsx"),
  path.join(ROOT, "src", "components", "TopNav.jsx"),
  path.join(ROOT, "src", "components", "BottomNav.jsx"),
  path.join(ROOT, "src", "layouts", "MainLayout.jsx"),
  path.join(ROOT, "src", "styles", "tokens.css"),
  path.join(ROOT, "src", "styles", "components.css"),
  path.join(ROOT, "src", "styles", "layout.css"),
];
for (const sf of shellFiles) {
  assert.ok(fs.existsSync(sf), `Shell file ${sf} must exist`);
}
console.log("  ok   5. Protected files and shell files integrity verified");

console.log("\nAll Profile & Settings Simplification (Phase 7.0B.5) contract tests passed successfully!");
