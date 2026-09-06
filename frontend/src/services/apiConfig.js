// Centralized API base URL configuration (Phase 5E.10).
//
// The frontend talks to a single backend origin. That origin is configured at
// build time through VITE_API_BASE_URL and baked into the static bundle by
// Vite. Every API request is built from this one place so the origin, trailing
// slash, and endpoint joins are normalized exactly once.
//
// SECURITY NOTE: VITE_* values are PUBLIC. They are compiled into the bundle
// that any visitor can read. The API base URL and the Firebase browser config
// are intended to be public. Never place a secret (backend API key, Firebase
// service account, database URL, JWT secret, etc.) in a VITE_* variable.

export const DEFAULT_API_BASE_URL = "http://localhost:8000";

// Strip trailing slashes so a base like "https://api.example.com/" can never
// produce "https://api.example.com//jobs".
export function normalizeBaseUrl(raw) {
  if (typeof raw !== "string") return "";
  const url = raw.trim();
  if (!url) return "";
  return url.replace(/\/+$/, "");
}

const LOCALHOST_HOSTNAMES = new Set(["localhost", "127.0.0.1", "::1"]);

export function isLocalhostBaseUrl(raw) {
  const url = normalizeBaseUrl(raw);
  if (!url) return false;
  try {
    return LOCALHOST_HOSTNAMES.has(new URL(url).hostname);
  } catch {
    return false;
  }
}

// Join an endpoint path onto a base URL, guaranteeing exactly one slash at the
// seam. The backend exposes its routers at the root (no /api prefix):
// /jobs, /resumes, /applications, /analytics, ... so no prefix is inserted.
export function joinApiUrl(baseUrl, endpoint) {
  const base = normalizeBaseUrl(baseUrl);
  if (!base) return endpoint || "";
  let path = (endpoint || "").trim();
  if (!path) return base;
  if (!path.startsWith("/")) path = `/${path}`;
  return `${base}${path}`;
}

// Environment-driven base URL (safe to import outside Vite, e.g. in the
// frontend's node contract tests).
const rawBaseUrl =
  typeof import.meta.env !== "undefined" &&
  typeof import.meta.env.VITE_API_BASE_URL === "string"
    ? import.meta.env.VITE_API_BASE_URL
    : undefined;

export const API_BASE_URL = normalizeBaseUrl(rawBaseUrl || DEFAULT_API_BASE_URL);