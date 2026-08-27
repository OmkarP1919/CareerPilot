import { NavLink } from "react-router-dom";
import { Compass, Briefcase, Layers, User, MoreHorizontal } from "lucide-react";

const NAV_ITEMS = [
  { to: "/home", label: "Home", icon: Compass },
  { to: "/discover", label: "Discover", icon: Briefcase },
  { to: "/pipeline", label: "Pipeline", icon: Layers },
  { to: "/profile", label: "My Career", icon: User },
];

export default function BottomNav({ onMoreClick }) {
  return (
    <nav className="bottom-nav" aria-label="Mobile workspace navigation">
      <div className="bottom-nav-inner">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `bottom-nav-item ${isActive ? "active" : ""}`
            }
          >
            <item.icon size={20} />
            <span>{item.label}</span>
          </NavLink>
        ))}
        <button
          className="bottom-nav-item"
          onClick={onMoreClick}
          aria-label="More workspace options"
          type="button"
        >
          <MoreHorizontal size={20} />
          <span>More</span>
        </button>
      </div>
    </nav>
  );
}
