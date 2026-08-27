import { auth } from "../firebase";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function getToken() {
  const user = auth.currentUser;
  if (!user) return null;
  return user.getIdToken();
}

async function request(endpoint, options = {}) {
  const fullUrl = `${API_BASE_URL}${endpoint}`;
  try {
    const token = await getToken();
    const headers = {
      ...options.headers,
    };

    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    if (!(options.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
    }

    console.log("[API 4] Fetch starting", fullUrl, options.method || "GET");
    const response = await fetch(fullUrl, {
      ...options,
      headers,
    });
    console.log("[API 5] Fetch response received", response.status, response.statusText);

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Request failed" }));
      console.error("[API Error Response]", response.status, error);
      throw new Error(error.detail || `API error: ${response.status}`);
    }

    console.log("[API 6] Parsing response");
    const data = await response.json();
    console.log("[API 7] Parsed response", data);
    return data;
  } catch (err) {
    console.error("[API Request Exception]", fullUrl, err);
    throw err;
  }
}

export const api = {
  baseUrl: API_BASE_URL,

  get(endpoint) {
    return request(endpoint, { method: "GET" });
  },

  post(endpoint, data = {}) {
    console.log("[API 3] post() entered", endpoint);
    return request(endpoint, {
      method: "POST",
      body: JSON.stringify(data),
    });
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
    console.log("[API 1] discoverPersonalizedJobs entered");
    console.log("[API 2] Calling POST");
    return this.post("/jobs/discover/personalized", {});
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
