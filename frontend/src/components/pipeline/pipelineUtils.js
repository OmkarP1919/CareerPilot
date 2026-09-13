/**
 * Pipeline Utility Module — Phase 7.0B.3
 *
 * Centralized helpers for statuses, stage groupings, progression,
 * datetime parsing, file formatting, and safe filtering.
 */

// Canonical 8 backend statuses exactly matching backend/app/api/applications.py
export const PIPELINE_STATUSES = [
  "Saved",
  "Preparing",
  "Applied",
  "Assessment",
  "Interview",
  "Offer",
  "Rejected",
  "Withdrawn",
];

// Display labels for each status
export const STATUS_LABELS = {
  Saved: "Saved",
  Preparing: "Preparing",
  Applied: "Applied",
  Assessment: "Assessment",
  Interview: "Interview",
  Offer: "Offer Received",
  Rejected: "Rejected",
  Withdrawn: "Withdrawn",
};

// Semantic status badges
export const STATUS_VARIANTS = {
  Saved: "saved",
  Preparing: "preparing",
  Applied: "applied",
  Assessment: "assessment",
  Interview: "interview",
  Offer: "offer",
  Rejected: "rejected",
  Withdrawn: "withdrawn",
};

// Logical groupings for filter tabs & summary metrics
export const STATUS_GROUPS = {
  Active: ["Preparing", "Applied", "Assessment", "Interview"],
  Saved: ["Saved"],
  Offer: ["Offer"],
  Archived: ["Rejected", "Withdrawn"],
};

// Filter tabs exposed in UI
export const FILTER_TABS = [
  { id: "all", label: "All" },
  { id: "active", label: "Active" },
  { id: "interview", label: "Interviewing" },
  { id: "offer", label: "Offers" },
  { id: "saved", label: "Saved" },
  { id: "archived", label: "Archived" },
];

// Progression ladder for advancing an application
export const NEXT_STAGE_MAP = {
  Saved: "Applied",
  Preparing: "Applied",
  Applied: "Assessment",
  Assessment: "Interview",
  Interview: "Offer",
};

/**
 * Returns the next logical status, or null if at end of happy path or archived.
 */
export function getNextStatus(currentStatus) {
  return NEXT_STAGE_MAP[currentStatus] || null;
}

/**
 * Filter applications by tab ID and search query.
 */
export function filterApplications(applications, tabId, query = "") {
  if (!Array.isArray(applications)) return [];

  const trimmed = query.trim().toLowerCase();

  return applications.filter((app) => {
    const status = app.status || "Saved";

    // Stage Tab Matching
    if (tabId === "active") {
      if (!STATUS_GROUPS.Active.includes(status)) return false;
    } else if (tabId === "interview") {
      if (status !== "Interview") return false;
    } else if (tabId === "offer") {
      if (status !== "Offer") return false;
    } else if (tabId === "saved") {
      if (status !== "Saved") return false;
    } else if (tabId === "archived") {
      if (!STATUS_GROUPS.Archived.includes(status)) return false;
    }

    // Search Query Matching (company, title, location, notes)
    if (trimmed) {
      const title = (app.job_title || app.title || "").toLowerCase();
      const company = (app.job_company || app.company_name || app.company || "").toLowerCase();
      const location = (app.location || "").toLowerCase();
      const notes = (app.notes || "").toLowerCase();
      const matches =
        title.includes(trimmed) ||
        company.includes(trimmed) ||
        location.includes(trimmed) ||
        notes.includes(trimmed);
      if (!matches) return false;
    }

    return true;
  });
}

/**
 * Sort applications deterministically.
 */
export function sortApplications(applications, sortKey = "recent") {
  if (!Array.isArray(applications)) return [];

  const copy = [...applications];
  return copy.sort((a, b) => {
    if (sortKey === "applied_date") {
      const dateA = new Date(a.application_date || a.created_at || 0).getTime();
      const dateB = new Date(b.application_date || b.created_at || 0).getTime();
      return dateB - dateA;
    }

    if (sortKey === "company_asc") {
      const compA = (a.job_company || a.company_name || a.company || "").toLowerCase();
      const compB = (b.job_company || b.company_name || b.company || "").toLowerCase();
      return compA.localeCompare(compB);
    }

    if (sortKey === "match_score") {
      // Only sort by match score when a genuine score is present
      const scoreA = typeof a.match_score === "number" ? a.match_score : -1;
      const scoreB = typeof b.match_score === "number" ? b.match_score : -1;
      return scoreB - scoreA;
    }

    // Default: recently updated
    const timeA = new Date(a.updated_at || a.created_at || 0).getTime();
    const timeB = new Date(b.updated_at || b.created_at || 0).getTime();
    return timeB - timeA;
  });
}

/**
 * Derive high-level summary counts from applications.
 */
export function deriveSummaryMetrics(applications) {
  if (!Array.isArray(applications)) {
    return { total: 0, active: 0, interviews: 0, offers: 0 };
  }

  let total = applications.length;
  let active = 0;
  let interviews = 0;
  let offers = 0;

  for (const app of applications) {
    const s = app.status || "Saved";
    if (STATUS_GROUPS.Active.includes(s)) active++;
    if (s === "Interview") interviews++;
    if (s === "Offer") offers++;
  }

  return { total, active, interviews, offers };
}

/**
 * Backend datetimes (SQLite/Postgres) are serialized as naive UTC strings.
 * Safely parse with 'Z' fallback for accurate local timezone rendering.
 */
export function parseBackendDatetime(str) {
  if (!str) return null;
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(str);
  const d = new Date(hasZone ? str : `${str}Z`);
  return isNaN(d.getTime()) ? null : d;
}

/**
 * Format date for friendly human reading.
 */
export function formatFriendlyDate(str) {
  const d = parseBackendDatetime(str);
  if (!d) return str || "";
  return d.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

/**
 * Format datetime for detailed logs and interviews.
 */
export function formatDateTime(str) {
  const d = parseBackendDatetime(str);
  if (!d) return str || "";
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function toLocalInputValue(date) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours()
  )}:${pad(date.getMinutes())}`;
}

export function fromLocalInputValue(str) {
  if (!str) return null;
  const d = new Date(str);
  return isNaN(d.getTime()) ? null : d.toISOString();
}

export function backendToInputValue(str) {
  const d = parseBackendDatetime(str);
  return d ? toLocalInputValue(d) : "";
}

export function formatFileSize(size) {
  if (size === null || size === undefined || size === "") return null;
  const n = Number(size);
  if (Number.isNaN(n)) return null;
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

// Sub-resource enums
export const USER_EVENT_TYPES = ["note_added", "milestone", "other"];

export const EVENT_LABELS = {
  created: "Created",
  status_changed: "Status Changed",
  note_added: "Note Added",
  resume_attached: "Resume Attached",
  document_attached: "Document Attached",
  interview_scheduled: "Interview Scheduled",
  interview_completed: "Interview Completed",
  milestone: "Milestone",
  other: "Other",
};

export const INTERVIEW_KINDS = [
  "phone",
  "video",
  "onsite",
  "technical",
  "behavioral",
  "assessment",
  "panel",
  "other",
];

export const INTERVIEW_KIND_LABELS = {
  phone: "Phone",
  video: "Video",
  onsite: "Onsite",
  technical: "Technical",
  behavioral: "Behavioral",
  assessment: "Assessment",
  panel: "Panel",
  other: "Other",
};

export const INTERVIEW_STATUSES = [
  "scheduled",
  "completed",
  "cancelled",
  "rescheduled",
  "no_show",
];

export const INTERVIEW_STATUS_LABELS = {
  scheduled: "Scheduled",
  completed: "Completed",
  cancelled: "Cancelled",
  rescheduled: "Rescheduled",
  no_show: "No Show",
};

export const DOCUMENT_TYPES = [
  "resume",
  "cover_letter",
  "portfolio",
  "transcript",
  "assessment",
  "contract",
  "other",
];

export const DOCUMENT_TYPE_LABELS = {
  resume: "Resume",
  cover_letter: "Cover Letter",
  portfolio: "Portfolio",
  transcript: "Transcript",
  assessment: "Assessment",
  contract: "Contract",
  other: "Other",
};
