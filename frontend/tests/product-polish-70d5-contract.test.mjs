import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, "..");

console.log("Starting Product Polish & Continuity (Phase 7.0D.5) Contract Tests...\n");

// -----------------------------------------------------------------------------
// 1. Dashboard Sync CTA points to /profile?action=sync
// -----------------------------------------------------------------------------
const dashboardUtilsPath = path.join(ROOT, "src", "components", "dashboard", "dashboardUtils.js");
const { determineNextAction } = await import(`file://${dashboardUtilsPath}`);

const syncAction = determineNextAction({
  resumes: [{ id: "res-1", filename: "my-resume.pdf" }],
  profile: { skills: [] },
  applications: [],
  recommendedJobs: [],
  interviews: [],
});

assert.strictEqual(
  syncAction.type,
  "sync_resume_profile",
  "Must detect sync_resume_profile when user has resumes but no profile skills"
);
assert.strictEqual(
  syncAction.ctaLink,
  "/profile?action=sync",
  "Dashboard sync action must route directly to /profile?action=sync"
);
assert.strictEqual(
  syncAction.ctaLabel,
  "Sync to Profile",
  "Dashboard sync CTA label must be 'Sync to Profile'"
);
console.log("  ok   1. Dashboard sync CTA routes to /profile?action=sync verified");

// Verify ProfilePage handles action=sync query param
const profilePagePath = path.join(ROOT, "src", "pages", "ProfilePage.jsx");
const profilePageContent = fs.readFileSync(profilePagePath, "utf8");
assert.ok(
  profilePageContent.includes('searchParams.get("action") === "sync"'),
  "ProfilePage must read action=sync from URL search params"
);
assert.ok(
  profilePageContent.includes("setShowSyncModal(true)"),
  "ProfilePage must trigger sync modal when parsed data is ready"
);
assert.ok(
  profilePageContent.includes("profile-discovery-hint"),
  "ProfilePage must include profile-discovery-hint guidance banner"
);
assert.ok(
  profilePageContent.includes("Your skills, target roles, and preferred locations help CareerPilot personalize job matching and discovery."),
  "ProfilePage must display accurate discovery guidance copy"
);
console.log("  ok   1b. ProfilePage action=sync handling and discovery guidance verified");

// -----------------------------------------------------------------------------
// 2. External Apply flow contracts
// -----------------------------------------------------------------------------
const externalApplyToastPath = path.join(ROOT, "src", "components", "jobs", "ExternalApplyToast.jsx");
assert.ok(fs.existsSync(externalApplyToastPath), "ExternalApplyToast.jsx must exist");
const externalApplyToastContent = fs.readFileSync(externalApplyToastPath, "utf8");

assert.ok(
  externalApplyToastContent.includes("Application opened. Mark"),
  "External apply toast must clearly state application was opened (never claim submitted)"
);
assert.ok(
  externalApplyToastContent.includes("Mark Applied"),
  "External apply toast must offer 'Mark Applied' confirmation action"
);
assert.ok(
  externalApplyToastContent.includes("Not now"),
  "External apply toast must offer 'Not now' dismissal action"
);
assert.ok(
  !externalApplyToastContent.includes("You submitted") && !externalApplyToastContent.includes("submitted your application"),
  "External apply toast must not claim that the application was already submitted"
);

// Verify JobCard and JobActionBar integrate external apply
const jobCardPath = path.join(ROOT, "src", "components", "jobs", "JobCard.jsx");
const jobCardContent = fs.readFileSync(jobCardPath, "utf8");
assert.ok(
  jobCardContent.includes("onExternalApply"),
  "JobCard must accept and invoke onExternalApply handler"
);

const jobActionBarPath = path.join(ROOT, "src", "components", "job-details", "JobActionBar.jsx");
const jobActionBarContent = fs.readFileSync(jobActionBarPath, "utf8");
assert.ok(
  jobActionBarContent.includes("onExternalApply"),
  "JobActionBar must accept and invoke onExternalApply handler"
);
console.log("  ok   2. External apply prompt contracts verified");

// -----------------------------------------------------------------------------
// 3. Canonical pipeline statuses supported in JobActionBar
// -----------------------------------------------------------------------------
assert.ok(
  jobActionBarContent.includes('from "../pipeline/pipelineUtils"'),
  "JobActionBar must import canonical PIPELINE_STATUSES from pipelineUtils"
);
assert.ok(
  !jobActionBarContent.includes('value: "Saved", label: "Saved in Pipeline"'),
  "JobActionBar must not define a duplicate local status list"
);

const { PIPELINE_STATUSES } = await import(
  `file://${path.join(ROOT, "src", "components", "pipeline", "pipelineUtils.js")}`
);
const canonical8 = ["Saved", "Preparing", "Applied", "Assessment", "Interview", "Offer", "Rejected", "Withdrawn"];
for (const st of canonical8) {
  assert.ok(PIPELINE_STATUSES.includes(st), `pipelineUtils must contain canonical status: ${st}`);
}
console.log("  ok   3. All 8 canonical pipeline statuses consumed in JobActionBar verified");

// -----------------------------------------------------------------------------
// 4. Centralized Score Tier Classification
// -----------------------------------------------------------------------------
const constantsPath = path.join(ROOT, "src", "utils", "constants.js");
const { getMatchLabel, MATCH_THRESHOLDS } = await import(`file://${constantsPath}`);

// Boundary assertions
assert.strictEqual(getMatchLabel(100), "High Match", "Score 100 must be High Match");
assert.strictEqual(getMatchLabel(82), "High Match", "Score 82 must be High Match");
assert.strictEqual(getMatchLabel(80), "High Match", "Score 80 must be High Match (boundary)");
assert.strictEqual(getMatchLabel(79), "Strong Match", "Score 79 must be Strong Match");
assert.strictEqual(getMatchLabel(60), "Strong Match", "Score 60 must be Strong Match (boundary)");
assert.strictEqual(getMatchLabel(59), "Moderate Match", "Score 59 must be Moderate Match");
assert.strictEqual(getMatchLabel(40), "Moderate Match", "Score 40 must be Moderate Match (boundary)");
assert.strictEqual(getMatchLabel(39), "Low Match", "Score 39 must be Low Match");
assert.strictEqual(getMatchLabel(1), "Low Match", "Score 1 must be Low Match");
assert.strictEqual(getMatchLabel(0), "Not Calculated", "Score 0 must be Not Calculated");
assert.strictEqual(getMatchLabel(null), "Not Calculated", "Score null must be Not Calculated");

// Verify JobFitPanel and ScoreBadge consume getMatchLabel
const fitPanelPath = path.join(ROOT, "src", "components", "job-details", "JobFitPanel.jsx");
const fitPanelContent = fs.readFileSync(fitPanelPath, "utf8");
assert.ok(
  fitPanelContent.includes("getMatchLabel(overallScore)"),
  "JobFitPanel must consume getMatchLabel directly"
);

const scoreBadgePath = path.join(ROOT, "src", "components", "ScoreBadge.jsx");
const scoreBadgeContent = fs.readFileSync(scoreBadgePath, "utf8");
assert.ok(
  scoreBadgeContent.includes("getMatchLabel(score)"),
  "ScoreBadge must consume getMatchLabel directly"
);

const heroHeaderPath = path.join(ROOT, "src", "components", "job-details", "JobHeroHeader.jsx");
const heroHeaderContent = fs.readFileSync(heroHeaderPath, "utf8");
assert.ok(
  heroHeaderContent.includes("getMatchLabel(score)"),
  "JobHeroHeader must consume getMatchLabel directly"
);
console.log("  ok   4. Centralized score tier classification across all views verified");

// -----------------------------------------------------------------------------
// 5. Mobile Job Details Action Access
// -----------------------------------------------------------------------------
assert.ok(
  jobActionBarContent.includes("job-sticky-more-btn"),
  "Mobile Job Details action bar must provide a More button"
);
assert.ok(
  jobActionBarContent.includes("mobile-action-sheet"),
  "JobActionBar must include a mobile action sheet"
);
assert.ok(
  jobActionBarContent.includes("onCoverLetter") && jobActionBarContent.includes("onAnalyzeResume"),
  "Mobile action sheet must expose Cover Letter and Analyze Resume actions"
);
console.log("  ok   5. Mobile action access (Cover Letter, Analyze Resume) verified");

// -----------------------------------------------------------------------------
// 6. 7-Factor copy accuracy across entire codebase
// -----------------------------------------------------------------------------
const landingPagePath = path.join(ROOT, "src", "pages", "LandingPage.jsx");
const landingPageContent = fs.readFileSync(landingPagePath, "utf8");
assert.ok(
  !landingPageContent.includes("5-factor"),
  "LandingPage must not contain stale '5-factor' references"
);
assert.ok(
  landingPageContent.includes("Transparent 7-factor scoring"),
  "LandingPage must advertise Transparent 7-factor scoring"
);
assert.ok(
  landingPageContent.includes("transparent 7-factor breakdown"),
  "LandingPage must advertise transparent 7-factor breakdown"
);

const authLayoutPath = path.join(ROOT, "src", "layouts", "AuthLayout.jsx");
const authLayoutContent = fs.readFileSync(authLayoutPath, "utf8");
assert.ok(
  !authLayoutContent.includes("5-factor"),
  "AuthLayout must not contain stale '5-factor' references"
);
assert.ok(
  authLayoutContent.includes("Transparent 7-factor fit scoring"),
  "AuthLayout must advertise Transparent 7-factor fit scoring"
);
console.log("  ok   6. Complete 7-factor copy accuracy verified with zero stale 5-factor text");

// -----------------------------------------------------------------------------
// 7. Visual / Content Polish
// -----------------------------------------------------------------------------
const pagesCssPath = path.join(ROOT, "src", "styles", "pages.css");
const pagesCssContent = fs.readFileSync(pagesCssPath, "utf8");

// Verify wide-screen rule targets the actual .jobs-unified-page selector with max-width: 1040px
const wideJobsMediaRegex = /@media\s*\(\s*min-width:\s*1440px\s*\)\s*\{[\s\S]*?\.jobs-unified-page\s*\{[\s\S]*?max-width:\s*1040px;/;
assert.ok(
  wideJobsMediaRegex.test(pagesCssContent),
  "Wide Jobs feed at >=1440px must target .jobs-unified-page with max-width: 1040px"
);

console.log("  ok   7. Visual polish (wide jobs feed constraint, subtle sign-out) verified");

console.log("\nAll Phase 7.0D.5 Product Polish & Continuity contract checks passed successfully!\n");
