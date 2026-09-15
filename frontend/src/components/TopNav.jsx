import { useState, useRef, useEffect } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";
import { useTranslation } from "../context/LanguageContext";
import { getInitials } from "../utils/formatters";
import {
  ChevronDown,
  Sun,
  Moon,
  Globe,
} from "lucide-react";

export default function TopNav({ onAvatarClick }) {
  const { currentUser } = useAuth();
  const { theme, setTheme } = useTheme();
  const { language, setLanguage } = useTranslation();
  const [langMenuOpen, setLangMenuOpen] = useState(false);
  const langRef = useRef(null);

  const displayName = currentUser?.displayName || currentUser?.email?.split("@")[0] || "User";
  const initials = getInitials(displayName);

  useEffect(() => {
    const handleClick = (e) => {
      if (langRef.current && !langRef.current.contains(e.target)) {
        setLangMenuOpen(false);
      }
    };
    const handleKey = (e) => {
      if (e.key === "Escape") {
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

  const handleUserBtnClick = () => {
    onAvatarClick?.();
  };

  return (
    <header className="topnav" aria-label="Mobile and tablet workspace bar">
      <div className="topnav-inner">
        <div className="topnav-left">
          <Link to="/home" className="topnav-logo" aria-label="CareerPilot AI Home">
            <span className="topnav-logo-mark" aria-hidden="true">
              <span className="logo-dot" />
            </span>
            <span className="topnav-logo-text">CareerPilot</span>
            <span className="sidebar-brand-badge">AI</span>
          </Link>
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
          <div className="topnav-user-wrap">
            <button
              type="button"
              className="topnav-user-btn"
              onClick={handleUserBtnClick}
              aria-label="User account menu"
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
          </div>
        </div>
      </div>
    </header>
  );
}
