import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const fitPanelPath = path.resolve(__dirname, '../src/components/job-details/JobFitPanel.jsx');
const fitPanelContent = fs.readFileSync(fitPanelPath, 'utf8');

console.log("Testing JobFitPanel 7.0D.3 Canonical Factor Contracts...");

// 1. Hardcoded legacy weights MUST NOT exist
const prohibitedWeights = ['50%', '20%', '15%', '10%', '5%'];
for (const w of prohibitedWeights) {
  assert.ok(
    !fitPanelContent.includes(`weight="${w}"`),
    `JobFitPanel must not contain hardcoded weight="${w}"`
  );
  assert.ok(
    !fitPanelContent.includes(`(${w})`),
    `JobFitPanel must not contain hardcoded (${w}) in explainer or labels`
  );
}

// 2. Explainer text must describe dynamic normalization without 5-factor formula
assert.ok(
  fitPanelContent.includes("weighted, dynamically normalized set of profile and job factors"),
  "JobFitPanel must explain dynamic normalization"
);
assert.ok(
  !fitPanelContent.includes("5-factor weighting model"),
  "JobFitPanel must not describe legacy 5-factor model"
);

// 3. FACTOR_LABELS must contain all canonical factors
const canonicalKeys = ['skills', 'experience', 'role', 'projects', 'location', 'education', 'work_mode'];
for (const key of canonicalKeys) {
  assert.ok(
    fitPanelContent.includes(key),
    `JobFitPanel must handle canonical factor key: ${key}`
  );
}

// 4. Overall score must directly display matchData.overall_score without frontend recalculation
assert.ok(
  fitPanelContent.includes("matchData?.overall_score"),
  "JobFitPanel must read matchData.overall_score directly"
);

// 5. Test dynamic factor rendering logic contract (simulated)
const FACTOR_LABELS = {
  skills: "Skills",
  experience: "Experience",
  role: "Role Alignment",
  projects: "Projects",
  location: "Location",
  education: "Education",
  work_mode: "Work Mode",
};

function getDisplayFactors(matchData) {
  return Array.isArray(matchData?.factors)
    ? matchData.factors
        .filter((f) => f && f.available === true && f.score !== null && f.score !== undefined)
        .map((f) => ({
          key: f.key,
          label: FACTOR_LABELS[f.key] || f.key,
          weight: f.weight,
          score: f.score,
        }))
    : [];
}

// Case A: Legacy/unavailable education and work_mode
const mockV2FactorsPartial = [
  { key: "skills", score: 85, weight: 35, available: true },
  { key: "experience", score: 70, weight: 20, available: true },
  { key: "role", score: 90, weight: 15, available: true },
  { key: "projects", score: 60, weight: 10, available: true },
  { key: "location", score: 100, weight: 10, available: true },
  { key: "education", score: 0, weight: 5, available: false },
  { key: "work_mode", score: null, weight: 5, available: false },
];

const renderedPartial = getDisplayFactors({ factors: mockV2FactorsPartial });
assert.strictEqual(renderedPartial.length, 5, "Unavailable factors must be omitted");
assert.ok(!renderedPartial.some((f) => f.key === "education"), "Education must not be rendered when available=false");
assert.ok(!renderedPartial.some((f) => f.key === "work_mode"), "Work mode must not be rendered when available=false");

// Case B: All factors available
const mockV2FactorsFull = [
  { key: "skills", score: 85, weight: 35, available: true },
  { key: "experience", score: 70, weight: 20, available: true },
  { key: "role", score: 90, weight: 15, available: true },
  { key: "projects", score: 60, weight: 10, available: true },
  { key: "location", score: 100, weight: 10, available: true },
  { key: "education", score: 80, weight: 5, available: true },
  { key: "work_mode", score: 100, weight: 5, available: true },
];

const renderedFull = getDisplayFactors({ factors: mockV2FactorsFull });
assert.strictEqual(renderedFull.length, 7, "All available factors must be rendered");

console.log("All JobFitPanel 7.0D.3 Canonical Factor Contracts passed!");
