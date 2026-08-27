import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { signOut } from "firebase/auth";
import { auth } from "../firebase";
import { useAuth } from "../context/AuthContext";
import Modal from "../components/Modal";
import {
  User,
  Shield,
  Info,
  LogOut,
  Trash2,
  Lock,
  Mail,
  Calendar,
  CheckCircle2,
} from "lucide-react";

export default function SettingsPage() {
  const { currentUser } = useAuth();
  const navigate = useNavigate();
  const [showConfirm, setShowConfirm] = useState(false);

  const handleLogout = async () => {
    try {
      await signOut(auth);
      navigate("/");
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
  const created = currentUser?.metadata?.creationTime;
  const lastSignIn = currentUser?.metadata?.lastSignInTime;

  const initials = displayName
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2) || "U";

  return (
    <div className="page">
      {/* === Page Header === */}
      <header className="page-header">
        <div className="page-header-row">
          <div>
            <h1>Settings & Preferences</h1>
            <p>Manage your account identity, security, and workspace preferences</p>
          </div>
        </div>
      </header>

      <div className="settings-grid-layout">
        {/* === User Identity Card === */}
        <section className="card">
          <div className="card-header">
            <h2 style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <User size={18} className="text-accent" />
              <span>Account Identity</span>
            </h2>
          </div>
          <div className="card-body">
            <div className="settings-user-profile-row">
              {photoURL ? (
                <img src={photoURL} alt="Profile" className="settings-avatar-img" />
              ) : (
                <div className="settings-avatar-fallback">{initials}</div>
              )}
              <div>
                <h3 className="settings-user-name">{displayName}</h3>
                <span className="settings-user-email">{email}</span>
                <div className="settings-verified-badge">
                  <CheckCircle2 size={12} className="text-success" />
                  <span>Authenticated Account</span>
                </div>
              </div>
            </div>

            <div className="settings-info-table">
              <div className="settings-info-row">
                <span className="info-label">Authentication Provider</span>
                <span className="info-val">{authProvider}</span>
              </div>
              <div className="settings-info-row">
                <span className="info-label">Account Created</span>
                <span className="info-val">
                  {created ? new Date(created).toLocaleDateString() : "Active"}
                </span>
              </div>
              <div className="settings-info-row">
                <span className="info-label">Last Session</span>
                <span className="info-val">
                  {lastSignIn ? new Date(lastSignIn).toLocaleDateString() : "Current session"}
                </span>
              </div>
            </div>
          </div>
        </section>

        {/* === Security & Data Privacy === */}
        <section className="card">
          <div className="card-header">
            <h2 style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <Shield size={18} className="text-accent" />
              <span>Security & Data Privacy</span>
            </h2>
          </div>
          <div className="card-body">
            <p className="text-secondary" style={{ fontSize: "var(--text-sm)", lineHeight: "var(--leading-relaxed)" }}>
              Your career profile, resumes, and tracked applications are encrypted and stored in your private PostgreSQL workspace.
              CareerPilot AI never sells your career information or shares your data with third-party recruiters without your consent.
            </p>

            <div className="settings-security-pills">
              <div className="security-pill">
                <Lock size={14} className="text-accent" />
                <span>SSL / TLS Encrypted Transit</span>
              </div>
              <div className="security-pill">
                <Shield size={14} className="text-success" />
                <span>Firebase Secure Session Tokens</span>
              </div>
            </div>
          </div>
        </section>

        {/* === Session & Account Actions === */}
        <section className="card">
          <div className="card-header">
            <h2>Account Management</h2>
          </div>
          <div className="card-body">
            <div className="settings-actions-group">
              <button className="btn btn-outline" onClick={handleLogout} type="button">
                <LogOut size={16} />
                <span>Sign Out of CareerPilot</span>
              </button>

              <button
                className="btn btn-ghost btn-danger"
                onClick={() => setShowConfirm(true)}
                type="button"
              >
                <Trash2 size={16} />
                <span>Delete Account & Clear Data</span>
              </button>
            </div>
          </div>
        </section>
      </div>

      {/* === Delete Confirmation Modal === */}
      {showConfirm && (
        <Modal
          isOpen={showConfirm}
          onClose={() => setShowConfirm(false)}
          title="Account Deletion Request"
          footer={
            <button className="btn btn-outline btn-sm" onClick={() => setShowConfirm(false)}>
              Close
            </button>
          }
        >
          <p style={{ fontSize: "var(--text-sm)", color: "var(--text-secondary)" }}>
            Self-service account deletion will be available in the upcoming release. If you wish to purge your profile data immediately, please contact support.
          </p>
        </Modal>
      )}
    </div>
  );
}
