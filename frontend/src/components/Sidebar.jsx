import { useRef, useEffect, useState } from "react";
import { NavLink, useLocation, useNavigate, Link } from "react-router-dom";
import { signOut } from "firebase/auth";
import { auth } from "../firebase";
import { useAuth } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";
import { useTranslation } from "../context/LanguageContext";
import { getInitials } from "../utils/formatters";
import {
  Compass,
  Briefcase,
  Layers,
  FileText,
  User,
  TrendingUp,
  Settings,
  LogOut,
  Sun,
  Moon,
  Globe,
  ChevronDown,
} from "lucide-react";

export default function Sidebar({ isOpen = false, onClose = () => {} }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { currentUser } = useAuth();
  const { theme, setTheme } = useTheme();
  const { language, setLanguage, t } = useTranslation();
  const [langOpen, setLangOpen] = useState(false);
  const sidebarRef = useRef(null);
  const langRef = useRef(null);

  const displayName = currentUser?.displayName || currentUser?.email?.split("@")[0] || "User";
  const email = currentUser?.email || "";
  const initials = getInitials(displayName);

  // Primary Workspace Navigation Items
  const primaryNavItems = [
    { to: "/home", label: t("nav.home", "Home"), icon: Compass },
    { to: "/discover", label: t("nav.jobs", "Jobs"), icon: Briefcase },
    { to: "/pipeline", label: t("nav.pipeline", "Pipeline"), icon: Layers },
    { to: "/resumes", label: t("nav.resumes", "Resumes"), icon: FileText },
    { to: "/insights", label: t("nav.insights", "Insights"), icon: TrendingUp },
  ];

  // Secondary Account Navigation Items
  const secondaryNavItems = [
    { to: "/profile", label: t("nav.profile", "Profile"), icon: User },
    { to: "/settings", label: t("nav.settings", "Settings"), icon: Settings },
  ];

  const languageLabels = {
    en: "English",
    hi: "हिन्दी",
    mr: "मराठी",
  };

  const toggleTheme = () => {
    setTheme(theme === "dark" ? "light" : "dark");
  };

  const handleLogout = async () => {
    try {
      await signOut(auth);
      navigate("/");
    } catch (error) {
      console.error("Logout error:", error);
    }
  };

  // Close language menu on click outside
  useEffect(() => {
    const handleClick = (e) => {
      if (langRef.current && !langRef.current.contains(e.target)) {
        setLangOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  // Close on outside click (mobile/overlay)
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
    if (to === "/pipeline") {
      return currentPath.startsWith("/pipeline") || currentPath.startsWith("/applications");
    }
    if (to === "/resumes") {
      return currentPath.startsWith("/resumes") || currentPath.startsWith("/resume");
    }
    if (to === "/profile") {
      return currentPath.startsWith("/profile");
    }
    if (to === "/insights") {
      return currentPath.startsWith("/insights");
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
        aria-label="Workspace navigation"
      >
        {/* Workspace Brand Header */}
        <div className="sidebar-header">
          <Link to="/home" className="sidebar-brand" aria-label="CareerPilot AI Home">
            <span className="sidebar-brand-mark" aria-hidden="true">
              <span className="logo-dot" />
            </span>
            <span className="sidebar-brand-text">CareerPilot</span>
            <span className="sidebar-brand-badge">AI</span>
          </Link>
        </div>

        {/* Primary Navigation Sections */}
        <nav className="sidebar-nav" aria-label="Primary workspace navigation">
          <div className="sidebar-section">
            <span className="sidebar-section-title">Workspace</span>
            {primaryNavItems.map(renderNavLink)}
          </div>

          <div className="sidebar-divider" />

          <div className="sidebar-section">
            <span className="sidebar-section-title">Account</span>
            {secondaryNavItems.map(renderNavLink)}
          </div>
        </nav>

        {/* Sidebar Footer with Utilities and Profile */}
        <div className="sidebar-footer">
          {/* Quick workspace utilities: Theme & Language */}
          <div className="sidebar-utilities">
            <button
              type="button"
              className="sidebar-utility-btn"
              onClick={toggleTheme}
              title={theme === "dark" ? "Switch to Light Mode" : "Switch to Dark Mode"}
              aria-label={theme === "dark" ? "Switch to Light Mode" : "Switch to Dark Mode"}
            >
              {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
              <span>{theme === "dark" ? "Light" : "Dark"}</span>
            </button>

            <div className="sidebar-lang-wrap" ref={langRef}>
              <button
                type="button"
                className="sidebar-utility-btn"
                onClick={() => setLangOpen((p) => !p)}
                aria-label="Select Language"
                aria-expanded={langOpen}
                aria-haspopup="true"
              >
                <Globe size={14} />
                <span>{language.toUpperCase()}</span>
                <ChevronDown size={12} className="sidebar-chevron" />
              </button>

              {langOpen && (
                <div className="sidebar-lang-dropdown" role="menu">
                  {Object.entries(languageLabels).map(([code, label]) => (
                    <button
                      key={code}
                      type="button"
                      className={`lang-option ${language === code ? "active" : ""}`}
                      onClick={() => {
                        setLanguage(code);
                        setLangOpen(false);
                      }}
                      role="menuitem"
                    >
                      <span>{label}</span>
                      {language === code && <span className="lang-check">✓</span>}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* User profile row */}
          <div className="sidebar-user-row">
            <Link to="/profile" className="sidebar-user" title="View Profile">
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
            </Link>

            <button
              type="button"
              className="sidebar-logout-btn"
              onClick={handleLogout}
              title={t("nav.signOut", "Sign Out")}
              aria-label={t("nav.signOut", "Sign Out")}
            >
              <LogOut size={16} aria-hidden="true" />
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
