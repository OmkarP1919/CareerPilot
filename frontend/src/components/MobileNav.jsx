import { NavLink, useLocation } from "react-router-dom";
import {
  Home,
  Briefcase,
  ClipboardList,
  User,
  MoreHorizontal,
} from "lucide-react";

const PRIMARY_NAV = [
  { to: "/dashboard", label: "Home", icon: Home },
  { to: "/jobs", label: "Jobs", icon: Briefcase },
  { to: "/applications", label: "Apps", icon: ClipboardList },
  { to: "/profile", label: "Profile", icon: User },
];

const SECONDARY_ROUTES = ["/resumes", "/analytics", "/settings"];

export default function MobileNav({ onMoreClick }) {
  const location = useLocation();

  const isSecondaryPage = SECONDARY_ROUTES.some((r) => location.pathname === r);

  return (
    <nav className="mobile-nav" aria-label="Mobile navigation">
      <div className="mobile-nav-items">
        {PRIMARY_NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `mobile-nav-item ${isActive ? "active" : ""}`
            }
          >
            <item.icon size={20} />
            <span>{item.label}</span>
          </NavLink>
        ))}
        <button
          className={`mobile-nav-item ${isSecondaryPage ? "active" : ""}`}
          onClick={onMoreClick}
          style={{ background: "none", border: "none" }}
          aria-label="More options"
        >
          <MoreHorizontal size={20} />
          <span>More</span>
        </button>
      </div>
    </nav>
  );
}
