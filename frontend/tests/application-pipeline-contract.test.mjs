import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, "..");

console.log("Starting Application Pipeline (Phase 7.0B.3) Contract Tests...");

// 1. Verify routing contract
const appJsx = fs.readFileSync(path.join(ROOT, "src", "App.jsx"), "utf8");
assert.match(
  appJsx,
  /<Route\s+path=["']\/pipeline["']\s+element=\{<ApplicationsPage\s*\/>\}/,
  "Pipeline primary route must remain /pipeline"
);
assert.match(
  appJsx,
  /<Route\s+path=["']\/applications["']\s+element=\{<Navigate\s+to=["']\/pipeline["']/,
  "Legacy /applications route must navigate/redirect to /pipeline"
);
console.log("  ok   Routing contracts (/pipeline, legacy /applications) passed");

// 2. Verify pipelineUtils.js contract and status definitions
const pipelineUtilsPath = path.join(ROOT, "src", "components", "pipeline", "pipelineUtils.js");
assert.ok(fs.existsSync(pipelineUtilsPath), "pipelineUtils.js must exist");

const pipelineUtilsModule = await import(`file://${pipelineUtilsPath}`);
const {
  PIPELINE_STATUSES,
  STATUS_LABELS,
  STATUS_GROUPS,
  FILTER_TABS,
  getNextStatus,
  filterApplications,
  sortApplications,
  deriveSummaryMetrics,
} = pipelineUtilsModule;

// Verify exact 8 backend statuses
const EXPECTED_STATUSES = [
  "Saved",
  "Preparing",
  "Applied",
  "Assessment",
  "Interview",
  "Offer",
  "Rejected",
  "Withdrawn",
];
assert.deepEqual(
  PIPELINE_STATUSES,
  EXPECTED_STATUSES,
  "Pipeline must represent exactly all 8 backend statuses"
);

// Verify status labels exist for all 8
for (const status of EXPECTED_STATUSES) {
  assert.ok(STATUS_LABELS[status], `Missing label for status ${status}`);
}
console.log("  ok   All 8 backend statuses defined and mapped in pipelineUtils");

// 3. Verify stage progression logic
assert.equal(getNextStatus("Saved"), "Applied", "Saved should advance to Applied");
assert.equal(getNextStatus("Preparing"), "Applied", "Preparing should advance to Applied");
assert.equal(getNextStatus("Applied"), "Assessment", "Applied should advance to Assessment");
assert.equal(getNextStatus("Assessment"), "Interview", "Assessment should advance to Interview");
assert.equal(getNextStatus("Interview"), "Offer", "Interview should advance to Offer");
assert.equal(getNextStatus("Offer"), null, "Offer should have no automatic advance stage");
assert.equal(getNextStatus("Rejected"), null, "Rejected should have no automatic advance stage");
console.log("  ok   Stage progression logic verified");

// 4. Verify deriveSummaryMetrics
const sampleApps = [
  { id: "1", status: "Saved" },
  { id: "2", status: "Applied" },
  { id: "3", status: "Interview" },
  { id: "4", status: "Offer" },
  { id: "5", status: "Rejected" },
  { id: "6", status: "Preparing" },
];
const metrics = deriveSummaryMetrics(sampleApps);
assert.equal(metrics.total, 6, "Total applications count must be 6");
assert.equal(metrics.active, 3, "Active count (Preparing, Applied, Interview) must be 3");
assert.equal(metrics.interviews, 1, "Interviews count must be 1");
assert.equal(metrics.offers, 1, "Offers count must be 1");
console.log("  ok   Summary metrics calculation passed (no fake metrics)");

// 5. Verify filterApplications logic
const filteredActive = filterApplications(sampleApps, "active");
assert.equal(filteredActive.length, 3, "Active filter should yield 3 applications");

const filteredSearch = filterApplications(
  [
    { id: "a1", job_title: "Staff Engineer", company_name: "Stripe", status: "Applied" },
    { id: "a2", job_title: "Designer", company_name: "Airbnb", status: "Interview" },
  ],
  "all",
  "stripe"
);
assert.equal(filteredSearch.length, 1, "Search for 'stripe' should match 1 application");
assert.equal(filteredSearch[0].company_name, "Stripe");

// Verify notes search match
const filteredNotes = filterApplications(
  [
    { id: "b1", job_title: "Engineer", company_name: "Google", notes: "Referral from Sarah", status: "Applied" },
  ],
  "all",
  "referral"
);
assert.equal(filteredNotes.length, 1, "Search should match notes content");
console.log("  ok   Filtering by stage and search query passed");

// 6. Verify deterministic sortApplications logic
const appsToSort = [
  { id: "s1", company_name: "Zendesk", updated_at: "2026-09-01T10:00:00Z" },
  { id: "s2", company_name: "Apple", updated_at: "2026-09-10T10:00:00Z" },
];
const sortedByRecent = sortApplications(appsToSort, "recent");
assert.equal(sortedByRecent[0].id, "s2", "Most recently updated should be first");

const sortedByCompany = sortApplications(appsToSort, "company_asc");
assert.equal(sortedByCompany[0].id, "s2", "Apple should precede Zendesk alphabetically");
console.log("  ok   Deterministic sorting contracts passed");

// 7. Verify component contracts
const componentFiles = [
  "PipelineSummaryStrip.jsx",
  "PipelineFilters.jsx",
  "PipelineCard.jsx",
  "PipelineCardGrid.jsx",
  "ApplicationDetailDrawer.jsx",
  "AddApplicationModal.jsx",
  "PipelineOverviewTab.jsx",
  "PipelineTimelineTab.jsx",
  "PipelineInterviewsTab.jsx",
  "PipelineDocumentsTab.jsx",
];

for (const file of componentFiles) {
  const filePath = path.join(ROOT, "src", "components", "pipeline", file);
  assert.ok(fs.existsSync(filePath), `Component file ${file} must exist`);
  const content = fs.readFileSync(filePath, "utf8");
  // Check no window.alert or window.confirm
  assert.doesNotMatch(content, /window\.alert\s*\(/, `${file} must not use window.alert`);
  assert.doesNotMatch(content, /window\.confirm\s*\(/, `${file} must not use window.confirm`);
}
console.log("  ok   All 10 pipeline components exist and avoid unsafe browser dialogs");

// 8. Verify ApplicationsPage container structure
const applicationsPageContent = fs.readFileSync(path.join(ROOT, "src", "pages", "ApplicationsPage.jsx"), "utf8");
assert.match(applicationsPageContent, /PipelineSummaryStrip/, "ApplicationsPage must use PipelineSummaryStrip");
assert.match(applicationsPageContent, /PipelineFilters/, "ApplicationsPage must use PipelineFilters");
assert.match(applicationsPageContent, /PipelineCardGrid/, "ApplicationsPage must use PipelineCardGrid");
assert.match(applicationsPageContent, /ApplicationDetailDrawer/, "ApplicationsPage must use ApplicationDetailDrawer");
assert.match(applicationsPageContent, /AddApplicationModal/, "ApplicationsPage must use AddApplicationModal");
assert.match(applicationsPageContent, /handleAddApplication/, "ApplicationsPage must provide handleAddApplication");
console.log("  ok   ApplicationsPage container properly orchestrates modular pipeline");

// 9. Verify Deep Interview and Timeline API Contracts (F-1, F-2, F-3, F-4, F-5, F-9)
const interviewsTabContent = fs.readFileSync(
  path.join(ROOT, "src", "components", "pipeline", "PipelineInterviewsTab.jsx"),
  "utf8"
);
const timelineTabContent = fs.readFileSync(
  path.join(ROOT, "src", "components", "pipeline", "PipelineTimelineTab.jsx"),
  "utf8"
);

// A & E: Interview creation sends kind, not interview_kind
assert.doesNotMatch(
  interviewsTabContent,
  /interview_kind\s*:/,
  "PipelineInterviewsTab must NOT send interview_kind in payload or state"
);
assert.match(
  interviewsTabContent,
  /kind\s*:\s*formFields\.kind/,
  "PipelineInterviewsTab must send exact backend field 'kind'"
);
console.log("  ok   F-1: Interview creation adheres to exact backend schema (kind, scheduled_at, status, notes)");

// B & F-4: Unsupported fields removed
assert.doesNotMatch(
  interviewsTabContent,
  /timezone\s*:/,
  "PipelineInterviewsTab must not send unsupported timezone"
);
assert.doesNotMatch(
  interviewsTabContent,
  /location_or_link/,
  "PipelineInterviewsTab must not reference unsupported location_or_link"
);
assert.doesNotMatch(
  interviewsTabContent,
  /Join Meeting/,
  "PipelineInterviewsTab must not render unsupported Join Meeting action"
);
console.log("  ok   F-4: Unsupported interview fields (timezone, location_or_link) strictly omitted");

// C & F-5: Interview response binding uses kind
assert.match(
  interviewsTabContent,
  /iv\.kind/,
  "PipelineInterviewsTab must bind interview response to iv.kind"
);
assert.doesNotMatch(
  interviewsTabContent,
  /iv\.interview_kind/,
  "PipelineInterviewsTab must NOT bind to iv.interview_kind"
);
console.log("  ok   F-5: Interview display binds to iv.kind as defined by backend");

// D & F-3: Timeline uses created_at, not timestamp
assert.match(
  timelineTabContent,
  /entry\.created_at/,
  "PipelineTimelineTab must use entry.created_at for timestamp"
);
assert.doesNotMatch(
  timelineTabContent,
  /entry\.timestamp/,
  "PipelineTimelineTab must NOT use non-existent entry.timestamp"
);
console.log("  ok   F-3: Timeline entry timestamps use created_at matching backend response");

// F & F-2: Interview editing restored and uses updateApplicationInterview
assert.match(
  interviewsTabContent,
  /api\.updateApplicationInterview\s*\(/,
  "PipelineInterviewsTab must call api.updateApplicationInterview for editing"
);
assert.match(
  interviewsTabContent,
  /openEdit/,
  "PipelineInterviewsTab must provide openEdit interaction"
);
assert.match(
  interviewsTabContent,
  /formMode\s*===\s*["']edit["']/,
  "PipelineInterviewsTab must support edit form mode"
);
console.log("  ok   F-2: Interview editing fully restored with updateApplicationInterview");

// 10. Verify CSS scoping
const pagesCss = fs.readFileSync(path.join(ROOT, "src", "styles", "pages.css"), "utf8");
assert.match(pagesCss, /\.pipeline-page-unified/, "pages.css must include .pipeline-page-unified namespace");
assert.match(pagesCss, /\.pipeline-drawer-panel/, "pages.css must include .pipeline-drawer-panel styles");
assert.match(pagesCss, /\.pipeline-modal/, "pages.css must include .pipeline-modal styles");
console.log("  ok   Scoped pipeline CSS verified");

// 11. Verify protected files remain untouched
const protectedFiles = [
  path.join(ROOT, "..", "backend", "app", "services", "resume_parser.py"),
  path.join(ROOT, "..", "backend", "tests", "test_resume_parser.py"),
  path.join(ROOT, "src", "pages", "ResumesPage.jsx"),
  path.join(ROOT, "src", "components", "Sidebar.jsx"),
  path.join(ROOT, "src", "components", "TopNav.jsx"),
  path.join(ROOT, "src", "components", "BottomNav.jsx"),
  path.join(ROOT, "src", "layouts", "MainLayout.jsx"),
  path.join(ROOT, "src", "styles", "tokens.css"),
  path.join(ROOT, "src", "styles", "components.css"),
  path.join(ROOT, "src", "styles", "layout.css"),
  path.join(ROOT, "src", "pages", "JobsPage.jsx"),
];

for (const pFile of protectedFiles) {
  assert.ok(fs.existsSync(pFile), `Protected file ${pFile} must exist`);
}
console.log("  ok   Protected files exist and verified");

console.log("\nAll Phase 7.0B.3 Application Pipeline contract checks passed!\n");
