import { Outlet, Link, useLocation } from "react-router-dom";
import { Sparkles, ShieldCheck, ArrowRight, ArrowLeft } from "lucide-react";

export default function AuthLayout() {
  const location = useLocation();
  const isSignup = location.pathname.includes("signup");
  const isForgot = location.pathname.includes("forgot");

  return (
    <div className="auth-split-layout">
      <div className={`auth-split-container ${isSignup ? "layout-signup" : "layout-signin"}`}>
        {/* =========================================================================
            BANNER PANE (Switches sides based on Sign In vs Sign Up)
            - On /login & /forgot-password: sits on the RIGHT side ("Create Account")
            - On /signup: sits on the LEFT side ("Welcome Back / Sign In")
            ========================================================================= */}
        <aside className="auth-interactive-banner">
          <div className="auth-banner-inner">
            <Link to="/" className="auth-banner-logo" aria-label="CareerPilot AI Home">
              <span className="topnav-logo-mark">
                <Sparkles size={16} />
              </span>
              <span className="topnav-logo-text">CareerPilot</span>
              <span className="topnav-logo-badge">AI</span>
            </Link>

            <div className="auth-banner-content">
              {isSignup ? (
                <>
                  <div className="auth-banner-tag">
                    <ShieldCheck size={14} />
                    <span>Welcome Back</span>
                  </div>

                  <h2 className="auth-banner-title">Already have an account?</h2>
                  <p className="auth-banner-desc">
                    Sign in to access your saved roles, fit scores, and tailored resumes.
                  </p>

                  <div className="banner-action-wrap">
                    <Link to="/login" className="btn-banner-switch">
                      <ArrowLeft size={18} />
                      <span>Sign In</span>
                    </Link>
                  </div>
                </>
              ) : isForgot ? (
                <>
                  <div className="auth-banner-tag">
                    <ShieldCheck size={14} />
                    <span>Account Security</span>
                  </div>

                  <h2 className="auth-banner-title">Remember your credentials?</h2>
                  <p className="auth-banner-desc">
                    Sign back in with your email and password to access your career workspace.
                  </p>

                  <div className="banner-action-wrap">
                    <Link to="/login" className="btn-banner-switch">
                      <ArrowLeft size={18} />
                      <span>Back to Sign In</span>
                    </Link>
                  </div>
                </>
              ) : (
                <>
                  <div className="auth-banner-tag">
                    <Sparkles size={14} />
                    <span>Hello, Friend!</span>
                  </div>

                  <h2 className="auth-banner-title">New to CareerPilot?</h2>
                  <p className="auth-banner-desc">
                    Enter your personal details and start your journey with precision AI job matching.
                  </p>

                  <div className="banner-action-wrap">
                    <Link to="/signup" className="btn-banner-switch">
                      <span>Create Account</span>
                      <ArrowRight size={18} />
                    </Link>
                  </div>
                </>
              )}
            </div>

            <div className="auth-banner-footer">
              <span>&copy; {new Date().getFullYear()} CareerPilot AI. Precision Career Intelligence.</span>
            </div>
          </div>
        </aside>

        {/* =========================================================================
            FORM PANE (Holds Login, Signup, or Forgot Password form)
            ========================================================================= */}
        <main className="auth-form-pane">
          <div className="auth-form-container">
            {/* Mobile Header Logo */}
            <div className="auth-mobile-header">
              <Link to="/" className="auth-brand-logo" aria-label="CareerPilot AI Home">
                <span className="topnav-logo-mark">
                  <Sparkles size={16} />
                </span>
                <span className="topnav-logo-text">CareerPilot</span>
                <span className="topnav-logo-badge">AI</span>
              </Link>
            </div>

            <div className="auth-card-inner">
              <Outlet />
            </div>

            <div className="auth-form-footer">
              <span>Protected by 256-bit encryption & Firebase Authentication</span>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
