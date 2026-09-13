import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { signOut } from "firebase/auth";
import { auth } from "../firebase";
import { useAuth } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";
import { useTranslation } from "../context/LanguageContext";
import { api } from "../services/api";
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
  Save,
  Check,
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

  // Job Search Defaults state (persisted via PUT /profile)
  const [jobPreferences, setJobPreferences] = useState({
    preferred_roles: "",
    preferred_locations: "",
  });
  const [savingPrefs, setSavingPrefs] = useState(false);
  const [prefSavedStatus, setPrefSavedStatus] = useState(false);

  useEffect(() => {
    let mounted = true;
    api
      .get("/profile")
      .then((data) => {
        if (mounted && data?.profile) {
          setJobPreferences({
            preferred_roles: data.profile.preferred_roles || "",
            preferred_locations: data.profile.preferred_locations || "",
          });
        }
      })
      .catch(() => {});
    return () => {
      mounted = false;
    };
  }, []);

  const handleSavePreferences = async (e) => {
    e.preventDefault();
    setSavingPrefs(true);
    try {
      await api.put("/profile", jobPreferences);
      setPrefSavedStatus(true);
      setTimeout(() => setPrefSavedStatus(false), 3000);
    } catch {
      // resilient error handling
    } finally {
      setSavingPrefs(false);
    }
  };

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
      <header className="page-header">
        <h1 className="settings-main-title">{t("settings.title", "Settings & Preferences")}</h1>
        <p className="settings-main-subtitle">
          Manage your account identity, workspace appearance, and default job search criteria.
        </p>
      </header>

      <div className="settings-sections-stack">
        {/* =========================================================================
            GROUP 1: ACCOUNT IDENTITY
            ========================================================================= */}
        <section className="card settings-card" aria-labelledby="settings-account-heading">
          <div className="card-header settings-card-header">
            <div className="settings-section-title-wrap">
              <User size={18} className="text-accent" aria-hidden="true" />
              <h2 id="settings-account-heading" className="settings-section-title">
                {t("settings.account", "Account Identity")}
              </h2>
            </div>
          </div>

          <div className="card-body settings-card-body">
            <div className="settings-user-profile-row">
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

            <div className="settings-account-actions" style={{ marginTop: "var(--space-6)" }}>
              <button
                type="button"
                className="btn btn-secondary settings-signout-btn"
                onClick={handleLogout}
              >
                <LogOut size={16} aria-hidden="true" />
                <span>Sign Out of CareerPilot</span>
              </button>
            </div>

            <p className="text-xs text-muted" style={{ marginTop: "var(--space-4)" }}>
              Your account sessions and authentication tokens are managed securely through Firebase Auth.
            </p>
          </div>
        </section>

        {/* =========================================================================
            GROUP 2: JOB SEARCH DEFAULTS (PERSISTED VIA /profile)
            ========================================================================= */}
        <section className="card settings-card" aria-labelledby="settings-search-defaults-heading">
          <div className="card-header settings-card-header">
            <div className="settings-section-title-wrap">
              <Briefcase size={18} className="text-accent" aria-hidden="true" />
              <h2 id="settings-search-defaults-heading" className="settings-section-title">
                Job Search Defaults
              </h2>
            </div>
          </div>

          <div className="card-body settings-card-body">
            <p className="text-secondary text-sm" style={{ marginBottom: "var(--space-4)" }}>
              These criteria are used as your default search baseline for automated discovery and recommendations.
            </p>

            <form onSubmit={handleSavePreferences} className="settings-prefs-form">
              <div className="form-group">
                <label className="form-label" htmlFor="settings-roles">
                  Default Target Roles
                </label>
                <input
                  id="settings-roles"
                  className="form-input"
                  value={jobPreferences.preferred_roles}
                  onChange={(e) =>
                    setJobPreferences({ ...jobPreferences, preferred_roles: e.target.value })
                  }
                  placeholder="e.g. Senior Frontend Engineer, Full-Stack Developer"
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="settings-locations">
                  Default Preferred Locations
                </label>
                <input
                  id="settings-locations"
                  className="form-input"
                  value={jobPreferences.preferred_locations}
                  onChange={(e) =>
                    setJobPreferences({ ...jobPreferences, preferred_locations: e.target.value })
                  }
                  placeholder="e.g. Remote, San Francisco, CA, New York, NY"
                />
              </div>

              <div className="settings-form-actions">
                <button
                  type="submit"
                  className="btn btn-primary btn-sm settings-save-prefs-btn"
                  disabled={savingPrefs}
                >
                  {prefSavedStatus ? (
                    <>
                      <Check size={14} aria-hidden="true" />
                      <span>Saved!</span>
                    </>
                  ) : (
                    <>
                      <Save size={14} aria-hidden="true" />
                      <span>{savingPrefs ? "Saving..." : "Save Search Defaults"}</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </section>

        {/* =========================================================================
            GROUP 3: APPEARANCE & ACCESSIBILITY
            ========================================================================= */}
        <section className="card settings-card" aria-labelledby="settings-appearance-heading">
          <div className="card-header settings-card-header">
            <div className="settings-section-title-wrap">
              <Palette size={18} className="text-accent" aria-hidden="true" />
              <h2 id="settings-appearance-heading" className="settings-section-title">
                {t("settings.appearance", "Appearance & Accessibility")}
              </h2>
            </div>
          </div>

          <div className="card-body settings-card-body stack" style={{ gap: "var(--space-6)" }}>
            {/* Color Scheme */}
            <div>
              <label className="form-label">{t("settings.theme", "Interface Theme")}</label>
              <div className="theme-options-grid" style={{ marginTop: "var(--space-2)" }}>
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

            {/* Language */}
            <div>
              <label className="form-label" style={{ display: "flex", alignItems: "center", gap: "var(--space-1)" }}>
                <Globe size={14} aria-hidden="true" />
                <span>{t("settings.language", "Display Language")}</span>
              </label>
              <div className="theme-options-grid" style={{ marginTop: "var(--space-2)" }}>
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

            {/* Accessibility (Text Size & Motion) */}
            <div>
              <label className="form-label" style={{ display: "flex", alignItems: "center", gap: "var(--space-1)" }}>
                <Eye size={14} aria-hidden="true" />
                <span>{t("settings.accessibility", "Reading & Contrast")}</span>
              </label>

              <div className="theme-options-grid" style={{ marginTop: "var(--space-2)", marginBottom: "var(--space-4)" }}>
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
        </section>
      </div>
    </div>
  );
}
