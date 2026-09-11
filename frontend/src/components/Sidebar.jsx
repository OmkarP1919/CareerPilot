import { useRef, useEffect } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { signOut } from "firebase/auth";
import { auth } from "../firebase";
import { useAuth } from "../context/AuthContext";
import { useTranslation } from "../context/LanguageContext";
import { getInitials } from "../utils/formatters";
import {
  Compass,
  Briefcase,
  FileText,
  Layers,
  TrendingUp,
  User,
  Settings,
  LogOut,
} from "lucide-react";

export default function Sidebar({ isOpen = false, onClose = () => {} }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { currentUser } = useAuth();
  const { t } = useTranslation();
  const sidebarRef = useRef(null);

  const displayName = currentUser?.displayName || currentUser?.email?.split("@")[0] || "User";
  const email = currentUser?.email || "";
  const initials = getInitials(displayName);

  const mainNavItems = [
    { to: "/home", label: t("nav.home", "Home"), icon: Compass },
    { to: "/discover", label: t("nav.jobs", "Jobs"), icon: Briefcase },
    { to: "/resumes", label: t("nav.resumes", "Resume"), icon: FileText },
    { to: "/pipeline", label: t("nav.applications", "Applications"), icon: Layers },
    { to: "/insights", label: t("nav.insights", "Insights"), icon: TrendingUp },
  ];

  const secondaryNavItems = [
    { to: "/profile", label: t("nav.profile", "Profile"), icon: User },
    { to: "/settings", label: t("nav.settings", "Settings"), icon: Settings },
  ];

  const handleLogout = async () => {
    try {
      await signOut(auth);
      navigate("/");
    } catch (error) {
      console.error("Logout error:", error);
    }
  };

  // Close on outside click (mobile)
  useEffect(() => {
    if (!isOpen) return;
    const handleClick = (e) => {
      if (sidebarRef.current && !sidebarRef.current.contains(e.target)) {
        onClose();
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [isOpen, onClose]);

  // Close on escape key
  useEffect(() => {
    if (!isOpen) return;
    const handleKey = (e) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [isOpen, onClose]);

  const currentPath = location.pathname;
  const isItemActive = (to) => {
    if (to === "/home") {
      return currentPath === "/home" || currentPath === "/dashboard";
    }
    if (to === "/discover") {
      return currentPath.startsWith("/discover") || currentPath.startsWith("/jobs");
    }
    if (to === "/resumes") {
      return currentPath.startsWith("/resumes") || currentPath.startsWith("/resume");
    }
    if (to === "/pipeline") {
      return currentPath.startsWith("/pipeline") || currentPath.startsWith("/applications");
    }
    if (to === "/insights") {
      return currentPath.startsWith("/insights") || currentPath.startsWith("/analytics");
    }
    if (to === "/profile") {
      return currentPath.startsWith("/profile");
    }
    if (to === "/settings") {
      return currentPath.startsWith("/settings");
    }
    return currentPath === to;
  };

  const renderNavLink = (item) => {
    const active = isItemActive(item.to);
    const Icon = item.icon;
    return (
      <NavLink
        key={item.to}
        to={item.to}
        onClick={onClose}
        className={`sidebar-link ${active ? "active" : ""}`}
        aria-current={active ? "page" : undefined}
      >
        <span className="sidebar-link-icon">
          <Icon size={18} aria-hidden="true" />
        </span>
        <span className="sidebar-link-text">{item.label}</span>
      </NavLink>
    );
  };

  return (
    <>
      <div
        className={`sidebar-overlay ${isOpen ? "open" : ""}`}
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        ref={sidebarRef}
        className={`sidebar ${isOpen ? "open" : ""}`}
        aria-label="Desktop sidebar"
      >
        <div className="sidebar-header">
          <div className="sidebar-logo">CareerPilot</div>
          <span className="sidebar-logo-badge">AI</span>
        </div>

        <nav className="sidebar-nav" aria-label="Main navigation">
          <div className="sidebar-section">
            <span className="sidebar-section-title">Navigation</span>
            {mainNavItems.map(renderNavLink)}
          </div>

          <div className="sidebar-divider" />

          <div className="sidebar-section">
            <span className="sidebar-section-title">Account</span>
            {secondaryNavItems.map(renderNavLink)}
          </div>
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-user">
            <div className="sidebar-user-avatar">
              {currentUser?.photoURL ? (
                <img src={currentUser.photoURL} alt="" />
              ) : (
                initials
              )}
            </div>
            <div className="sidebar-user-info">
              <div className="sidebar-user-name">{displayName}</div>
              <div className="sidebar-user-email">{email}</div>
            </div>
          </div>
          <button className="sidebar-logout" onClick={handleLogout} aria-label={t("nav.signOut", "Sign Out")}>
            <span className="sidebar-link-icon">
              <LogOut size={18} aria-hidden="true" />
            </span>
            <span className="sidebar-link-text">{t("nav.signOut", "Sign Out")}</span>
          </button>
        </div>
      </aside>
    </>
  );
}
