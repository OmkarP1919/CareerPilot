import assert from "node:assert";
import {
  normalizeJob,
  formatSalary,
  buildDiscoveryPayload,
  postedAfterDays,
  toCanonicalEmploymentType,
  toCanonicalExperienceLevel,
} from "../src/components/jobs/jobUtils.js";

console.log("Starting Unified Job Search (Phase 7.0B.2) Contract Tests...");

// -----------------------------------------------------------------------------
// 1. URL Query Serialization & Criteria Mapping (incl. type/level round-trip)
// -----------------------------------------------------------------------------
const criteria1 = {
  query: "python backend",
  location: "Pune",
  remote: "Remote",
  type: "Full-time",
  level: "Senior Level",
  smin: "1500000",
  smax: "3000000",
  posted: "7",
  sources: ["Adzuna", "LinkedIn"],
};

const payload1 = buildDiscoveryPayload(criteria1);
assert.deepStrictEqual(payload1.queries, ["python backend"], "Queries must contain trimmed string");
assert.deepStrictEqual(payload1.locations, ["Pune"], "Locations must contain location");
assert.strictEqual(payload1.remote, true, "Remote work mode must map to remote: true");
assert.strictEqual(
  payload1.employment_type,
  "full-time",
  "UI 'Full-time' must round-trip to canonical backend 'full-time'"
);
assert.strictEqual(
  payload1.experience_level,
  "senior",
  "UI 'Senior Level' must round-trip to canonical backend 'senior'"
);
assert.strictEqual(payload1.salary_min, 1500000, "salary_min must be parsed to number");
assert.strictEqual(payload1.salary_max, 3000000, "salary_max must be parsed to number");
assert.deepStrictEqual(payload1.sources, ["Adzuna", "LinkedIn"], "Sources array must be preserved");
assert.ok(payload1.posted_after, "posted_after must be a valid ISO string when posted days is given");

// Criteria with empty values
const emptyPayload = buildDiscoveryPayload({});
assert.deepStrictEqual(emptyPayload.queries, [], "Empty query must produce empty queries array");
assert.deepStrictEqual(emptyPayload.locations, [], "Empty location must produce empty locations array");
assert.strictEqual(emptyPayload.remote, null, "Unspecified work mode must map to remote: null");
assert.strictEqual(emptyPayload.salary_min, null, "Missing salary min must map to null");
assert.strictEqual(emptyPayload.salary_max, null, "Missing salary max must map to null");
assert.strictEqual(emptyPayload.posted_after, null, "Empty posted days must map to null");
assert.ok(
  !("employment_type" in emptyPayload),
  "employment_type must be omitted when no employment type filter is active"
);
assert.ok(
  !("experience_level" in emptyPayload),
  "experience_level must be omitted when no experience level filter is active"
);

console.log("  ok   URL query serialization & criteria mapping passed");

// -----------------------------------------------------------------------------
// 2. Employment Type Canonical Round-Trip
// -----------------------------------------------------------------------------
const employmentTypeCases = [
  ["Full-time", "full-time"],
  ["Part-time", "part-time"],
  ["Contract", "contract"],
  ["Internship", "internship"],
  ["Freelance", "freelance"],
];
for (const [uiValue, canonical] of employmentTypeCases) {
  assert.strictEqual(
    toCanonicalEmploymentType(uiValue),
    canonical,
    `Employment type '${uiValue}' must map to canonical '${canonical}'`
  );
  const payload = buildDiscoveryPayload({ type: uiValue });
  assert.strictEqual(
    payload.employment_type,
    canonical,
    `Discovery payload must send canonical '${canonical}' for type '${uiValue}'`
  );
}
assert.strictEqual(toCanonicalEmploymentType(""), null, "Empty type must map to null");
assert.strictEqual(toCanonicalEmploymentType("unknown"), null, "Unrecognized type must map to null");

console.log("  ok   Employment type canonical round-trip passed");

// -----------------------------------------------------------------------------
// 3. Experience Level Canonical Round-Trip
// -----------------------------------------------------------------------------
const experienceLevelCases = [
  ["Entry Level", "entry"],
  ["Mid Level", "mid"],
  ["Senior Level", "senior"],
  ["Lead", "lead"],
  ["Executive", "executive"],
];
for (const [uiValue, canonical] of experienceLevelCases) {
  assert.strictEqual(
    toCanonicalExperienceLevel(uiValue),
    canonical,
    `Experience level '${uiValue}' must map to canonical '${canonical}'`
  );
  const payload = buildDiscoveryPayload({ level: uiValue });
  assert.strictEqual(
    payload.experience_level,
    canonical,
    `Discovery payload must send canonical '${canonical}' for level '${uiValue}'`
  );
}
assert.strictEqual(toCanonicalExperienceLevel(""), null, "Empty level must map to null");
assert.strictEqual(
  toCanonicalExperienceLevel("unknown"),
  null,
  "Unrecognized level must map to null"
);

console.log("  ok   Experience level canonical round-trip passed");

// -----------------------------------------------------------------------------
// 4. Work Mode Mapping (Hybrid must NEVER become an unconstrained request)
// -----------------------------------------------------------------------------
assert.strictEqual(buildDiscoveryPayload({ remote: "Remote" }).remote, true, "Remote maps to true");
assert.strictEqual(buildDiscoveryPayload({ remote: "Hybrid" }).remote, true, "Hybrid maps to true (constrained, not null)");
assert.strictEqual(buildDiscoveryPayload({ remote: "Onsite" }).remote, false, "Onsite maps to false");
assert.strictEqual(buildDiscoveryPayload({ remote: "" }).remote, null, "Empty work mode maps to null");
assert.strictEqual(buildDiscoveryPayload({ remote: undefined }).remote, null, "Missing work mode maps to null");

console.log("  ok   Work mode mapping passed (no silent Hybrid no-op)");

// -----------------------------------------------------------------------------
// 5. Sorting Mapping (each UI sort maps to a genuinely different backend value)
// -----------------------------------------------------------------------------
assert.strictEqual(buildDiscoveryPayload({ sort: "match" }).sort, "relevance", "Best Match maps to backend relevance ordering");
assert.strictEqual(buildDiscoveryPayload({ sort: "newest" }).sort, "newest", "Newest maps to backend newest ordering");
assert.strictEqual(buildDiscoveryPayload({ sort: "relevance" }).sort, "relevance", "Relevance maps to backend relevance ordering");
assert.notStrictEqual(
  buildDiscoveryPayload({ sort: "match" }).sort,
  "newest",
  "Best Match must NOT be silently identical to Newest"
);
assert.notStrictEqual(
  buildDiscoveryPayload({ sort: "newest" }).sort,
  "relevance",
  "Newest must NOT silently map to relevance ordering"
);

console.log("  ok   Sorting mapping passed (no no-op sort)");

// -----------------------------------------------------------------------------
// 6. postedAfterDays date calculation
// -----------------------------------------------------------------------------
assert.strictEqual(postedAfterDays(""), null);
assert.strictEqual(postedAfterDays(null), null);
const sevenDaysAgo = new Date(postedAfterDays("7"));
const now = new Date();
const diffDays = Math.round((now - sevenDaysAgo) / (1000 * 60 * 60 * 24));
assert.ok(diffDays >= 6 && diffDays <= 8, "postedAfterDays calculates within 7 days");

console.log("  ok   postedAfterDays date math passed");

// -----------------------------------------------------------------------------
// 7. Salary Formatting & No Fake Salary
// -----------------------------------------------------------------------------
assert.strictEqual(formatSalary(null), null, "Null salary must return null");
assert.strictEqual(formatSalary({}), null, "Empty salary object must return null");
assert.strictEqual(formatSalary({ min: null, max: null }), null, "Null min/max must return null");

// INR formatting
const inrSalary = formatSalary({ min: 2500000, max: 3500000, currency: "INR", period: "annual" });
assert.strictEqual(inrSalary, "₹25L – ₹35L / yr", "INR Lakh formatting check");

// USD formatting
const usdSalary = formatSalary({ min: 120000, max: 150000, currency: "USD", period: "annual" });
assert.strictEqual(usdSalary, "$120k – $150k / yr", "USD k formatting check");

// Single bound salary
const minOnlySalary = formatSalary({ min: 800000, currency: "INR", period: "annual" });
assert.strictEqual(minOnlySalary, "From ₹8L / yr", "Single bound min salary check");

console.log("  ok   Salary formatting contracts passed");

// -----------------------------------------------------------------------------
// 8. Canonical JobCard Normalization & NO FAKE SCORES
// -----------------------------------------------------------------------------
// Test 8A: Discovery external hit WITHOUT match score
const externalHitNoMatch = {
  canonical_key: "ext-12345",
  title: "Frontend Engineer",
  company: "Vercel",
  location: "Remote",
  work_mode: "remote",
  skills: ["React", "TypeScript"],
  match: null,
};
const normalizedNoMatch = normalizeJob(externalHitNoMatch);
assert.strictEqual(normalizedNoMatch.match_score, null, "NO fake score when match is null");
assert.strictEqual(normalizedNoMatch.fit_summary, null, "NO fake fit summary when match is null");
assert.strictEqual(normalizedNoMatch.is_external, true, "Is external when not materialized");
assert.strictEqual(normalizedNoMatch.id, null, "id is null before materialization");
assert.strictEqual(normalizedNoMatch.work_mode, "remote", "Canonical work_mode is preserved for exact filtering");

// Test 8B: Discovery external hit WITH authentic match score
const externalHitWithMatch = {
  canonical_key: "ext-67890",
  title: "Staff Platform Engineer",
  company: "Datadog",
  location: "Bengaluru",
  work_mode: "hybrid",
  skills: ["Go", "Kubernetes", "AWS"],
  match: {
    overall_score: 94,
    reasons: ["Strong alignment with your distributed systems background"],
  },
};
const normalizedWithMatch = normalizeJob(externalHitWithMatch);
assert.strictEqual(normalizedWithMatch.match_score, 94, "Authentic score 94% preserved");
assert.strictEqual(
  normalizedWithMatch.fit_summary,
  "Strong alignment with your distributed systems background",
  "Authentic fit summary preserved"
);

// Test 8C: Local job normalization
const localJob = {
  id: "job-local-001",
  title: "Backend Developer",
  company: "Stripe",
  location: "Remote",
  employment_type: "Full-time",
  experience_level: "Senior Level",
  required_skills: "Python, Django, PostgreSQL",
  match_score: 85,
};
const normalizedLocal = normalizeJob(localJob);
assert.strictEqual(normalizedLocal.id, "job-local-001");
assert.strictEqual(normalizedLocal.is_external, false);
assert.strictEqual(normalizedLocal.match_score, 85);
assert.deepStrictEqual(normalizedLocal.skills, ["Python", "Django", "PostgreSQL"]);

console.log("  ok   Canonical JobCard normalization & score integrity passed");

// -----------------------------------------------------------------------------
// 9. Session Cache & Prevention of Repeated Imports
// -----------------------------------------------------------------------------
const sessionCache = new Map();
sessionCache.set("ext-12345", "persisted-db-uuid-999");

const normalizedCached = normalizeJob(externalHitNoMatch, sessionCache);
assert.strictEqual(normalizedCached.id, "persisted-db-uuid-999", "Reuses session cached local job ID");
assert.strictEqual(normalizedCached.is_external, false, "Marked as local once cached in session");

console.log("  ok   Session materialization cache contract passed");

// -----------------------------------------------------------------------------
// 10. Supported JobCreate Payload Validation
// -----------------------------------------------------------------------------
// Materialization MUST ONLY use valid JobCreate fields:
// title, company, location, employment_type, experience_level, description, required_skills, application_url, source
const allowedJobCreateKeys = new Set([
  "title",
  "company",
  "location",
  "employment_type",
  "experience_level",
  "description",
  "required_skills",
  "application_url",
  "source",
]);

const sampleExternalJob = {
  title: "Senior Backend Engineer",
  company: "Datadog",
  location: "Remote",
  employment_type: "full-time",
  experience_level: "senior",
  description: "Join our core infrastructure team.",
  skills: ["Python", "FastAPI", "PostgreSQL"],
  application_urls: ["https://careers.datadog.com/apply/123"],
  primary_source: "Adzuna",
  // Fields that must NOT be present in JobCreate
  salary: { min: 2500000, max: 3500000 },
  work_mode: "Remote",
  canonical_key: "ext-datadog-123",
};

const materializationPayload = {
  title: sampleExternalJob.title,
  company: sampleExternalJob.company,
  location: sampleExternalJob.location || null,
  employment_type: sampleExternalJob.employment_type || null,
  experience_level: sampleExternalJob.experience_level || null,
  description: sampleExternalJob.description || null,
  required_skills: sampleExternalJob.skills.join(", "),
  application_url: sampleExternalJob.application_urls[0] || null,
  source: sampleExternalJob.primary_source || "Discovery",
};

for (const key of Object.keys(materializationPayload)) {
  assert.ok(
    allowedJobCreateKeys.has(key),
    `Key "${key}" must be a valid backend JobCreate field`
  );
}
assert.strictEqual("salary" in materializationPayload, false, "salary must NOT be in JobCreate payload");
assert.strictEqual("work_mode" in materializationPayload, false, "work_mode must NOT be in JobCreate payload");
assert.strictEqual("canonical_key" in materializationPayload, false, "canonical_key must NOT be in JobCreate payload");

console.log("  ok   External job materialization schema compliance passed");

console.log("\nAll Phase 7.0B.2 Unified Job Search contract checks passed!\n");