import { NavLink } from "react-router-dom";
import { FileText, BarChart3, Settings, LogOut } from "lucide-react";
import { signOut } from "firebase/auth";
import { useNavigate } from "react-router-dom";
import { auth } from "../firebase";

const items = [
  { to: "/resumes", label: "Resumes", icon: FileText },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/settings", label: "Settings", icon: Settings },
];

export default function MobileMoreMenu({ isOpen, onClose }) {
  const navigate = useNavigate();

  const handleLogout = async () => {
    try {
      await signOut(auth);
      navigate("/");
    } catch {
      // silent
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose} style={{ alignItems: "flex-end" }}>
      <div
        className="modal"
        onClick={(e) => e.stopPropagation()}
        style={{
          maxWidth: "100%",
          width: "100%",
          borderRadius: "var(--radius-xl) var(--radius-xl) 0 0",
          maxHeight: "60vh",
          animation: "slide-up 0.3s ease",
        }}
      >
        <div className="modal-body" style={{ padding: "var(--space-4)" }}>
          <div style={{
            width: 40,
            height: 4,
            background: "var(--gray-300)",
            borderRadius: "var(--radius-full)",
            margin: "0 auto var(--space-5)",
          }} />
          <nav style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
            {items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={onClose}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--space-3)",
                  padding: "var(--space-3) var(--space-4)",
                  borderRadius: "var(--radius-md)",
                  color: "var(--text-primary)",
                  textDecoration: "none",
                  fontSize: "var(--text-sm)",
                  fontWeight: "var(--font-medium)",
                }}
              >
                <item.icon size={18} style={{ color: "var(--text-secondary)" }} />
                {item.label}
              </NavLink>
            ))}
            <hr style={{ border: "none", borderTop: "1px solid var(--border-color)", margin: "var(--space-2) 0" }} />
            <button
              onClick={() => { onClose(); handleLogout(); }}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "var(--space-3)",
                padding: "var(--space-3) var(--space-4)",
                borderRadius: "var(--radius-md)",
                color: "var(--color-danger)",
                fontSize: "var(--text-sm)",
                fontWeight: "var(--font-medium)",
                width: "100%",
                textAlign: "left",
              }}
            >
              <LogOut size={18} />
              Sign Out
            </button>
          </nav>
        </div>
      </div>
      <style>{`
        @keyframes slide-up {
          from { transform: translateY(100%); }
          to { transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}
