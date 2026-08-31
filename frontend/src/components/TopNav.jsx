import { useState, useRef, useEffect } from "react";
import { NavLink, Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";
import { useTranslation } from "../context/LanguageContext";
import { getInitials } from "../utils/formatters";
import AccountMenu from "./AccountMenu";
import {
  Compass,
  Briefcase,
  FileText,
  Layers,
  TrendingUp,
  ChevronDown,
  Sun,
  Moon,
  Globe,
} from "lucide-react";

export default function TopNav() {
  const { currentUser } = useAuth();
  const { theme, setTheme } = useTheme();
  const { language, setLanguage, t } = useTranslation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [langMenuOpen, setLangMenuOpen] = useState(false);
  const menuRef = useRef(null);
  const langRef = useRef(null);

  const displayName = currentUser?.displayName || currentUser?.email?.split("@")[0] || "User";
  const initials = getInitials(displayName);

  const navItems = [
    { to: "/home", label: t("nav.home", "Home"), icon: Compass },
    { to: "/discover", label: t("nav.jobs", "Find Jobs"), icon: Briefcase },
    { to: "/resumes", label: t("nav.resumes", "My Resume"), icon: FileText },
    { to: "/pipeline", label: t("nav.applications", "Applications"), icon: Layers },
    { to: "/insights", label: t("nav.insights", "Insights"), icon: TrendingUp },
  ];

  useEffect(() => {
    const handleClick = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false);
      }
      if (langRef.current && !langRef.current.contains(e.target)) {
        setLangMenuOpen(false);
      }
    };
    const handleKey = (e) => {
      if (e.key === "Escape") {
        setMenuOpen(false);
        setLangMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKey);
    };
  }, []);

  const toggleTheme = () => {
    setTheme(theme === "dark" ? "light" : "dark");
  };

  const languageLabels = {
    en: "English",
    hi: "हिन्दी",
    mr: "मराठी",
  };

  return (
    <header className="topnav" aria-label="Main navigation">
      <div className="topnav-inner">
        <div className="topnav-left">
          <Link to="/home" className="topnav-logo" aria-label="CareerPilot AI Home">
            <span className="topnav-logo-mark" aria-hidden="true">
              <span className="logo-dot" />
            </span>
            <span className="topnav-logo-text">CareerPilot</span>
          </Link>

          <nav className="topnav-links" aria-label="Primary navigation">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `topnav-link ${isActive ? "active" : ""}`
                }
              >
                <item.icon size={16} aria-hidden="true" />
                <span>{item.label}</span>
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="topnav-right">
          {/* Theme Quick Toggle */}
          <button
            type="button"
            className="topnav-icon-btn"
            onClick={toggleTheme}
            title={theme === "dark" ? "Switch to Light Mode" : "Switch to Dark Mode"}
            aria-label={theme === "dark" ? "Switch to Light Mode" : "Switch to Dark Mode"}
          >
            {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
          </button>

          {/* Language Quick Dropdown */}
          <div className="topnav-lang-wrap" ref={langRef}>
            <button
              type="button"
              className="topnav-lang-btn"
              onClick={() => setLangMenuOpen((p) => !p)}
              aria-label="Select Language"
              aria-expanded={langMenuOpen}
              aria-haspopup="true"
            >
              <Globe size={15} />
              <span className="topnav-lang-code">{language.toUpperCase()}</span>
            </button>

            {langMenuOpen && (
              <div className="topnav-lang-dropdown" role="menu">
                {Object.entries(languageLabels).map(([code, label]) => (
                  <button
                    key={code}
                    type="button"
                    className={`lang-option ${language === code ? "active" : ""}`}
                    onClick={() => {
                      setLanguage(code);
                      setLangMenuOpen(false);
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

          {/* User Account Menu */}
          <div className="topnav-user-wrap" ref={menuRef}>
            <button
              className={`topnav-user-btn ${menuOpen ? "open" : ""}`}
              onClick={() => setMenuOpen((p) => !p)}
              aria-label="User account menu"
              aria-expanded={menuOpen}
              aria-haspopup="true"
            >
              <div className="topnav-avatar">
                {currentUser?.photoURL ? (
                  <img src={currentUser.photoURL} alt={displayName} />
                ) : (
                  <span>{initials}</span>
                )}
              </div>
              <span className="topnav-username">{displayName}</span>
              <ChevronDown size={14} className="topnav-chevron" aria-hidden="true" />
            </button>

            {menuOpen && (
              <AccountMenu onClose={() => setMenuOpen(false)} />
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
