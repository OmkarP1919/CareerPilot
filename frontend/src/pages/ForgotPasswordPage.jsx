import { useState } from "react";
import { Link } from "react-router-dom";
import { sendPasswordResetEmail } from "firebase/auth";
import { auth } from "../firebase";
import { Mail, ArrowLeft, ArrowRight, CheckCircle, AlertCircle } from "lucide-react";

function getFirebaseErrorMessage(code) {
  switch (code) {
    case "auth/user-not-found":
      return "If an account exists with this email, a reset link has been sent.";
    case "auth/invalid-email":
      return "Please enter a valid email address.";
    case "auth/too-many-requests":
      return "Too many reset attempts. Please try again in a few moments.";
    case "auth/network-request-failed":
      return "Network error. Please check your connection.";
    default:
      return "Unable to send reset email. Please try again.";
  }
}

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    if (!email) {
      setError("Please enter your email address.");
      return;
    }

    setLoading(true);
    try {
      await sendPasswordResetEmail(auth, email.trim());
      setSent(true);
    } catch (err) {
      if (err.code === "auth/user-not-found") {
        setSent(true);
      } else {
        setError(getFirebaseErrorMessage(err.code));
      }
    } finally {
      setLoading(false);
    }
  };

  if (sent) {
    return (
      <div className="auth-form-wrapper" style={{ textAlign: "center" }}>
        <div className="auth-success-icon-wrap">
          <CheckCircle size={32} />
        </div>
        <h2>Check your email</h2>
        <p className="auth-subtitle">
          We've sent password reset instructions to<br />
          <strong>{email}</strong>
        </p>
        <p className="auth-reset-hint">
          Didn't receive the email? Check your spam folder or try another address.
        </p>

        <button
          className="btn btn-secondary btn-block"
          onClick={() => { setSent(false); setEmail(""); }}
          type="button"
          style={{ marginTop: "var(--space-4)" }}
        >
          Try a different email
        </button>

        <div className="auth-footer" style={{ marginTop: "var(--space-6)" }}>
          <Link to="/login" className="auth-back-link">
            <ArrowLeft size={14} />
            <span>Back to sign in</span>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-form-wrapper">
      <div className="auth-form-header">
        <h2>Reset your password</h2>
        <p className="auth-subtitle">
          Enter your registered email and we'll send you a recovery link
        </p>
      </div>

      {error && (
        <div className="alert alert-error" role="alert">
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="auth-form" noValidate>
        <div className="form-group">
          <label className="form-label" htmlFor="reset-email">
            Email Address
          </label>
          <div className="input-with-icon">
            <Mail size={16} className="input-icon" />
            <input
              id="reset-email"
              type="email"
              className="form-input with-left-icon"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              required
            />
          </div>
        </div>

        <button
          type="submit"
          className="btn btn-primary btn-block btn-lg"
          disabled={loading}
          style={{ marginTop: "var(--space-2)" }}
        >
          {loading ? (
            <>
              <span className="spinner-inline" />
              <span>Sending link...</span>
            </>
          ) : (
            <>
              <span>Send Reset Link</span>
              <ArrowRight size={16} />
            </>
          )}
        </button>
      </form>

      <div className="auth-footer">
        <Link to="/login" className="auth-back-link">
          <ArrowLeft size={14} />
          <span>Back to sign in</span>
        </Link>
      </div>
    </div>
  );
}
