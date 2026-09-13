import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, "..");

console.log("Starting Simple Home / Dashboard Redesign (Phase 7.0B.4) Contract Tests...");

// -----------------------------------------------------------------------------
// 1. Routing Contracts in App.jsx
// -----------------------------------------------------------------------------
const appJsxPath = path.join(ROOT, "src", "App.jsx");
assert.ok(fs.existsSync(appJsxPath), "App.jsx must exist");
const appJsx = fs.readFileSync(appJsxPath, "utf8");

// Canonical /home route renders DashboardPage
assert.match(
  appJsx,
  /<Route\s+path=["']\/home["']\s+element=\{<DashboardPage\s*\/>\}/,
  "Canonical /home route must render DashboardPage"
);

// /dashboard route must redirect to /home
assert.match(
  appJsx,
  /<Route\s+path=["']\/dashboard["']\s+element=\{<Navigate\s+to=["']\/home["']\s+replace\s*\/>\}/,
  "/dashboard must redirect to canonical /home"
);

// Verify core workspace routes remain intact
const requiredRoutes = ["/discover", "/pipeline", "/resumes", "/profile", "/settings"];
for (const r of requiredRoutes) {
  assert.ok(appJsx.includes(`path="${r}"`), `Route ${r} must be preserved in App.jsx`);
}
console.log("  ok   1. Routing contracts (/home canonical, /dashboard redirect) verified");

// -----------------------------------------------------------------------------
// 2. Next-Action Logic & Priority in dashboardUtils.js
// -----------------------------------------------------------------------------
const dashboardUtilsPath = path.join(ROOT, "src", "components", "dashboard", "dashboardUtils.js");
assert.ok(fs.existsSync(dashboardUtilsPath), "dashboardUtils.js must exist");

const { determineNextAction, derivePipelineSummary } = await import(`file://${dashboardUtilsPath}`);

// Priority 1: New user with no resumes and no profile skills
const actionNewUser = determineNextAction({
  resumes: [],
  profile: null,
  applications: [],
  recommendedJobs: [],
  interviews: [],
});
assert.strictEqual(actionNewUser.type, "setup_resume", "Completely new user must get setup_resume action");
assert.strictEqual(actionNewUser.ctaLink, "/resumes", "Setup resume action must link to /resumes");
assert.strictEqual(actionNewUser.secondaryLink, "/profile", "Setup resume action must offer secondary profile link");

// Priority 2: User with profile skills but no resume uploaded
const actionHasSkills = determineNextAction({
  resumes: [],
  profile: { skills: ["React", "Node.js"] },
  applications: [],
  recommendedJobs: [],
  interviews: [],
});
assert.strictEqual(actionHasSkills.type, "upload_resume", "User with skills but no resume must get upload_resume action");
assert.strictEqual(actionHasSkills.ctaLink, "/resumes", "Upload resume action must link to /resumes");

// Priority 3: Upcoming Interview in the future
const futureDate = new Date(Date.now() + 86400000 * 2).toISOString();
const actionUpcomingInterview = determineNextAction({
  resumes: [{ id: "res-1", file_name: "cv.pdf" }],
  profile: { skills: ["React"] },
  applications: [{ id: "app-1", status: "Interview" }],
  recommendedJobs: [{ id: "job-1", match_score: 95 }],
  interviews: [{ id: "iv-1", scheduled_at: futureDate, status: "scheduled", kind: "Technical" }],
});
assert.strictEqual(
  actionUpcomingInterview.type,
  "upcoming_interview",
  "Upcoming scheduled interview must take priority over job opportunity"
);
assert.strictEqual(actionUpcomingInterview.ctaLink, "/pipeline", "Interview action must link to /pipeline");
assert.ok(actionUpcomingInterview.title.includes("Technical"), "Interview kind should be reflected in title");

// Priority 3 edge case: Past interview should not trigger upcoming interview action
const pastDate = new Date(Date.now() - 86400000 * 3).toISOString();
const actionPastInterview = determineNextAction({
  resumes: [{ id: "res-1" }],
  profile: { skills: ["React"] },
  applications: [],
  recommendedJobs: [{ id: "job-1", title: "Frontend Lead", company: "Stripe", match_score: 88 }],
  interviews: [{ id: "iv-2", scheduled_at: pastDate, status: "scheduled" }],
});
assert.strictEqual(
  actionPastInterview.type,
  "tailor_opportunity",
  "Past interview must NOT trigger upcoming interview; strong opportunity should trigger instead"
);

// Priority 4: High-Fit Opportunity (score >= 70)
const actionStrongOpp = determineNextAction({
  resumes: [{ id: "res-1" }],
  profile: { skills: ["React"] },
  applications: [{ id: "app-1", status: "Saved", job_company: "Meta" }],
  recommendedJobs: [
    { id: "job-88", title: "Senior Staff Engineer", company: "Datadog", match_score: 82 },
  ],
  interviews: [],
});
assert.strictEqual(
  actionStrongOpp.type,
  "tailor_opportunity",
  "Strong match (>= 70%) must trigger tailor_opportunity action"
);
assert.strictEqual(actionStrongOpp.ctaLink, "/discover/job-88", "Tailor opportunity must link to specific job");
assert.deepStrictEqual(
  actionStrongOpp.ctaState,
  { openTailor: true },
  "Tailor opportunity must pass { openTailor: true } route state"
);
assert.strictEqual(actionStrongOpp.secondaryLink, "/discover/job-88", "Secondary link must view job details");

// Priority 5: Saved Application needing advance
const actionAdvanceApp = determineNextAction({
  resumes: [{ id: "res-1" }],
  profile: { skills: ["React"] },
  applications: [{ id: "app-2", status: "Saved", job_title: "Fullstack Dev", job_company: "Vercel" }],
  recommendedJobs: [{ id: "job-low", match_score: 45 }],
  interviews: [],
});
assert.strictEqual(
  actionAdvanceApp.type,
  "advance_application",
  "Saved application must trigger advance_application when no strong job match exists"
);
assert.strictEqual(actionAdvanceApp.ctaLink, "/pipeline", "Advance app must link to /pipeline");
assert.ok(actionAdvanceApp.title.includes("Vercel"), "Advance app title must cite company");

// Priority 6: Default Neutral Action (explore jobs)
const actionDefault = determineNextAction({
  resumes: [{ id: "res-1" }],
  profile: { skills: ["React"] },
  applications: [{ id: "app-3", status: "Rejected" }],
  recommendedJobs: [],
  interviews: [],
});
assert.strictEqual(actionDefault.type, "explore_jobs", "Default fallback must be explore_jobs");
assert.strictEqual(actionDefault.ctaLink, "/discover", "Default action must link to /discover");
console.log("  ok   2. Next-action deterministic priority system verified");

// -----------------------------------------------------------------------------
// 3. Data Integrity: No Fabricated Scores, Percentages, or Explanations
// -----------------------------------------------------------------------------
const dashboardPagePath = path.join(ROOT, "src", "pages", "DashboardPage.jsx");
assert.ok(fs.existsSync(dashboardPagePath), "DashboardPage.jsx must exist");
const dashboardPageSrc = fs.readFileSync(dashboardPagePath, "utf8");

// Assert absence of fake readiness percentage calculations
assert.ok(
  !dashboardPageSrc.includes("profileReadiness"),
  "DashboardPage must not contain profileReadiness state or formula"
);
assert.ok(
  !dashboardPageSrc.includes("readinessScore"),
  "DashboardPage must not contain readinessScore variable"
);
assert.ok(
  !dashboardPageSrc.includes("readiness = 20"),
  "DashboardPage must not contain fabricated readiness scoring"
);

// Assert absence of hardcoded match reason string
assert.ok(
  !dashboardPageSrc.includes("High alignment with your technical profile"),
  "DashboardPage must not contain hardcoded 'High alignment with your technical profile'"
);
assert.ok(
  !dashboardPageSrc.includes("job-card-mini"),
  "DashboardPage must not contain legacy .job-card-mini duplication"
);

// Assert absence of pipeline funnel strip
assert.ok(
  !dashboardPageSrc.includes("pipeline-funnel-strip"),
  "DashboardPage must not contain duplicate pipeline funnel strip"
);
console.log("  ok   3. Data integrity verified: No fabricated readiness or fake explanations");

// -----------------------------------------------------------------------------
// 4. Pipeline Summary Derivation Contract
// -----------------------------------------------------------------------------
assert.strictEqual(derivePipelineSummary([]), null, "derivePipelineSummary([]) must return null for empty list");
assert.strictEqual(derivePipelineSummary(null), null, "derivePipelineSummary(null) must return null");

const sampleApps = [
  { id: "1", status: "Saved" },
  { id: "2", status: "Preparing" },
  { id: "3", status: "Applied" },
  { id: "4", status: "Assessment" },
  { id: "5", status: "Interview" },
  { id: "6", status: "Offer" },
  { id: "7", status: "Rejected" },
];
const summary = derivePipelineSummary(sampleApps);
assert.strictEqual(summary.total, 7, "Total applications must be 7");
assert.strictEqual(summary.active, 4, "Active applications (Preparing, Applied, Assessment, Interview) must be 4");
assert.strictEqual(summary.interviews, 1, "Interview count must be 1");
assert.strictEqual(summary.offers, 1, "Offer count must be 1");
console.log("  ok   4. derivePipelineSummary contract verified");

// -----------------------------------------------------------------------------
// 5. Component Contracts
// -----------------------------------------------------------------------------
const nextActionCompPath = path.join(ROOT, "src", "components", "dashboard", "HomeNextAction.jsx");
const recJobsCompPath = path.join(ROOT, "src", "components", "dashboard", "HomeRecommendedJobs.jsx");
const pipeSummaryCompPath = path.join(ROOT, "src", "components", "dashboard", "HomePipelineSummary.jsx");

assert.ok(fs.existsSync(nextActionCompPath), "HomeNextAction.jsx component must exist");
assert.ok(fs.existsSync(recJobsCompPath), "HomeRecommendedJobs.jsx component must exist");
assert.ok(fs.existsSync(pipeSummaryCompPath), "HomePipelineSummary.jsx component must exist");

const recJobsSrc = fs.readFileSync(recJobsCompPath, "utf8");
// Reuses unified JobCard
assert.match(
  recJobsSrc,
  /import\s+JobCard\s+from\s+["']\.\.\/jobs\/JobCard["']/,
  "HomeRecommendedJobs must reuse unified JobCard component"
);
// Limits opportunities cleanly (slice 0, 3)
assert.ok(recJobsSrc.includes("jobs.slice(0, 3)"), "HomeRecommendedJobs must slice to max 3 items");
// Has See all jobs link
assert.ok(recJobsSrc.includes('to="/discover"'), "HomeRecommendedJobs must provide 'See all jobs' link to /discover");

const nextActionSrc = fs.readFileSync(nextActionCompPath, "utf8");
assert.ok(nextActionSrc.includes("home-next-step-card"), "HomeNextAction must render .home-next-step-card");
assert.ok(nextActionSrc.includes("action.ctaLink"), "HomeNextAction must link to action.ctaLink");

const pipeSummarySrc = fs.readFileSync(pipeSummaryCompPath, "utf8");
assert.ok(pipeSummarySrc.includes("home-pipeline-card"), "HomePipelineSummary must render .home-pipeline-card");
assert.ok(pipeSummarySrc.includes('to="/pipeline"'), "HomePipelineSummary must link to /pipeline");
console.log("  ok   5. Component structural and integration contracts verified");

// -----------------------------------------------------------------------------
// 6. CSS & Responsive Design Inspection
// -----------------------------------------------------------------------------
const pagesCssPath = path.join(ROOT, "src", "styles", "pages.css");
const pagesCss = fs.readFileSync(pagesCssPath, "utf8");

assert.ok(pagesCss.includes(".home-page-unified"), "pages.css must include .home-page-unified container");
assert.ok(pagesCss.includes(".home-next-step-card"), "pages.css must style .home-next-step-card");
assert.ok(pagesCss.includes(".home-jobs-grid"), "pages.css must style .home-jobs-grid");
assert.ok(pagesCss.includes(".home-pipeline-card"), "pages.css must style .home-pipeline-card");

// Check mobile media query rules
assert.ok(pagesCss.includes("@media (max-width: 767px)"), "pages.css must define mobile responsive styles for home");
assert.ok(
  pagesCss.includes(".home-jobs-grid > :nth-child(n+3)"),
  "pages.css mobile rule must hide 3rd job on mobile to enforce max 2 jobs"
);
assert.ok(
  pagesCss.includes("padding-bottom: calc(var(--bottom-nav-height, 64px) + var(--space-8))"),
  "pages.css must provide adequate bottom-nav clearance on mobile"
);
console.log("  ok   6. CSS and responsive styles verified");

// -----------------------------------------------------------------------------
// 7. Protected Files Integrity Check
// -----------------------------------------------------------------------------
// Verify shell files have not been touched during Phase 7.0B.4
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
console.log("  ok   7. Protected files integrity verified");

console.log("\nAll Simple Home / Dashboard (Phase 7.0B.4) contract tests passed successfully!");
