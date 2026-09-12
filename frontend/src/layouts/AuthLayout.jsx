import { Outlet, Link, useLocation } from "react-router-dom";
import { useTheme } from "../context/ThemeContext";
import {
  ShieldCheck,
  CheckCircle2,
  Sun,
  Moon,
  ArrowLeft,
  Briefcase,
} from "lucide-react";

export default function AuthLayout() {
  const location = useLocation();
  const { theme, setTheme } = useTheme();
  const isSignup = location.pathname.includes("signup");
  const isForgot = location.pathname.includes("forgot-password");

  const handleToggleTheme = () => {
    const isDark = document.documentElement.getAttribute("data-theme") === "dark";
    setTheme(isDark ? "light" : "dark");
  };

  return (
    <div className="auth-page-root">
      {/* Top Header Bar with Back-to-Home and Theme Switcher */}
      <header className="auth-header-bar" aria-label="Authentication Header">
        <Link to="/" className="auth-back-brand" aria-label="Back to CareerPilot Home">
          <ArrowLeft size={16} className="auth-back-arrow" />
          <span className="auth-logo-mark">
            <span className="auth-logo-dot" />
          </span>
          <span className="auth-logo-text">CareerPilot</span>
        </Link>

        <button
          type="button"
          className="btn btn-ghost btn-icon btn-sm auth-theme-toggle"
          onClick={handleToggleTheme}
          aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        >
          {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
        </button>
      </header>

      {/* Centered Area: 2-Column on Desktop (>=1024px), Single Focused Column on Tablet & Mobile */}
      <main className="auth-main-area" id="auth-main-content">
        <div className="auth-layout-container">
          {/* Subtle Desktop Value Sidebar (>=1024px only) */}
          <aside className="auth-showcase-sidebar" aria-label="CareerPilot Benefits">
            <div className="auth-sidebar-inner">
              <div className="auth-sidebar-header">
                <div className="auth-sidebar-brand-pill">
                  <span className="auth-logo-mark-sm">
                    <span className="auth-logo-dot-sm" />
                  </span>
                  <span>{isForgot ? "Account Security" : "Career Intelligence"}</span>
                </div>
              </div>

              <div className="auth-sidebar-body">
                <h2 className="auth-sidebar-headline">
                  {isForgot
                    ? "Secure account recovery."
                    : isSignup
                    ? "Start applying with complete clarity."
                    : "Welcome back to your career workspace."}
                </h2>
                <p className="auth-sidebar-copy">
                  {isForgot
                    ? "Enter your registered email address to securely restore access to your career workspace, saved opportunities, and tailored resumes."
                    : isSignup
                    ? "Discover verified opportunities, evaluate honest 5-factor fit scores, and tailor resumes safely without fabricated experience."
                    : "Access your saved roles, customized fit analysis, and synchronized application tracker."}
                </p>

                <div className="auth-sidebar-benefits">
                  <div className="sidebar-benefit-item">
                    <CheckCircle2 size={16} className="text-accent flex-shrink-0" />
                    <span>Transparent 5-factor fit scoring</span>
                  </div>
                  <div className="sidebar-benefit-item">
                    <ShieldCheck size={16} className="text-accent flex-shrink-0" />
                    <span>Fact-preserving resume tailoring</span>
                  </div>
                  <div className="sidebar-benefit-item">
                    <Briefcase size={16} className="text-accent flex-shrink-0" />
                    <span>Unified application tracking pipeline</span>
                  </div>
                </div>
              </div>

              <div className="auth-sidebar-footer">
                <ShieldCheck size={14} className="text-tertiary flex-shrink-0" />
                <span className="auth-sidebar-footnote">
                  Private & secure • Zero fabricated credentials
                </span>
              </div>
            </div>
          </aside>

          {/* Form Column */}
          <section className="auth-form-column" aria-label="Authentication Form">
            <div className="auth-form-card">
              <Outlet />
            </div>

            <div className="auth-trust-footer">
              <span>Protected by Firebase Secure Authentication</span>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
