export const APPLICATION_STATUSES = [
  { value: "Saved", label: "Saved", color: "status-saved" },
  { value: "Preparing", label: "Preparing", color: "status-preparing" },
  { value: "Applied", label: "Applied", color: "status-applied" },
  { value: "Assessment", label: "Assessment", color: "status-assessment" },
  { value: "Interview", label: "Interview", color: "status-interview" },
  { value: "Offer", label: "Offer", color: "status-offer" },
  { value: "Rejected", label: "Rejected", color: "status-rejected" },
  { value: "Withdrawn", label: "Withdrawn", color: "status-withdrawn" },
];

export const STATUS_COLORS = {
  Saved: { bg: "#f1f5f9", text: "#475569" },
  Preparing: { bg: "#eff6ff", text: "#1d4ed8" },
  Applied: { bg: "#eef2ff", text: "#4338ca" },
  Assessment: { bg: "#fff7ed", text: "#c2410c" },
  Interview: { bg: "#ecfdf5", text: "#047857" },
  Offer: { bg: "#f0fdf4", text: "#15803d" },
  Rejected: { bg: "#fef2f2", text: "#b91c1c" },
  Withdrawn: { bg: "#f5f5f5", text: "#737373" },
};

export const EMPLOYMENT_TYPES = [
  "Full-time",
  "Part-time",
  "Contract",
  "Internship",
  "Freelance",
];

export const EXPERIENCE_LEVELS = [
  "Entry Level",
  "Mid Level",
  "Senior Level",
  "Lead",
  "Executive",
];

export const SKILL_CATEGORIES = [
  "Programming Languages",
  "Frameworks/Libraries",
  "Databases",
  "Developer Tools",
  "Other Technical Skills",
];

export const MATCH_THRESHOLDS = {
  EXCELLENT: 90,
  STRONG: 75,
  MODERATE: 50,
};

export function getMatchLabel(score) {
  if (score >= MATCH_THRESHOLDS.EXCELLENT) return "Excellent Match";
  if (score >= MATCH_THRESHOLDS.STRONG) return "Strong Match";
  if (score >= MATCH_THRESHOLDS.MODERATE) return "Moderate Match";
  return "Low Match";
}

export function getMatchClass(score) {
  if (score >= MATCH_THRESHOLDS.STRONG) return "score-high match-strong match-excellent";
  if (score >= MATCH_THRESHOLDS.MODERATE) return "score-medium match-moderate";
  return "score-low match-low";
}

export function getStatusColor(status) {
  const norm = status ? status.charAt(0).toUpperCase() + status.slice(1).toLowerCase() : "Saved";
  return STATUS_COLORS[norm] || STATUS_COLORS.Saved;
}

export function getStatusClass(status) {
  if (!status) return "status-saved";
  const s = status.toLowerCase();
  return `status-${s}`;
}
