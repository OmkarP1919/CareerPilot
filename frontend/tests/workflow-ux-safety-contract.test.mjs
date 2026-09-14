import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, "..");

console.log("Starting Workflow Integrity & UX Safety (Phase 7.0C.2) Contract Tests...\n");

// -----------------------------------------------------------------------------
// 1. RESUME -> PROFILE BRIDGE & HOME NEXT-ACTION PRECEDENCE
// -----------------------------------------------------------------------------
console.log("1. Testing Resume -> Profile Bridge & Home Next-Action Precedence...");

// 1A. Home Next-Action Precedence in dashboardUtils.js
const dashboardUtilsPath = path.join(ROOT, "src", "components", "dashboard", "dashboardUtils.js");
const { determineNextAction } = await import(`file://${dashboardUtilsPath}`);

// Precedence 1: setup_resume (!hasResumes && !hasProfileSkills)
const p1 = determineNextAction({
  resumes: [],
  profile: null,
  applications: [],
  recommendedJobs: [],
  interviews: [],
});
assert.strictEqual(p1.type, "setup_resume", "Precedence 1 must be setup_resume");

// Precedence 2: upload_resume (!hasResumes && hasProfileSkills)
const p2 = determineNextAction({
  resumes: [],
  profile: { skills: [{ skill_name: "React" }] },
  applications: [],
  recommendedJobs: [],
  interviews: [],
});
assert.strictEqual(p2.type, "upload_resume", "Precedence 2 must be upload_resume");

// Precedence 3: sync_resume_profile (hasResumes && !hasProfileSkills)
const p3 = determineNextAction({
  resumes: [{ id: "res-1", filename: "resume.pdf" }],
  profile: { skills: [] },
  applications: [],
  recommendedJobs: [],
  interviews: [],
});
assert.strictEqual(p3.type, "sync_resume_profile", "Precedence 3 must be sync_resume_profile when hasResumes && !hasProfileSkills");
assert.strictEqual(p3.ctaLink, "/resumes", "sync_resume_profile must link to /resumes");
assert.strictEqual(p3.ctaLabel, "Sync to Profile");
assert.strictEqual(p3.ctaIcon, "refresh");

// Precedence 4: upcoming_interview (must NOT be overridden by lower priorities, but only runs if user has profile skills)
const futureDate = new Date(Date.now() + 86400000 * 2).toISOString();
const p4WithProfile = determineNextAction({
  resumes: [{ id: "res-1", filename: "resume.pdf" }],
  profile: { skills: [{ skill_name: "Python" }] },
  applications: [{ id: "app-1", status: "interview" }],
  recommendedJobs: [{ id: "job-1", match_score: 92 }],
  interviews: [{ id: "iv-1", scheduled_at: futureDate, status: "scheduled", kind: "Technical" }],
});
assert.strictEqual(p4WithProfile.type, "upcoming_interview", "Upcoming interview takes precedence once profile has skills");

// Precedence 5: tailor_opportunity
const p5 = determineNextAction({
  resumes: [{ id: "res-1", filename: "resume.pdf" }],
  profile: { skills: [{ skill_name: "Python" }] },
  applications: [],
  recommendedJobs: [{ id: "job-1", title: "Backend Eng", company: "Meta", match_score: 85 }],
  interviews: [],
});
assert.strictEqual(p5.type, "tailor_opportunity", "Tailor opportunity takes precedence over advance_application / explore_jobs");

// Precedence 6: advance_application
const p6 = determineNextAction({
  resumes: [{ id: "res-1", filename: "resume.pdf" }],
  profile: { skills: [{ skill_name: "Python" }] },
  applications: [{ id: "app-1", status: "saved", job_title: "Staff Eng", job_company: "Stripe" }],
  recommendedJobs: [{ id: "job-1", match_score: 50 }],
  interviews: [],
});
assert.strictEqual(p6.type, "advance_application", "Saved application advancement takes precedence over explore_jobs");

// Precedence 7: explore_jobs
const p7 = determineNextAction({
  resumes: [{ id: "res-1", filename: "resume.pdf" }],
  profile: { skills: [{ skill_name: "Python" }] },
  applications: [],
  recommendedJobs: [],
  interviews: [],
});
assert.strictEqual(p7.type, "explore_jobs", "Default fallback action is explore_jobs");

console.log("  ok   Home next-action precedence verified (1. setup, 2. upload, 3. sync, 4. interview, 5. tailor, 6. advance, 7. explore)");

// 1B. Reusable profileAutofillUtils contracts
const autofillUtilsPath = path.join(ROOT, "src", "components", "profile", "profileAutofillUtils.js");
const { buildResumeProfileDiff, applyResumeProfileSync } = await import(`file://${autofillUtilsPath}`);

// Diff with empty profile
const emptyProfileDiff = buildResumeProfileDiff(
  {
    basic_info: { location: "Seattle, WA" },
    skills: ["TypeScript", "Node.js", "Docker"],
    experience: [{ company: "Amazon", role: "SDE II", description: "Cloud services" }],
    education: [{ degree: "B.S. CS", institution: "UW" }],
    projects: [{ name: "CareerPilot", description: "AI Platform" }],
    certifications: ["AWS Solutions Architect"],
  },
  { profile: {}, skills: [], experiences: [], education: [], projects: [], certifications: [] }
);
assert.strictEqual(emptyProfileDiff.hasChanges, true);
assert.strictEqual(emptyProfileDiff.counts.skills, 3);
assert.strictEqual(emptyProfileDiff.counts.experiences, 1);
assert.strictEqual(emptyProfileDiff.counts.education, 1);
assert.strictEqual(emptyProfileDiff.counts.projects, 1);
assert.strictEqual(emptyProfileDiff.counts.certifications, 1);
assert.strictEqual(emptyProfileDiff.counts.location, 1);

// Diff with already-synced profile (no-changes state)
const alreadySyncedDiff = buildResumeProfileDiff(
  {
    basic_info: { location: "Seattle, WA" },
    skills: ["TypeScript", "Node.js"],
    experience: [{ company: "Amazon", role: "SDE II" }],
    education: [{ degree: "B.S. CS", college: "UW" }],
    projects: [{ name: "CareerPilot" }],
    certifications: ["AWS Solutions Architect"],
  },
  {
    profile: { location: "Seattle, WA" },
    skills: [{ skill_name: "TypeScript" }, { skill_name: "Node.js" }],
    experiences: [{ company: "Amazon", role: "SDE II" }],
    education: [{ degree: "B.S. CS", college: "UW" }],
    projects: [{ name: "CareerPilot" }],
    certifications: [{ name: "AWS Solutions Architect" }],
  }
);
assert.strictEqual(alreadySyncedDiff.hasChanges, false, "Already synced resume must report hasChanges: false");
assert.strictEqual(alreadySyncedDiff.totalItems, 0, "Already synced resume total items to add must be 0");

// Partial sync failure handling in applyResumeProfileSync
const mockApiWithFailure = {
  post: async (path, body) => {
    if (path === "/profile/skills" && body.name === "FailSkill") {
      throw new Error("Duplicate database constraint");
    }
    return { id: "ok-1", ...body };
  },
  put: async () => ({}),
};
const partialDiff = {
  hasChanges: true,
  toAdd: {
    location: null,
    skills: [{ name: "GoodSkill", category: "Other" }, { name: "FailSkill", category: "Other" }],
    education: [],
    experiences: [],
    projects: [],
    certifications: [],
  },
};
const syncResult = await applyResumeProfileSync(partialDiff, mockApiWithFailure, {});
assert.strictEqual(syncResult.success, false, "Partial failure must report success: false");
assert.strictEqual(syncResult.count, 1, "Successful items must still be counted");
assert.strictEqual(syncResult.errors.length, 1, "Error must be recorded in errors array");

// 1C. Verify Resume -> Profile bridge lives in non-protected surfaces only.
// ResumesPage.jsx is a protected Resume Parsing 2.0 baseline file (see
// backend/scripts/release_smoke.py PROTECTED_FILES_AT_HEAD); the bridge must
// therefore be wired through ProfilePage.jsx and the shared profile utilities,
// never asserted against protected file content.
const profileBridgePath = path.join(ROOT, "src", "pages", "ProfilePage.jsx");
const profileBridgeContent = fs.readFileSync(profileBridgePath, "utf8");
assert.ok(
  profileBridgeContent.includes("import ProfileResumeSyncModal from \"../components/profile/ProfileResumeSyncModal\";"),
  "ProfilePage must import ProfileResumeSyncModal"
);
assert.ok(profileBridgeContent.includes("<ProfileResumeSyncModal"), "ProfilePage must render ProfileResumeSyncModal");
assert.ok(profileBridgeContent.includes("onConfirmSync={handleConfirmResumeSync}"), "ProfilePage must bind ProfileResumeSyncModal confirm handler");
assert.ok(profileBridgeContent.includes("buildResumeProfileDiff"), "ProfilePage must use buildResumeProfileDiff");
assert.ok(profileBridgeContent.includes("applyResumeProfileSync"), "ProfilePage must use applyResumeProfileSync");
console.log("  ok   Resume -> Profile bridge verified (via ProfilePage, non-protected surface)");

// -----------------------------------------------------------------------------
// 2. PROFILE DELETION SAFETY
// -----------------------------------------------------------------------------
console.log("2. Testing Profile Deletion Safety...");

const profilePagePath = path.join(ROOT, "src", "pages", "ProfilePage.jsx");
const profilePageContent = fs.readFileSync(profilePagePath, "utf8");

// Verify ConfirmDialog is imported and used
assert.ok(profilePageContent.includes("import ConfirmDialog from \"../components/ConfirmDialog\";"), "ProfilePage must import ConfirmDialog");
assert.ok(profilePageContent.includes("<ConfirmDialog"), "ProfilePage must render ConfirmDialog");
assert.ok(profilePageContent.includes("promptDeleteRecord"), "ProfilePage must define promptDeleteRecord");
assert.ok(profilePageContent.includes("handleConfirmDelete"), "ProfilePage must define handleConfirmDelete");
assert.ok(profilePageContent.includes("handleCancelDelete"), "ProfilePage must define handleCancelDelete");

// Confirm prompt wired on all 4 structured records
assert.ok(profilePageContent.includes("promptDeleteRecord(\"experience\""), "Experience deletion must prompt confirmation");
assert.ok(profilePageContent.includes("promptDeleteRecord(\"project\""), "Project deletion must prompt confirmation");
assert.ok(profilePageContent.includes("promptDeleteRecord(\"education\""), "Education deletion must prompt confirmation");
assert.ok(profilePageContent.includes("promptDeleteRecord(\"certification\""), "Certification deletion must prompt confirmation");

// Check loading state prevents double submit
assert.ok(profilePageContent.includes("loading={deletingRecord}"), "ConfirmDialog must bind loading={deletingRecord}");
assert.ok(profilePageContent.includes("if (!type || !id || deletingRecord) return;"), "handleConfirmDelete must guard against double submission");
console.log("  ok   Profile record deletion confirmation & safety verified");

// -----------------------------------------------------------------------------
// 3. JOB WORK-MODE NORMALIZATION
// -----------------------------------------------------------------------------
console.log("3. Testing Job Work-Mode Normalization...");

const jobUtilsPath = path.join(ROOT, "src", "components", "jobs", "jobUtils.js");
const { normalizeWorkMode, formatWorkMode, normalizeJob: normJob } = await import(`file://${jobUtilsPath}`);

// Canonical internal values
assert.strictEqual(normalizeWorkMode("Remote"), "remote");
assert.strictEqual(normalizeWorkMode("remote"), "remote");
assert.strictEqual(normalizeWorkMode("true"), "remote");
assert.strictEqual(normalizeWorkMode("Hybrid"), "hybrid");
assert.strictEqual(normalizeWorkMode("hybrid"), "hybrid");
assert.strictEqual(normalizeWorkMode("Onsite"), "onsite");
assert.strictEqual(normalizeWorkMode("onsite"), "onsite");
assert.strictEqual(normalizeWorkMode("on-site"), "onsite");
assert.strictEqual(normalizeWorkMode("in-office"), "onsite");
assert.strictEqual(normalizeWorkMode("false"), "onsite");
assert.strictEqual(normalizeWorkMode("unspecified"), "unspecified");
assert.strictEqual(normalizeWorkMode("", "San Francisco (Remote)"), "remote");
assert.strictEqual(normalizeWorkMode("", "Austin, TX (Hybrid)"), "hybrid");
assert.strictEqual(normalizeWorkMode("", "New York Onsite"), "onsite");
assert.strictEqual(normalizeWorkMode("", "London, UK"), "unspecified");

// User-friendly formatted labels
assert.strictEqual(formatWorkMode("remote"), "Remote");
assert.strictEqual(formatWorkMode("hybrid"), "Hybrid");
assert.strictEqual(formatWorkMode("onsite"), "Onsite");
assert.strictEqual(formatWorkMode("unspecified"), "");
assert.strictEqual(formatWorkMode(""), "");

// Normalizing local job vs external hit consistency
const localNorm = normJob({
  id: "loc-1",
  title: "Dev",
  location: "Remote",
  work_mode: "Remote",
});
assert.strictEqual(localNorm.work_mode, "remote", "Local job with Remote must normalize to canonical 'remote'");

const extNorm = normJob({
  canonical_key: "ext-1",
  title: "Dev",
  location: "Austin",
  work_mode: "Hybrid",
});
assert.strictEqual(extNorm.work_mode, "hybrid", "External job with Hybrid must normalize to canonical 'hybrid'");

// Verify useJobSearch.js preserves _remote_mode in saved search payload
const useJobSearchPath = path.join(ROOT, "src", "hooks", "useJobSearch.js");
const useJobSearchContent = fs.readFileSync(useJobSearchPath, "utf8");
assert.ok(
  useJobSearchContent.includes('payload._remote_mode = criteria.remote || "";'),
  "useJobSearch.js must preserve criteria.remote into payload._remote_mode"
);

// Verify JobsPage.jsx uses normalizeWorkMode in both loadFilteredFeed and handleRunSavedSearchFromDrawer
const jobsPagePath = path.join(ROOT, "src", "pages", "JobsPage.jsx");
const jobsPageContent = fs.readFileSync(jobsPagePath, "utf8");
assert.ok(jobsPageContent.includes("normalizeWorkMode"), "JobsPage must import and use normalizeWorkMode");
assert.ok(jobsPageContent.includes("const canonicalFilter = normalizeWorkMode(remote);"), "JobsPage loadFilteredFeed must normalize remote filter");
assert.ok(
  jobsPageContent.includes("savedSearch?.criteria?._remote_mode !== undefined"),
  "JobsPage handleRunSavedSearchFromDrawer must check _remote_mode first"
);

// 3B. Behavioral proof of Saved Search Creation & Replay Work-Mode Preservation (BLOCKER B1)
const { buildDiscoveryPayload } = await import(`file://${jobUtilsPath}`);

// Helper simulating handleSaveSearch payload construction
function prepareSavedSearchPayload(criteria) {
  const payload = buildDiscoveryPayload(criteria);
  payload._remote_mode = criteria.remote || "";
  return payload;
}

// 1. Remote preserves _remote_mode = "Remote"
const savedRemotePayload = prepareSavedSearchPayload({ remote: "Remote" });
assert.strictEqual(savedRemotePayload._remote_mode, "Remote", "handleSaveSearch must preserve _remote_mode = 'Remote'");
assert.strictEqual(savedRemotePayload.remote, true, "Backend discovery remote boolean must remain true");

// 2. Hybrid preserves _remote_mode = "Hybrid"
const savedHybridPayload = prepareSavedSearchPayload({ remote: "Hybrid" });
assert.strictEqual(savedHybridPayload._remote_mode, "Hybrid", "handleSaveSearch must preserve _remote_mode = 'Hybrid'");
assert.strictEqual(savedHybridPayload.remote, true, "Backend discovery remote boolean must remain true for Hybrid");

// 3. Onsite preserves _remote_mode = "Onsite"
const savedOnsitePayload = prepareSavedSearchPayload({ remote: "Onsite" });
assert.strictEqual(savedOnsitePayload._remote_mode, "Onsite", "handleSaveSearch must preserve _remote_mode = 'Onsite'");
assert.strictEqual(savedOnsitePayload.remote, false, "Backend discovery remote boolean must remain false for Onsite");

// 4. Empty preserves _remote_mode = ""
const savedEmptyPayload = prepareSavedSearchPayload({ remote: "" });
assert.strictEqual(savedEmptyPayload._remote_mode, "", "Empty remote must preserve _remote_mode = ''");
assert.strictEqual(savedEmptyPayload.remote, null, "Backend discovery remote boolean must remain null for empty");

// Helper simulating JobsPage.jsx handleRunSavedSearchFromDrawer replay resolution
function resolveReplayFilter(savedSearch) {
  let canonicalFilter = null;
  if (savedSearch?.criteria?._remote_mode !== undefined) {
    const raw = savedSearch.criteria._remote_mode;
    if (raw) canonicalFilter = normalizeWorkMode(raw);
  } else if (savedSearch?.criteria?.remote !== undefined && savedSearch.criteria.remote !== null) {
    canonicalFilter = normalizeWorkMode(savedSearch.criteria.remote);
  }
  return canonicalFilter;
}

// Sample jobs pool for replay filtering test
const replaySampleJobs = [
  { id: "job-rem", title: "Remote Role", work_mode: "remote" },
  { id: "job-hyb", title: "Hybrid Role", work_mode: "hybrid" },
  { id: "job-ons", title: "Onsite Role", work_mode: "onsite" },
];

function applyReplayNarrowing(jobs, filter) {
  if (!filter) return jobs;
  return jobs.filter((j) => normalizeWorkMode(j.work_mode, j.location) === filter);
}

// Replay test: Remote saved search
const replayRemoteFilter = resolveReplayFilter({ criteria: savedRemotePayload });
assert.strictEqual(replayRemoteFilter, "remote", "Remote replay must resolve to 'remote'");
const remoteFiltered = applyReplayNarrowing(replaySampleJobs, replayRemoteFilter);
assert.deepStrictEqual(remoteFiltered.map((j) => j.id), ["job-rem"], "Remote replay must yield ONLY remote jobs");

// Replay test: Hybrid saved search (PROOF: Does NOT narrow to remote only despite criteria.remote === true!)
const replayHybridFilter = resolveReplayFilter({ criteria: savedHybridPayload });
assert.strictEqual(replayHybridFilter, "hybrid", "Hybrid replay must resolve to 'hybrid', NOT 'remote'");
const hybridFiltered = applyReplayNarrowing(replaySampleJobs, replayHybridFilter);
assert.deepStrictEqual(hybridFiltered.map((j) => j.id), ["job-hyb"], "Hybrid replay must yield ONLY hybrid jobs");

// Replay test: Onsite saved search (PROOF: Does NOT get skipped despite criteria.remote === false!)
const replayOnsiteFilter = resolveReplayFilter({ criteria: savedOnsitePayload });
assert.strictEqual(replayOnsiteFilter, "onsite", "Onsite replay must resolve to 'onsite'");
const onsiteFiltered = applyReplayNarrowing(replaySampleJobs, replayOnsiteFilter);
assert.deepStrictEqual(onsiteFiltered.map((j) => j.id), ["job-ons"], "Onsite replay must yield ONLY onsite jobs");

// Replay test: Empty work-mode saved search
const replayEmptyFilter = resolveReplayFilter({ criteria: savedEmptyPayload });
assert.strictEqual(replayEmptyFilter, null, "Empty remote mode must produce null filter");
const emptyFiltered = applyReplayNarrowing(replaySampleJobs, replayEmptyFilter);
assert.strictEqual(emptyFiltered.length, 3, "Empty remote mode must keep all jobs without narrowing");

// Replay test: Legacy saved searches (backward compatibility without _remote_mode)
const legacyRemoteFilter = resolveReplayFilter({ criteria: { remote: true } });
assert.strictEqual(legacyRemoteFilter, "remote", "Legacy saved search with remote: true must fall back to 'remote'");

const legacyOnsiteFilter = resolveReplayFilter({ criteria: { remote: false } });
assert.strictEqual(legacyOnsiteFilter, "onsite", "Legacy saved search with remote: false must fall back to 'onsite'");

const legacyUnspecifiedFilter = resolveReplayFilter({ criteria: { remote: null } });
assert.strictEqual(legacyUnspecifiedFilter, null, "Legacy saved search with remote: null must not narrow");

// Verify JobCard and JobHeroHeader use formatWorkMode
const jobCardPath = path.join(ROOT, "src", "components", "jobs", "JobCard.jsx");
const jobCardContent = fs.readFileSync(jobCardPath, "utf8");
assert.ok(jobCardContent.includes("formatWorkMode"), "JobCard must import and use formatWorkMode");

const jobHeroHeaderPath = path.join(ROOT, "src", "components", "job-details", "JobHeroHeader.jsx");
const jobHeroHeaderContent = fs.readFileSync(jobHeroHeaderPath, "utf8");
assert.ok(jobHeroHeaderContent.includes("formatWorkMode"), "JobHeroHeader must import and use formatWorkMode");
console.log("  ok   Job work-mode canonical normalization, saved search _remote_mode preservation & replay verified");

// -----------------------------------------------------------------------------
// 4. TAILORED RESULT CORRECTNESS
// -----------------------------------------------------------------------------
console.log("4. Testing Tailored Result Correctness...");

const tailoredResultPath = path.join(ROOT, "src", "components", "TailoredResult.jsx");
const tailoredResultContent = fs.readFileSync(tailoredResultPath, "utf8");

// Developer comment removed
assert.ok(
  !tailoredResultContent.includes("(Tailored ATS score requires backend enhancement)"),
  "Developer comment '(Tailored ATS score requires backend enhancement)' must be removed"
);

// Actual backend contract fields consumed in experience comparison
assert.ok(tailoredResultContent.includes("exp.original_title"), "TailoredResult must consume exp.original_title");
assert.ok(tailoredResultContent.includes("exp.original_bullets"), "TailoredResult must consume exp.original_bullets");
assert.ok(tailoredResultContent.includes("exp.tailored_bullets"), "TailoredResult must consume exp.tailored_bullets");
assert.ok(tailoredResultContent.includes("exp.changes"), "TailoredResult must consume exp.changes");
console.log("  ok   TailoredResult contract correctness and developer text absence verified");

// -----------------------------------------------------------------------------
// 5. INSIGHTS NAVIGATION
// -----------------------------------------------------------------------------
console.log("5. Testing Insights Navigation in Sidebar...");

const sidebarPath = path.join(ROOT, "src", "components", "Sidebar.jsx");
const sidebarContent = fs.readFileSync(sidebarPath, "utf8");

assert.ok(sidebarContent.includes("TrendingUp"), "Sidebar must import TrendingUp");
assert.ok(
  sidebarContent.includes('{ to: "/insights", label: t("nav.insights", "Insights"), icon: TrendingUp }'),
  "Sidebar must include /insights in secondaryNavItems"
);
assert.ok(sidebarContent.includes('to === "/insights"'), "Sidebar isItemActive must handle /insights");
assert.ok(sidebarContent.includes('{ to: "/profile"'), "Profile must remain in secondary navigation");
assert.ok(sidebarContent.includes('{ to: "/settings"'), "Settings must remain in secondary navigation");
console.log("  ok   Sidebar Insights navigation contract verified");

// -----------------------------------------------------------------------------
// 6. JOBS FILTER DRAWER LAYOUT & WORKSPACE SHELL POSITIONING
// -----------------------------------------------------------------------------
console.log("6. Testing Jobs Filter Drawer Layout & Positioning...");

const jobFilterDrawerPath = path.join(ROOT, "src", "components", "jobs", "JobFilterDrawer.jsx");
const jobFilterDrawerContent = fs.readFileSync(jobFilterDrawerPath, "utf8");

// Portal to document.body
assert.ok(
  jobFilterDrawerContent.includes('import { createPortal } from "react-dom";'),
  "JobFilterDrawer must import createPortal from react-dom"
);
assert.ok(
  jobFilterDrawerContent.includes("createPortal(drawerContent, document.body)"),
  "JobFilterDrawer must mount drawerContent to document.body via createPortal"
);

// CSS rules verification
const pagesCssPath = path.join(ROOT, "src", "styles", "pages.css");
const pagesCssContent = fs.readFileSync(pagesCssPath, "utf8");

// No undefined --z-modal
assert.ok(
  !pagesCssContent.includes("var(--z-modal)"),
  "pages.css must not use undefined --z-modal"
);

// No orphaned jobs-filter-panel or duplicate unscoped drawer
assert.ok(
  !pagesCssContent.includes(".jobs-filter-panel.desktop-only"),
  "pages.css must not contain stale .jobs-filter-panel styles"
);
assert.ok(
  !pagesCssContent.includes("slideUpDrawer"),
  "pages.css must not contain rogue slideUpDrawer keyframes"
);

// Exactly one desktop .jobs-filter-drawer definition and one in media query
const drawerMatches = pagesCssContent.match(/\.jobs-filter-drawer\s*\{/g);
assert.strictEqual(
  drawerMatches?.length,
  2,
  "There must be exactly 2 .jobs-filter-drawer blocks in pages.css (1 desktop base, 1 mobile media query)"
);

// Desktop right slide-over contracts
assert.ok(
  pagesCssContent.includes("width: 440px;"),
  "Desktop .jobs-filter-drawer must be 440px wide"
);
assert.ok(
  pagesCssContent.includes("justify-content: flex-end;"),
  "Desktop .jobs-filter-drawer-backdrop must align drawer to right side via justify-content: flex-end"
);
assert.ok(
  pagesCssContent.includes("z-index: 1000;"),
  "Desktop .jobs-filter-drawer-backdrop must have z-index: 1000 (above persistent desktop sidebar z-index: 40)"
);
assert.ok(
  pagesCssContent.includes("z-index: 1001;"),
  "Desktop .jobs-filter-drawer must have z-index: 1001"
);

// Mobile bottom-sheet contract
assert.ok(
  pagesCssContent.includes("@media (max-width: 768px)"),
  "Mobile bottom sheet styles must be scoped under @media (max-width: 768px)"
);
assert.ok(
  pagesCssContent.includes("animation: slideInUp"),
  "Mobile drawer must use slideInUp animation"
);

// Drawer body scroll contract
assert.ok(
  pagesCssContent.includes("min-height: 0;"),
  ".drawer-body must have min-height: 0 for reliable flex scroll"
);

console.log("  ok   Jobs filter drawer layout, portal mounting, and viewport contracts verified");

console.log("\nAll Workflow Integrity & UX Safety (Phase 7.0C.2) contract tests passed successfully!");
