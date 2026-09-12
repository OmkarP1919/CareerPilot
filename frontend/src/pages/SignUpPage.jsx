import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import {
  createUserWithEmailAndPassword,
  updateProfile,
  signInWithPopup,
} from "firebase/auth";
import { auth, googleProvider } from "../firebase";
import { api } from "../services/api";
import { User, Mail, Lock, Eye, EyeOff, ArrowRight, AlertCircle, CheckCircle2, ShieldCheck } from "lucide-react";

function formatAuthError(err, defaultFallback = "Registration failed. Please try again.") {
  if (!err) return defaultFallback;

  // Handle backend ApiError (e.g. from /auth/sync, timeout, network, or server down)
  if (err.name === "ApiError" || err.kind) {
    if (err.kind === "network") {
      return "Unable to reach the backend server. Please verify the backend API is running.";
    }
    if (err.kind === "server") {
      return err.message && err.message !== "Something went wrong. Please try again."
        ? `Backend error: ${err.message}`
        : "Backend database or server error during registration sync. Please verify backend database connection.";
    }
    return err.message || "Backend synchronization failed.";
  }

  // Handle Firebase Auth error codes
  const code = err.code || (typeof err === "string" ? err : "");
  switch (code) {
    case "auth/email-already-in-use":
      return "An account with this email already exists. Try signing in instead.";
    case "auth/invalid-email":
      return "Please enter a valid email address.";
    case "auth/weak-password":
      return "Password should be at least 6 characters long.";
    case "auth/too-many-requests":
      return "Too many attempts. Please try again in a few moments.";
    case "auth/network-request-failed":
      return "Network issue connecting to Firebase. Please check your internet connection.";
    case "auth/popup-blocked":
      return "Sign-in popup was blocked by your browser. Please allow popups for this site.";
    case "auth/unauthorized-domain":
      return "This domain is not authorized for OAuth in Firebase. Add localhost to Authorized Domains in Firebase Console.";
    case "auth/operation-not-allowed":
      return "This sign-in method is not enabled in Firebase Console.";
    default:
      return err.message || defaultFallback;
  }
}

export default function SignUpPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const syncAndRedirect = async () => {
    await api.post("/auth/sync", {});
    navigate("/home");
  };

  const handleEmailSignUp = async (e) => {
    e.preventDefault();
    setError("");

    if (!name.trim()) {
      setError("Please enter your full name.");
      return;
    }
    if (!email) {
      setError("Please enter a valid email address.");
      return;
    }
    if (password.length < 6) {
      setError("Password must be at least 6 characters long.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      const credential = await createUserWithEmailAndPassword(auth, email.trim(), password);
      if (name.trim()) {
        await updateProfile(credential.user, { displayName: name.trim() });
      }
      await syncAndRedirect();
    } catch (err) {
      console.error("Sign up error:", err);
      setError(formatAuthError(err, "Registration failed. Please try again."));
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSignUp = async () => {
    setError("");
    setLoading(true);
    try {
      await signInWithPopup(auth, googleProvider);
      await syncAndRedirect();
    } catch (err) {
      if (err.code === "auth/popup-closed-by-user") return;
      console.error("Google sign up error:", err);
      setError(formatAuthError(err, "Google sign up failed. Please try again."));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-form-wrapper">
      <div className="auth-form-header">
        <h1 className="auth-title">Create your account</h1>
        <p className="auth-subtitle">Start your job search with transparent AI matching</p>
      </div>

      {error && (
        <div id="signup-error-alert" className="alert alert-error auth-alert" role="alert">
          <AlertCircle size={16} className="flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Google Authentication */}
      <button
        className="btn btn-google btn-block auth-google-btn"
        onClick={handleGoogleSignUp}
        disabled={loading}
        type="button"
        aria-label="Sign up with Google"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" className="auth-google-icon">
          <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/>
          <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
          <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
          <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
        </svg>
        <span>Sign up with Google</span>
      </button>

      <div className="auth-divider" role="separator" aria-label="Or sign up with email">
        <span>or sign up with email</span>
      </div>

      {/* Registration Form */}
      <form onSubmit={handleEmailSignUp} className="auth-form" noValidate>
        <div className="form-group">
          <label className="form-label" htmlFor="signup-name">
            Full Name
          </label>
          <div className="input-with-icon">
            <User size={16} className="input-icon" />
            <input
              id="signup-name"
              type="text"
              className={`form-input with-left-icon auth-input ${error && !name.trim() ? "error" : ""}`}
              placeholder="Alex Johnson"
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoComplete="name"
              required
              aria-invalid={error && !name.trim() ? "true" : undefined}
              aria-describedby={error && !name.trim() ? "signup-error-alert" : undefined}
            />
          </div>
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="signup-email">
            Email Address
          </label>
          <div className="input-with-icon">
            <Mail size={16} className="input-icon" />
            <input
              id="signup-email"
              type="email"
              className={`form-input with-left-icon auth-input ${error && (!email || error.toLowerCase().includes("email")) ? "error" : ""}`}
              placeholder="alex@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              required
              aria-invalid={error && (!email || error.toLowerCase().includes("email")) ? "true" : undefined}
              aria-describedby={error && (!email || error.toLowerCase().includes("email")) ? "signup-error-alert" : undefined}
            />
          </div>
        </div>

        <div className="form-group">
          <div className="form-label-row">
            <label className="form-label" htmlFor="signup-password">
              Password
            </label>
            <span id="signup-password-hint" className="form-hint">
              At least 6 characters
            </span>
          </div>
          <div className="input-with-icon">
            <Lock size={16} className="input-icon" />
            <input
              id="signup-password"
              type={showPassword ? "text" : "password"}
              className={`form-input with-left-icon with-right-icon auth-input ${error && (password.length < 6 || password !== confirmPassword) ? "error" : ""}`}
              placeholder="At least 6 characters"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              required
              aria-invalid={error && (password.length < 6 || password !== confirmPassword) ? "true" : undefined}
              aria-describedby={
                error && (password.length < 6 || password !== confirmPassword)
                  ? "signup-error-alert signup-password-hint"
                  : "signup-password-hint"
              }
            />
            <button
              type="button"
              className="input-action-btn auth-pwd-toggle"
              onClick={() => setShowPassword(!showPassword)}
              aria-label={showPassword ? "Hide password" : "Show password"}
            >
              {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="signup-confirm">
            Confirm Password
          </label>
          <div className="input-with-icon">
            <Lock size={16} className="input-icon" />
            <input
              id="signup-confirm"
              type={showPassword ? "text" : "password"}
              className={`form-input with-left-icon auth-input ${error && password !== confirmPassword ? "error" : ""}`}
              placeholder="Re-enter your password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              autoComplete="new-password"
              required
              aria-invalid={error && password !== confirmPassword ? "true" : undefined}
              aria-describedby={
                error && password !== confirmPassword
                  ? "signup-error-alert"
                  : confirmPassword && password === confirmPassword
                  ? "signup-password-match"
                  : undefined
              }
            />
          </div>
          {confirmPassword && password === confirmPassword && (
            <span id="signup-password-match" className="auth-helper-success" aria-live="polite">
              <CheckCircle2 size={12} className="flex-shrink-0" />
              <span>Passwords match</span>
            </span>
          )}
        </div>

        <button
          type="submit"
          className="btn btn-primary btn-block btn-lg auth-submit-btn"
          disabled={loading}
        >
          {loading ? (
            <>
              <span className="spinner-inline" />
              <span>Creating account...</span>
            </>
          ) : (
            <>
              <span>Create Free Account</span>
              <ArrowRight size={16} />
            </>
          )}
        </button>

        <p className="auth-terms-notice">
          By creating an account, you agree to our Terms of Service and Privacy Policy.
        </p>
      </form>

      {/* Switch to Login */}
      <div className="auth-switch-box">
        <span>Already have an account?</span>{" "}
        <Link to="/login" className="auth-switch-link">
          Sign in
        </Link>
      </div>

      <div className="auth-micro-trust">
        <ShieldCheck size={13} className="text-accent flex-shrink-0" />
        <span>100% Fact-preserving AI • Zero fabricated credentials</span>
      </div>
    </div>
  );
}
