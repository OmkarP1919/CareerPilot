import { auth } from "../firebase";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const DEFAULT_TIMEOUT_MS = 120_000;
const DISCOVERY_TIMEOUT_MS = 90_000;

const GENERIC_SERVER_MESSAGE = "Something went wrong. Please try again.";

export class ApiError extends Error {
  constructor(kind, message, status = null) {
    super(message);
    this.name = "ApiError";
    this.kind = kind; // "timeout" | "auth" | "forbidden" | "server" | "network" | "http"
    this.status = status;
  }
}

function sanitizeDetail(detail) {
  if (typeof detail !== "string" || !detail.trim()) return null;
  if (detail.includes("Traceback") || detail.includes("\n")) return null;
  return detail.trim();
}

async function getToken() {
  const user = auth.currentUser;
  if (!user) return null;
  return user.getIdToken();
}

async function request(endpoint, options = {}, timeoutMs = DEFAULT_TIMEOUT_MS) {
  const fullUrl = `${API_BASE_URL}${endpoint}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    let token;
    try {
      token = await getToken();
    } catch {
      throw new ApiError("network", "Unable to reach the authentication service. Please try again.");
    }

    const headers = {
      ...options.headers,
    };

    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    if (!(options.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
    }

    const response = await fetch(fullUrl, {
      ...options,
      headers,
      signal: controller.signal,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      const detail = sanitizeDetail(error.detail);

      if (response.status === 401) {
        throw new ApiError("auth", detail || "Your session has expired. Please sign in again.", 401);
      }
      if (response.status === 403) {
        throw new ApiError("forbidden", detail || "You don't have permission to do that.", 403);
      }
      if (response.status === 408 || response.status === 504) {
        throw new ApiError("timeout", detail || "The request timed out. Please try again.", response.status);
      }
      if (response.status >= 500) {
        throw new ApiError("server", detail || GENERIC_SERVER_MESSAGE, response.status);
      }
      throw new ApiError("http", detail || `Request failed (${response.status}).`, response.status);
    }

    return await response.json();
  } catch (err) {
    if (err instanceof ApiError) {
      throw err;
    }
    if (err && err.name === "AbortError") {
      throw new ApiError("timeout", "The request timed out. Please try again.");
    }
    // Network-level failures (offline, DNS, refused, CORS, etc.) surface as TypeError.
    throw new ApiError("network", "Network error. Please check your connection and try again.");
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  baseUrl: API_BASE_URL,

  get(endpoint) {
    return request(endpoint, { method: "GET" });
  },

  post(endpoint, data = {}, timeoutMs = DEFAULT_TIMEOUT_MS) {
    return request(endpoint, {
      method: "POST",
      body: JSON.stringify(data),
    }, timeoutMs);
  },

  put(endpoint, data = {}) {
    return request(endpoint, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  delete(endpoint) {
    return request(endpoint, { method: "DELETE" });
  },

  discoverPersonalizedJobs() {
    return this.post("/jobs/discover/personalized", {}, DISCOVERY_TIMEOUT_MS);
  },

  analyzeResume(jobId, resumeId) {
    return this.post(`/jobs/${jobId}/resume-analysis`, { resume_id: resumeId });
  },

  getResumeAnalysis(jobId, resumeId) {
    return this.get(`/jobs/${jobId}/resume-analysis/${resumeId}`);
  },

  tailorResume(jobId, resumeId, regenerate = false) {
    return this.post(`/jobs/${jobId}/resume-tailor`, {
      resume_id: resumeId,
      regenerate,
    });
  },

  getTailoredResumes() {
    return this.get("/resumes/tailored");
  },

  async downloadTailoredResume(id, format) {
    const token = await getToken();
    const headers = {};
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(
      `${API_BASE_URL}/resumes/tailored/${id}/export/${format}`,
      { headers }
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Download failed" }));
      throw new Error(error.detail || `Download failed: ${response.status}`);
    }

    let filename = "";
    const disposition = response.headers.get("Content-Disposition") || "";
    const match = /filename="?([^"]+)"?/.exec(disposition);
    if (match) filename = match[1];
    if (!filename) {
      filename = `CareerPilot_Tailored_Resume.${format === "pdf" ? "pdf" : "docx"}`;
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);

    return { filename };
  },

  async uploadFile(endpoint, formData) {
    const token = await getToken();
    const headers = {};
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: "POST",
      headers,
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Upload failed" }));
      throw new Error(error.detail || `Upload error: ${response.status}`);
    }

    return response.json();
  },
};