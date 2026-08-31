import { NavLink } from "react-router-dom";
import { useTranslation } from "../context/LanguageContext";
import { Compass, Briefcase, FileText, Layers, MoreHorizontal } from "lucide-react";

export default function BottomNav({ onMoreClick }) {
  const { t } = useTranslation();

  const navItems = [
    { to: "/home", label: t("nav.home", "Home"), icon: Compass },
    { to: "/discover", label: t("nav.jobs", "Jobs"), icon: Briefcase },
    { to: "/resumes", label: t("nav.resumes", "Resume"), icon: FileText },
    { to: "/pipeline", label: t("nav.applications", "Applications"), icon: Layers },
  ];

  return (
    <nav className="bottom-nav" aria-label="Mobile workspace navigation">
      <div className="bottom-nav-inner">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `bottom-nav-item ${isActive ? "active" : ""}`
            }
          >
            <item.icon size={20} aria-hidden="true" />
            <span>{item.label}</span>
          </NavLink>
        ))}
        <button
          className="bottom-nav-item"
          onClick={onMoreClick}
          aria-label={t("nav.more", "More")}
          type="button"
        >
          <MoreHorizontal size={20} aria-hidden="true" />
          <span>{t("nav.more", "More")}</span>
        </button>
      </div>
    </nav>
  );
}
