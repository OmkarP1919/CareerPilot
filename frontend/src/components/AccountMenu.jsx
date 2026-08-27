import { useEffect } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { signOut } from "firebase/auth";
import { auth } from "../firebase";
import { useAuth } from "../context/AuthContext";
import { getInitials } from "../utils/formatters";
import { FileText, TrendingUp, Settings, LogOut, X } from "lucide-react";

const MENU_ITEMS = [
  { to: "/resumes", label: "Resumes Hub", icon: FileText, desc: "Manage master & tailored versions" },
  { to: "/insights", label: "Career Insights", icon: TrendingUp, desc: "Skill gaps & funnel analytics" },
  { to: "/settings", label: "Settings", icon: Settings, desc: "Account security & preferences" },
];

export default function AccountMenu({ onClose, isMobile = false }) {
  const navigate = useNavigate();
  const { currentUser } = useAuth();

  const displayName = currentUser?.displayName || currentUser?.email?.split("@")[0] || "User";
  const email = currentUser?.email || "";
  const initials = getInitials(displayName);

  // Close mobile drawer on escape
  useEffect(() => {
    if (!isMobile) return;
    const handleKey = (e) => {
      if (e.key === "Escape") onClose?.();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [isMobile, onClose]);

  const handleLogout = async () => {
    try {
      await signOut(auth);
      onClose?.();
      navigate("/login");
    } catch (err) {
      console.error("Logout error:", err);
    }
  };

  if (isMobile) {
    return (
      <div
        className="mobile-sheet-overlay open"
        onClick={onClose}
        role="dialog"
        aria-modal="true"
        aria-label="Account and more options"
      >
        <div className="mobile-sheet" onClick={(e) => e.stopPropagation()}>
          <div className="mobile-sheet-handle" />
          
          <div className="mobile-sheet-header">
            <div className="mobile-sheet-user">
              <div className="topnav-avatar">
                {currentUser?.photoURL ? (
                  <img src={currentUser.photoURL} alt={displayName} />
                ) : (
                  <span>{initials}</span>
                )}
              </div>
              <div>
                <div className="account-menu-name">{displayName}</div>
                <div className="account-menu-email">{email}</div>
              </div>
            </div>
            <button
              className="btn btn-ghost btn-icon btn-sm"
              onClick={onClose}
              aria-label="Close menu"
            >
              <X size={18} />
            </button>
          </div>

          <nav className="mobile-sheet-nav">
            {MENU_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={onClose}
                className={({ isActive }) =>
                  `mobile-sheet-item ${isActive ? "active" : ""}`
                }
              >
                <item.icon size={20} />
                <div className="mobile-sheet-item-info">
                  <span className="mobile-sheet-item-title">{item.label}</span>
                  <span className="mobile-sheet-item-desc">{item.desc}</span>
                </div>
              </NavLink>
            ))}

            <div className="mobile-sheet-divider" />

            <button
              onClick={handleLogout}
              className="mobile-sheet-item danger"
              type="button"
            >
              <LogOut size={20} />
              <div className="mobile-sheet-item-info">
                <span className="mobile-sheet-item-title">Sign Out</span>
              </div>
            </button>
          </nav>
        </div>
      </div>
    );
  }

  return (
    <div
      className="account-menu"
      role="menu"
      aria-label="User account options"
    >
      <div className="account-menu-header">
        <div className="account-menu-name">{displayName}</div>
        <div className="account-menu-email">{email}</div>
      </div>

      <div className="account-menu-list">
        {MENU_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            onClick={onClose}
            className={({ isActive }) =>
              `account-menu-item ${isActive ? "active" : ""}`
            }
            role="menuitem"
          >
            <item.icon size={16} />
            <span>{item.label}</span>
          </NavLink>
        ))}
      </div>

      <div className="account-menu-divider" />

      <button
        onClick={handleLogout}
        className="account-menu-item danger"
        role="menuitem"
        type="button"
      >
        <LogOut size={16} />
        <span>Sign Out</span>
      </button>
    </div>
  );
}
