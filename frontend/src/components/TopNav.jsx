import { useState, useRef, useEffect } from "react";
import { NavLink, Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { getInitials } from "../utils/formatters";
import AccountMenu from "./AccountMenu";
import {
  Compass,
  Briefcase,
  Layers,
  User,
  ChevronDown,
  Sparkles,
} from "lucide-react";

const NAV_ITEMS = [
  { to: "/home", label: "Home", icon: Compass },
  { to: "/discover", label: "Discover", icon: Briefcase },
  { to: "/pipeline", label: "Pipeline", icon: Layers },
  { to: "/profile", label: "My Career", icon: User },
];

export default function TopNav() {
  const { currentUser } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);

  const displayName = currentUser?.displayName || currentUser?.email?.split("@")[0] || "User";
  const initials = getInitials(displayName);

  useEffect(() => {
    if (!menuOpen) return;
    const handleClick = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false);
      }
    };
    const handleKey = (e) => {
      if (e.key === "Escape") setMenuOpen(false);
    };
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKey);
    };
  }, [menuOpen]);

  return (
    <header className="topnav" aria-label="Main navigation">
      <div className="topnav-inner">
        <div className="topnav-left">
          <Link to="/home" className="topnav-logo" aria-label="CareerPilot AI Home">
            <span className="topnav-logo-mark">
              <Sparkles size={16} />
            </span>
            <span className="topnav-logo-text">CareerPilot</span>
            <span className="topnav-logo-badge">AI</span>
          </Link>

          <nav className="topnav-links" aria-label="Workspace links">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `topnav-link ${isActive ? "active" : ""}`
                }
              >
                <item.icon size={16} />
                <span>{item.label}</span>
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="topnav-right" ref={menuRef}>
          <button
            className={`topnav-user-btn ${menuOpen ? "open" : ""}`}
            onClick={() => setMenuOpen((p) => !p)}
            aria-label="User account menu"
            aria-expanded={menuOpen}
            aria-haspopup="true"
          >
            <div className="topnav-avatar">
              {currentUser?.photoURL ? (
                <img src={currentUser.photoURL} alt={displayName} />
              ) : (
                <span>{initials}</span>
              )}
            </div>
            <span className="topnav-username">{displayName}</span>
            <ChevronDown size={14} className="topnav-chevron" />
          </button>

          {menuOpen && (
            <AccountMenu onClose={() => setMenuOpen(false)} />
          )}
        </div>
      </div>
    </header>
  );
}
