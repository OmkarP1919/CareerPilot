import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function ProtectedRoute() {
  const { currentUser, loading } = useAuth();

  if (loading) {
    return (
      <div className="app-layout">
        <div className="topnav" style={{ opacity: 0.5 }}>
          <div className="topnav-inner">
            <div className="topnav-left">
              <div className="skeleton" style={{ width: 120, height: 24, borderRadius: 6 }} />
              <div style={{ display: "flex", gap: "var(--space-2)" }}>
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="skeleton" style={{ width: 64, height: 28, borderRadius: 6 }} />
                ))}
              </div>
            </div>
          </div>
        </div>
        <main className="main-content">
          <div className="page">
            <div style={{ maxWidth: 800, margin: "0 auto" }}>
              <div className="skeleton skeleton-title" style={{ width: 200, marginBottom: "var(--space-8)" }} />
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
                {[1, 2, 3].map((i) => (
                  <div key={i} className="skeleton-card">
                    <div className="skeleton skeleton-title" style={{ width: "40%" }} />
                    <div className="skeleton skeleton-text" />
                    <div className="skeleton skeleton-text" style={{ width: "70%" }} />
                  </div>
                ))}
              </div>
            </div>
          </div>
        </main>
      </div>
    );
  }

  if (!currentUser) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
