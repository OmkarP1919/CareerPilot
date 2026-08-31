import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { signOut } from "firebase/auth";
import { auth } from "../firebase";
import { useAuth } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";
import { useTranslation } from "../context/LanguageContext";
import Modal from "../components/Modal";
import {
  User,
  Shield,
  Palette,
  Globe,
  Eye,
  Bell,
  Trash2,
  LogOut,
  CheckCircle2,
  Lock,
  Sun,
  Moon,
  Laptop,
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

  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const handleLogout = async () => {
    try {
      await signOut(auth);
      navigate("/login");
    } catch (err) {
      console.error("Logout error:", err);
    }
  };

  const displayName = currentUser?.displayName || "Not specified";
  const email = currentUser?.email || "Not specified";
  const photoURL = currentUser?.photoURL;
  const providerData = currentUser?.providerData || [];
  const authProvider =
    providerData.length > 0
      ? providerData[0].providerId === "google.com"
        ? "Google Authentication"
        : providerData[0].providerId
      : "Firebase Email / Password";

  return (
    <div className="page settings-page">
      {/* Page Header */}
      <header className="page-header">
        <div className="page-header-row">
          <div>
            <h1>{t("settings.title", "Settings & Preferences")}</h1>
            <p>Manage your account identity, workspace appearance, language, and accessibility.</p>
          </div>
        </div>
      </header>

      <div className="settings-sections-stack">
        {/* =========================================================================
            SECTION 1: ACCOUNT IDENTITY
            ========================================================================= */}
        <section className="card settings-card">
          <div className="card-header">
            <h2 style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <User size={18} className="text-accent" />
              <span>{t("settings.account", "Account Identity")}</span>
            </h2>
          </div>
          <div className="card-body">
            <div className="settings-user-profile-row">
              <div className="settings-avatar-circle">
                {photoURL ? (
                  <img src={photoURL} alt="Profile" className="settings-avatar-img" />
                ) : (
                  <span>{displayName.slice(0, 2).toUpperCase()}</span>
                )}
              </div>
              <div className="settings-user-info">
                <h3 className="settings-user-name">{displayName}</h3>
                <span className="settings-user-email">{email}</span>
                <div className="settings-verified-badge">
                  <CheckCircle2 size={13} className="text-success" />
                  <span>Authenticated via {authProvider}</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* =========================================================================
            SECTION 2: APPEARANCE (THEME)
            ========================================================================= */}
        <section className="card settings-card">
          <div className="card-header">
            <h2 style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <Palette size={18} className="text-accent" />
              <span>{t("settings.appearance", "Appearance")}</span>
            </h2>
          </div>
          <div className="card-body">
            <p className="text-secondary text-sm" style={{ marginBottom: "var(--space-3)" }}>
              Select your interface color scheme. CareerPilot supports authentic light, deep charcoal dark, and system themes.
            </p>

            <div className="theme-options-grid">
              <button
                type="button"
                className={`theme-option-card ${theme === "light" ? "active" : ""}`}
                onClick={() => setTheme("light")}
              >
                <Sun size={20} />
                <span>{t("settings.themeLight", "Light")}</span>
              </button>

              <button
                type="button"
                className={`theme-option-card ${theme === "dark" ? "active" : ""}`}
                onClick={() => setTheme("dark")}
              >
                <Moon size={20} />
                <span>{t("settings.themeDark", "Dark")}</span>
              </button>

              <button
                type="button"
                className={`theme-option-card ${theme === "system" ? "active" : ""}`}
                onClick={() => setTheme("system")}
              >
                <Laptop size={20} />
                <span>{t("settings.themeSystem", "System")}</span>
              </button>
            </div>
          </div>
        </section>

        {/* =========================================================================
            SECTION 3: LANGUAGE
            ========================================================================= */}
        <section className="card settings-card">
          <div className="card-header">
            <h2 style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <Globe size={18} className="text-accent" />
              <span>{t("settings.language", "Language")}</span>
            </h2>
          </div>
          <div className="card-body">
            <p className="text-secondary text-sm" style={{ marginBottom: "var(--space-3)" }}>
              Choose your interface display language. Note that external job listings and original resume contents remain in their source format.
            </p>

            <div className="theme-options-grid">
              <button
                type="button"
                className={`theme-option-card ${language === "en" ? "active" : ""}`}
                onClick={() => setLanguage("en")}
              >
                <span className="lang-name font-medium">English</span>
                <span className="text-xs text-muted">EN</span>
              </button>

              <button
                type="button"
                className={`theme-option-card ${language === "hi" ? "active" : ""}`}
                onClick={() => setLanguage("hi")}
              >
                <span className="lang-name font-medium">हिन्दी</span>
                <span className="text-xs text-muted">HI</span>
              </button>

              <button
                type="button"
                className={`theme-option-card ${language === "mr" ? "active" : ""}`}
                onClick={() => setLanguage("mr")}
              >
                <span className="lang-name font-medium">मराठी</span>
                <span className="text-xs text-muted">MR</span>
              </button>
            </div>
          </div>
        </section>

        {/* =========================================================================
            SECTION 4: ACCESSIBILITY & TEXT SCALING
            ========================================================================= */}
        <section className="card settings-card">
          <div className="card-header">
            <h2 style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <Eye size={18} className="text-accent" />
              <span>{t("settings.accessibility", "Accessibility")}</span>
            </h2>
          </div>
          <div className="card-body stack" style={{ gap: "var(--space-4)" }}>
            {/* Text Size */}
            <div>
              <label className="form-label">{t("settings.textSize", "Text Size")}</label>
              <div className="theme-options-grid" style={{ marginTop: "var(--space-2)" }}>
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
            </div>

            {/* High Contrast & Reduced Motion Toggles */}
            <div className="setting-toggle-row">
              <div>
                <strong>{t("settings.highContrast", "High Contrast")}</strong>
                <p className="text-xs text-muted">Enhances borders, text contrast, and active focus rings.</p>
              </div>
              <button
                type="button"
                className={`toggle-switch-btn ${highContrast ? "on" : "off"}`}
                onClick={() => setHighContrast(!highContrast)}
                aria-pressed={highContrast}
              >
                <span className="toggle-switch-handle" />
              </button>
            </div>

            <div className="setting-toggle-row">
              <div>
                <strong>{t("settings.reducedMotion", "Reduce Motion")}</strong>
                <p className="text-xs text-muted">Disables all non-essential interface animations and transitions.</p>
              </div>
              <button
                type="button"
                className={`toggle-switch-btn ${reducedMotion ? "on" : "off"}`}
                onClick={() => setReducedMotion(!reducedMotion)}
                aria-pressed={reducedMotion}
              >
                <span className="toggle-switch-handle" />
              </button>
            </div>
          </div>
        </section>

        {/* =========================================================================
            SECTION 5: NOTIFICATIONS & PRIVACY
            ========================================================================= */}
        <section className="card settings-card">
          <div className="card-header">
            <h2 style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <Shield size={18} className="text-accent" />
              <span>{t("settings.privacy", "Privacy & Data Protection")}</span>
            </h2>
          </div>
          <div className="card-body">
            <p className="text-secondary text-sm" style={{ lineHeight: "var(--leading-relaxed)" }}>
              Your profile, parsed resumes, and tracked applications are encrypted and stored in your private PostgreSQL workspace.
              CareerPilot AI never sells your career data to third-party recruiters.
            </p>

            <div className="settings-security-pills" style={{ marginTop: "var(--space-4)" }}>
              <div className="security-pill">
                <Lock size={14} className="text-accent" />
                <span>SSL / TLS Encrypted Transit</span>
              </div>
              <div className="security-pill">
                <Shield size={14} className="text-success" />
                <span>Firebase Secure Auth Sessions</span>
              </div>
            </div>
          </div>
        </section>

        {/* =========================================================================
            SECTION 6: DANGER ZONE & SESSION
            ========================================================================= */}
        <section className="card settings-card danger-card">
          <div className="card-header">
            <h2 className="text-danger" style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <Trash2 size={18} />
              <span>{t("settings.dangerZone", "Danger Zone & Sign Out")}</span>
            </h2>
          </div>
          <div className="card-body">
            <div className="settings-actions-group">
              <button className="btn btn-secondary" onClick={handleLogout} type="button">
                <LogOut size={16} />
                <span>Sign Out of CareerPilot</span>
              </button>

              <button
                className="btn btn-ghost btn-danger"
                onClick={() => setShowDeleteConfirm(true)}
                type="button"
              >
                <Trash2 size={16} />
                <span>Delete Account & Reset Workspace</span>
              </button>
            </div>
          </div>
        </section>
      </div>

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <Modal
          isOpen={showDeleteConfirm}
          onClose={() => setShowDeleteConfirm(false)}
          title="Account Deletion Request"
        >
          <div className="stack" style={{ gap: "var(--space-3)" }}>
            <p className="text-secondary text-sm">
              Self-service account deletion will be available in the upcoming release. If you wish to purge your profile data immediately, please reach out to support.
            </p>
            <div className="modal-footer" style={{ marginTop: "var(--space-4)" }}>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => setShowDeleteConfirm(false)}
                type="button"
              >
                Close
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
