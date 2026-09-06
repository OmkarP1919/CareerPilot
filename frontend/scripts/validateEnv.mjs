#!/usr/bin/env node
// Build-time validation of the frontend production environment (Phase 5E.10).
//
// Called from vite.config.js during `vite build` (production mode). It makes
// two guarantees:
//
//   1. A production build NEVER silently points at a local origin: if
//      VITE_API_BASE_URL is absent the build FAILS with a clear message.
//   2. If VITE_API_BASE_URL is set but still points at localhost/127.0.0.1, the
//      build prints a loud warning and continues. It does not hard-fail so that
//      local `npm run build && npm run preview` workflows keep working, but a
//      production bundle with a localhost API origin is never built silently.
//
// Nothing in this file is a secret and nothing here is exposed to the browser.
// VITE_* values (including VITE_API_BASE_URL) are public by design.

import { URL } from "node:url";

const LOCALHOST_HOSTNAMES = new Set(["localhost", "127.0.0.1", "::1"]);

export function baseUrlFor(env) {
  const v = env && env.VITE_API_BASE_URL;
  return typeof v === "string" ? v.trim() : "";
}

export function isLocalhostUrl(raw) {
  try {
    return LOCALHOST_HOSTNAMES.has(new URL(raw).hostname);
  } catch {
    return false;
  }
}

export function validateProductionEnv(env) {
  const url = baseUrlFor(env);

  if (!url) {
    throw new Error(
      [
        "VITE_API_BASE_URL is required for production builds.",
        "Set it to your deployed HTTPS backend origin, for example:",
        "  VITE_API_BASE_URL=https://api.careerpilot.app",
        "Then run: npm run build",
        "See frontend/.env.example and frontend/docs/deployment.md for details.",
      ].join("\n"),
    );
  }

  if (isLocalhostUrl(url)) {
    console.warn(
      [
        "\n[careerpilot] VITE_API_BASE_URL points at a LOCAL origin:",
        `  ${url}`,
        "A production bundle must target the deployed HTTPS backend,",
        "e.g. VITE_API_BASE_URL=https://api.careerpilot.app.",
        "This build continues so local preview builds keep working, but it is",
        "NOT a production-ready bundle while it references localhost.\n",
      ].join("\n"),
    );
  }
}