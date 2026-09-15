import { useNavigate, Link } from "react-router-dom";
import { signOut } from "firebase/auth";
import { auth } from "../firebase";
import { useAuth } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";
import { useTranslation } from "../context/LanguageContext";
import {
  User,
  Palette,
  Globe,
  Eye,
  LogOut,
  CheckCircle2,
  Sun,
  Moon,
  Laptop,
  Briefcase,
  ArrowRight,
} from "lucide-react";

export default function SettingsPage() {
  const { currentUser } = useAuth();
  const {
    theme,
    setTheme,
    textSize,
    setTextSize,
    highContrast,
    setHighContrast,
    reducedMotion,
    setReducedMotion,
  } = useTheme();
  const { language, setLanguage, t } = useTranslation();
  const navigate = useNavigate();

  const handleLogout = async () => {
    try {
      await signOut(auth);
      navigate("/login");
    } catch (err) {
      console.error("Logout error:", err);
    }
  };

  const displayName = currentUser?.displayName || currentUser?.email?.split("@")[0] || "User";
  const email = currentUser?.email || "Not specified";
  const photoURL = currentUser?.photoURL;
  const providerData = currentUser?.providerData || [];
  const authProvider =
    providerData.length > 0
      ? providerData[0].providerId === "google.com"
        ? "Google Authentication"
        : providerData[0].providerId
      : "Email / Password";

  return (
    <div className="page settings-page settings-page-unified">
      {/* Header */}
      <header className="page-header settings-header">
        <h1 className="settings-main-title">{t("settings.title", "Settings")}</h1>
        <p className="settings-main-subtitle">
          Manage your account identity, workspace appearance, and system preferences.
        </p>
      </header>

      <div className="settings-sections-stack">
        {/* =========================================================================
            SECTION 1: ACCOUNT IDENTITY
            ========================================================================= */}
        <section className="settings-card" aria-labelledby="settings-account-heading">
          <div className="settings-card-header">
            <div className="settings-section-title-wrap">
              <User size={18} className="text-accent" aria-hidden="true" />
              <h2 id="settings-account-heading" className="settings-section-title">
                {t("settings.account", "Account Identity")}
              </h2>
            </div>
          </div>

          <div className="settings-card-body">
            <div className="settings-user-profile-row">
              <div className="settings-user-profile-info">
                <div className="settings-avatar-circle">
                  {photoURL ? (
                    <img src={photoURL} alt={displayName} className="settings-avatar-img" />
                  ) : (
                    <span>{displayName.slice(0, 2).toUpperCase()}</span>
                  )}
                </div>
                <div className="settings-user-info">
                  <h3 className="settings-user-name">{displayName}</h3>
                  <span className="settings-user-email">{email}</span>
                  <div className="settings-verified-badge">
                    <CheckCircle2 size={13} className="text-success" aria-hidden="true" />
                    <span>Authenticated via {authProvider}</span>
                  </div>
                </div>
              </div>

              <div className="settings-account-action">
                <button
                  type="button"
                  className="btn btn-secondary btn-sm settings-signout-btn"
                  onClick={handleLogout}
                >
                  <LogOut size={15} aria-hidden="true" />
                  <span>Sign Out</span>
                </button>
              </div>
            </div>

            <div className="settings-card-footer">
              <p className="text-xs text-muted">
                Your account sessions and authentication tokens are managed securely through Firebase Auth.
              </p>
            </div>
          </div>
        </section>

        {/* =========================================================================
            SECTION 2: APPEARANCE & ACCESSIBILITY
            ========================================================================= */}
        <section className="settings-card" aria-labelledby="settings-appearance-heading">
          <div className="settings-card-header">
            <div className="settings-section-title-wrap">
              <Palette size={18} className="text-accent" aria-hidden="true" />
              <h2 id="settings-appearance-heading" className="settings-section-title">
                {t("settings.appearance", "Appearance & Accessibility")}
              </h2>
            </div>
          </div>

          <div className="settings-card-body settings-appearance-body">
            {/* Interface Theme */}
            <div className="settings-group">
              <label className="form-label">{t("settings.theme", "Interface Theme")}</label>
              <div className="theme-options-grid">
                <button
                  type="button"
                  className={`theme-option-card ${theme === "light" ? "active" : ""}`}
                  onClick={() => setTheme("light")}
                >
                  <Sun size={18} aria-hidden="true" />
                  <span>{t("settings.themeLight", "Light")}</span>
                </button>

                <button
                  type="button"
                  className={`theme-option-card ${theme === "dark" ? "active" : ""}`}
                  onClick={() => setTheme("dark")}
                >
                  <Moon size={18} aria-hidden="true" />
                  <span>{t("settings.themeDark", "Dark")}</span>
                </button>

                <button
                  type="button"
                  className={`theme-option-card ${theme === "system" ? "active" : ""}`}
                  onClick={() => setTheme("system")}
                >
                  <Laptop size={18} aria-hidden="true" />
                  <span>{t("settings.themeSystem", "System")}</span>
                </button>
              </div>
            </div>

            {/* Display Language */}
            <div className="settings-group">
              <label className="form-label" style={{ display: "flex", alignItems: "center", gap: "var(--space-1)" }}>
                <Globe size={14} aria-hidden="true" />
                <span>{t("settings.language", "Display Language")}</span>
              </label>
              <div className="theme-options-grid">
                <button
                  type="button"
                  className={`theme-option-card ${language === "en" ? "active" : ""}`}
                  onClick={() => setLanguage("en")}
                >
                  <span className="font-medium">English</span>
                  <span className="text-xs text-muted">EN</span>
                </button>

                <button
                  type="button"
                  className={`theme-option-card ${language === "hi" ? "active" : ""}`}
                  onClick={() => setLanguage("hi")}
                >
                  <span className="font-medium">हिन्दी</span>
                  <span className="text-xs text-muted">HI</span>
                </button>

                <button
                  type="button"
                  className={`theme-option-card ${language === "mr" ? "active" : ""}`}
                  onClick={() => setLanguage("mr")}
                >
                  <span className="font-medium">मराठी</span>
                  <span className="text-xs text-muted">MR</span>
                </button>
              </div>
            </div>

            {/* Reading & Contrast */}
            <div className="settings-group">
              <label className="form-label" style={{ display: "flex", alignItems: "center", gap: "var(--space-1)" }}>
                <Eye size={14} aria-hidden="true" />
                <span>{t("settings.accessibility", "Reading & Contrast")}</span>
              </label>

              <div className="theme-options-grid text-size-grid">
                <button
                  type="button"
                  className={`theme-option-card ${textSize === "sm" ? "active" : ""}`}
                  onClick={() => setTextSize("sm")}
                >
                  <span>{t("settings.sizeSmall", "Small")}</span>
                  <span className="text-xs text-muted">14px</span>
                </button>
                <button
                  type="button"
                  className={`theme-option-card ${textSize === "md" ? "active" : ""}`}
                  onClick={() => setTextSize("md")}
                >
                  <span>{t("settings.sizeDefault", "Default")}</span>
                  <span className="text-xs text-muted">16px</span>
                </button>
                <button
                  type="button"
                  className={`theme-option-card ${textSize === "lg" ? "active" : ""}`}
                  onClick={() => setTextSize("lg")}
                >
                  <span>{t("settings.sizeLarge", "Large")}</span>
                  <span className="text-xs text-muted">18px</span>
                </button>
                <button
                  type="button"
                  className={`theme-option-card ${textSize === "xl" ? "active" : ""}`}
                  onClick={() => setTextSize("xl")}
                >
                  <span>{t("settings.sizeExtraLarge", "Extra Large")}</span>
                  <span className="text-xs text-muted">20px</span>
                </button>
              </div>

              <div className="settings-toggles-wrap">
                <div className="setting-toggle-row">
                  <div>
                    <strong>{t("settings.highContrast", "High Contrast")}</strong>
                    <p className="text-xs text-muted">Enhances active focus rings and border visibility.</p>
                  </div>
                  <button
                    type="button"
                    className={`toggle-switch-btn ${highContrast ? "on" : "off"}`}
                    onClick={() => setHighContrast(!highContrast)}
                    aria-pressed={highContrast}
                    aria-label="Toggle High Contrast"
                  >
                    <span className="toggle-switch-handle" />
                  </button>
                </div>

                <div className="setting-toggle-row">
                  <div>
                    <strong>{t("settings.reducedMotion", "Reduce Motion")}</strong>
                    <p className="text-xs text-muted">Disables non-essential interface animations.</p>
                  </div>
                  <button
                    type="button"
                    className={`toggle-switch-btn ${reducedMotion ? "on" : "off"}`}
                    onClick={() => setReducedMotion(!reducedMotion)}
                    aria-pressed={reducedMotion}
                    aria-label="Toggle Reduced Motion"
                  >
                    <span className="toggle-switch-handle" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* =========================================================================
            SECTION 3: CAREER & JOB SEARCH PREFERENCES (PROFILE REFERENCE)
            ========================================================================= */}
        <section className="settings-card settings-reference-card" aria-labelledby="settings-career-prefs-heading">
          <div className="settings-reference-inner">
            <div className="settings-reference-content">
              <div className="settings-section-title-wrap">
                <Briefcase size={18} className="text-accent" aria-hidden="true" />
                <h2 id="settings-career-prefs-heading" className="settings-section-title">
                  Career &amp; Job Search Preferences
                </h2>
              </div>
              <p className="settings-reference-desc">
                Target roles, preferred locations, and work preferences are managed in your candidate Profile to ensure consistent matching and automated discovery.
              </p>
            </div>
            <div className="settings-reference-action">
              <Link
                to="/profile"
                className="btn btn-secondary btn-sm settings-profile-link"
              >
                <span>Edit in Profile</span>
                <ArrowRight size={14} aria-hidden="true" />
              </Link>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
