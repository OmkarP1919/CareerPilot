#!/usr/bin/env node
// Static contract regression checks for the Resume upload/delete workflow.
//
// The frontend has no test runner (no vitest/jest), so these checks lock the
// upload/delete contract at the source level so a regression like "frontend
// posts to the nonexistent /resumes/upload again" cannot slip through build +
// lint alone.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const apiSource = readFileSync(join(root, "src/services/api.js"), "utf8");
const resumesSource = readFileSync(join(root, "src/pages/ResumesPage.jsx"), "utf8");

const failures = [];

function check(name, ok, hint = "") {
  if (ok) {
    console.log(`  ok   ${name}`);
  } else {
    failures.push(name);
    console.error(`  FAIL ${name}${hint ? ` -- ${hint}` : ""}`);
  }
}

console.log("Resume workflow contract checks\n");

// --- Upload contract: frontend must call the backend's real POST /resumes.
check(
  "upload calls POST /resumes (not /resumes/upload)",
  /uploadFile\(\s*["']\/resumes["']\s*,/.test(resumesSource) &&
    !/uploadFile\(\s*["']\/resumes\/upload/.test(resumesSource),
  "expected api.uploadFile('/resumes', ...) in ResumesPage.jsx",
);

// --- Upload success refreshes the on-screen resume list.
check(
  "upload success refetches the resume list",
  /await fetchResumes\(\)/.test(resumesSource),
  "expected await fetchResumes() after a successful upload",
);

// --- Upload errors are surfaced cleanly (not silently swallowed).
check(
  "upload errors notify the user",
  /notify\(err\.message \|\| "Failed to upload and parse resume\.", "error"\)/.test(
    resumesSource,
  ),
  "expected an error notification in the upload catch block",
);

// --- Delete: 204 responses must not be treated as JSON (would throw and turn a
// successful deletion into a visible failure).
check(
  "api handles HTTP 204 without trying to parse JSON",
  /response\.status === 204\s*\{?[\s\S]*?return null/.test(apiSource) &&
    apiSource.indexOf("response.status === 204") <
      apiSource.indexOf("return await response.json()"),
  "request() must short-circuit on 204 before response.json()",
);

// --- Delete success removes the item from the UI state.
check(
  "delete success removes the resume from state",
  /await api\.delete\(`\/resumes\/\$\{id\}`\)[\s\S]*?setResumes\(\(prev\) => prev\.filter/.test(
    resumesSource,
  ),
  "expected setResumes filter after the delete promise resolves",
);

// --- Delete failure must NOT remove the item from the UI state.
const deleteCatch = resumesSource.match(
  /const handleDeleteResume[\s\S]*?\n  \};/,
)?.[0];
check(
  "delete failure does not remove the item from state",
  Boolean(deleteCatch) &&
    !/setResumes\(/.test(deleteCatch.split("catch")[1] || "") &&
    /notify\("Failed to delete resume\.", "error"\)/.test(deleteCatch),
  "the delete catch block must only notify, never call setResumes",
);

console.log("");
if (failures.length > 0) {
  console.error(`${failures.length} contract check(s) FAILED`);
  process.exit(1);
}
console.log("All resume workflow contract checks passed");