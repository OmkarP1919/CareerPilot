#!/usr/bin/env node
// Focused deployment-configuration contract checks for the frontend
// (Phase 5E.10).
//
// Follows the repository's existing no-framework pattern (see
// tests/resume-contract.mjs): a plain Node script that imports the real
// modules and asserts behavior. Covers:
//
//   1. API base URL resolved from VITE_API_BASE_URL (+ documented dev default)
//   2. Trailing slash normalization
//   3. Production configuration never quietly points at localhost
//   4. A missing production API URL fails the build clearly
//   5. API requests use the configured backend origin (single-slash join,
//      no /api prefix, no relative routing/proxy assumptions)
//   6. Firebase public config is read from VITE_FIREBASE_* variables
//   7. No secrets are exposed through frontend env configuration

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

import {
  API_BASE_URL,
  DEFAULT_API_BASE_URL,
  normalizeBaseUrl,
  joinApiUrl,
  isLocalhostBaseUrl,
} from "../src/services/apiConfig.js";
import {
  baseUrlFor,
  isLocalhostUrl,
  validateProductionEnv,
} from "../scripts/validateEnv.mjs";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const apiSource = readFileSync(join(root, "src/services/api.js"), "utf8");
const firebaseSource = readFileSync(join(root, "src/firebase.js"), "utf8");
const envExample = readFileSync(join(root, ".env.example"), "utf8");
const viteConfig = readFileSync(join(root, "vite.config.js"), "utf8");

const failures = [];

function check(name, ok, hint = "") {
  if (ok) {
    console.log(`  ok   ${name}`);
  } else {
    failures.push(name);
    console.error(`  FAIL ${name}${hint ? ` -- ${hint}` : ""}`);
  }
}

// (1) API base URL resolution.
check(
  "default dev base URL is documented localhost",
  DEFAULT_API_BASE_URL.includes("localhost") || DEFAULT_API_BASE_URL.includes("127.0.0.1"),
  `expected a local dev default, got ${DEFAULT_API_BASE_URL}`,
);
check(
  "API_BASE_URL is resolved from the environment (trailing slash normalized)",
  typeof API_BASE_URL === "string" && !API_BASE_URL.endsWith("/"),
  "API_BASE_URL must be a normalized origin without a trailing slash",
);
check(
  "normalizeBaseUrl trims trailing slashes",
  normalizeBaseUrl("https://api.example.com///") === "https://api.example.com",
  "expected a single trailing-slash strip",
);

// (2) Trailing slash normalization guarantees no double-slash joins.
check(
  "joinApiUrl avoids // with a trailing-slash base",
  joinApiUrl("https://api.example.com/", "/jobs") === "https://api.example.com/jobs",
  "joined URL must have exactly one slash at the seam",
);
check(
  "joinApiUrl no /api prefix for root-based backend routes",
  joinApiUrl("https://api.example.com", "/jobs") === "https://api.example.com/jobs",
  "the backend exposes routes at the root; /api must NOT be inserted",
);

// (3) Production never (silently) points at localhost.
check(
  "isLocalhostUrl detects localhost origins",
  isLocalhostUrl("http://localhost:8000") && isLocalhostUrl("http://127.0.0.1:8000"),
  "expected localhost/127.0.0.1 to be flagged",
);
check(
  "isLocalhostBaseUrl flags local and NOT https production",
  isLocalhostBaseUrl("http://127.0.0.1:8000") && !isLocalhostBaseUrl("https://api.careerpilot.app"),
  "localhost detection must not misclassify a real HTTPS origin",
);

// (4) Missing production API URL fails clearly.
let threwForMissing = false;
try {
  validateProductionEnv({});
} catch (err) {
  threwForMissing = /VITE_API_BASE_URL is required/.test(err.message);
}
check(
  "missing VITE_API_BASE_URL fails the production build clearly",
  threwForMissing,
  "validateProductionEnv({}) must throw with a clear message",
);

// HTTPS (non-localhost) production URL passes validation (no throw).
let httpsPassed = false;
try {
  validateProductionEnv({ VITE_API_BASE_URL: "https://api.careerpilot.app" });
  httpsPassed = true;
} catch {
  httpsPassed = false;
}
check(
  "HTTPS production origin passes build validation",
  httpsPassed,
  "a real HTTPS origin must not be rejected",
);

// Vite actually invokes the validator for production builds only.
check(
  "vite.config.js calls validateProductionEnv for production builds only",
  /command === ['"]build['"] && mode === ['"]production['"]/.test(viteConfig) &&
    /validateProductionEnv\(env\)/.test(viteConfig),
  "expected a command==='build' && mode==='production' guard around validateProductionEnv",
);

// (5) API requests target the configured origin (no relative /api or proxy).
check(
  "api.js no longer hardcodes an origin or default",
  !/http:\/\/localhost/.test(apiSource) &&
    !/VITE_API_BASE_URL \|\|/.test(apiSource) &&
    /from ["'].\/apiConfig["']/.test(apiSource),
  "api.js must import the base URL and join helper from apiConfig",
);
check(
  "vite.config.js has no dev proxy defined",
  !/server[\s\S]*?proxy/.test(viteConfig),
  "the development proxy was removed; the API client uses an absolute origin",
);

// (6) Firebase public config read from VITE_FIREBASE_* variables.
const firebaseVars = [
  "VITE_FIREBASE_API_KEY",
  "VITE_FIREBASE_AUTH_DOMAIN",
  "VITE_FIREBASE_PROJECT_ID",
  "VITE_FIREBASE_STORAGE_BUCKET",
  "VITE_FIREBASE_MESSAGING_SENDER_ID",
  "VITE_FIREBASE_APP_ID",
];
check(
  "firebase.js reads all six VITE_FIREBASE_* values from the environment",
  firebaseVars.every((v) => firebaseSource.includes(`import.meta.env.${v}`)),
  "each Firebase browser config value must come from a VITE_FIREBASE_* env var",
);
check(
  "firebase.js does not hardcode Firebase config values",
  !/firebaseConfig = \{\s*apiKey:\s*["']AIza/.test(firebaseSource),
  "Firebase client values must not be hardcoded in firebase.js",
);

// (7) No secrets in frontend environment configuration.
const secretPatterns = [
  /AIza[0-9A-Za-z_-]{20,}/, // Firebase API key
  /["']type["']\s*:\s*["']service_account["']/, // a pasted service-account JSON
  /client_email["']?\s*:/, // a pasted service-account JSON
  /-----BEGIN [A-Z ]+PRIVATE KEY-----/,
  /postgres(ql)?:\/\/[^\s]+/,
  /sk-[0-9A-Za-z]{20,}/, // OpenAI-style secret
  /Bearer [0-9A-Za-z._-]{20,}/,
];
check(
  ".env.example contains no credential-shaped secrets",
  secretPatterns.every((re) => !re.test(envExample)),
  ".env.example must only contain empty placeholders, never real credentials",
);
check(
  "apiConfig.js and validateEnv.mjs contain no secrets",
  !secretPatterns.some(
    (re) => re.test(readFileSync(join(root, "src/services/apiConfig.js"), "utf8")) ||
      re.test(readFileSync(join(root, "scripts/validateEnv.mjs"), "utf8")),
  ),
  "deployment config modules must not embed credentials",
);
check(
  ".env.example documents that VITE_* values are public and never secrets",
  /VITE_\* values are PUBLIC/.test(envExample),
  "the env contract must state VITE_* values are public",
);

console.log("");
if (failures.length > 0) {
  console.error(`${failures.length} deployment contract check(s) FAILED`);
  process.exit(1);
}
console.log("All deployment configuration contract checks passed");