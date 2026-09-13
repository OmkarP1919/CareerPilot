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
  profileSrc.includes("newSkillText"),
  "ProfilePage must have newSkillText state for rapid skill entry"
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

const { buildResumeProfileDiff, applyResumeProfileSync } = await import(
  `file://${autofillUtilsPath}`
);

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

console.log("  ok   3. Resume autofill diff and deduplication contracts verified");

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
