import { Outlet, Link } from "react-router-dom";
import { Sparkles } from "lucide-react";

export default function AuthLayout() {
  return (
    <div className="auth-layout">
      <div className="auth-container">
        <header className="auth-header">
          <Link to="/" className="auth-logo" aria-label="CareerPilot AI Home">
            <span className="topnav-logo-mark">
              <Sparkles size={16} />
            </span>
            <span className="topnav-logo-text">CareerPilot</span>
            <span className="topnav-logo-badge">AI</span>
          </Link>
        </header>

        <main className="auth-card">
          <Outlet />
        </main>

        <footer className="auth-page-footer">
          <p>&copy; {new Date().getFullYear()} CareerPilot AI. Precision Career Intelligence.</p>
        </footer>
      </div>
    </div>
  );
}
