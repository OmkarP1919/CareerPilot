import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { getInitials } from "../utils/formatters";
import { Menu, Bell } from "lucide-react";

const PAGE_TITLES = {
  "/dashboard": "Dashboard",
  "/profile": "My Profile",
  "/resumes": "Resumes",
  "/jobs": "Jobs",
  "/applications": "Applications",
  "/analytics": "Analytics",
  "/settings": "Settings",
};

export default function Header({ onMenuToggle }) {
  const location = useLocation();
  const { currentUser } = useAuth();
  const navigate = useNavigate();

  const path = location.pathname;
  let title = "CareerPilot AI";

  if (path.startsWith("/jobs/")) {
    title = "Job Details";
  } else if (path === "/jobs") {
    title = "Jobs";
  } else {
    for (const [route, pageTitle] of Object.entries(PAGE_TITLES)) {
      if (path === route) {
        title = pageTitle;
        break;
      }
    }
  }

  const displayName = currentUser?.displayName || currentUser?.email?.split("@")[0] || "User";
  const initials = getInitials(displayName);

  return (
    <header className="page-header">
      <div className="page-header-row">
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-4)" }}>
          <button
            className="btn btn-ghost btn-icon header-menu-btn"
            onClick={onMenuToggle}
            aria-label="Toggle navigation menu"
          >
            <Menu size={20} />
          </button>
          <div>
            <h1>{title}</h1>
          </div>
        </div>
        <div className="page-header-actions">
          <button
            className="btn btn-ghost btn-icon"
            aria-label="Notifications"
          >
            <Bell size={18} />
          </button>
          <button
            className="btn btn-ghost btn-icon"
            onClick={() => navigate("/settings")}
            aria-label="Account settings"
            style={{
              width: 36,
              height: 36,
              borderRadius: "var(--radius-full)",
              background: "var(--color-primary)",
              color: "var(--text-inverse)",
              fontSize: "var(--text-xs)",
              fontWeight: "var(--font-semibold)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            {currentUser?.photoURL ? (
              <img
                src={currentUser.photoURL}
                alt=""
                style={{ width: "100%", height: "100%", borderRadius: "50%", objectFit: "cover" }}
              />
            ) : (
              initials
            )}
          </button>
        </div>
      </div>
    </header>
  );
}
