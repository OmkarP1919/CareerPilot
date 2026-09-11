import { useState, useCallback } from "react";
import { Outlet } from "react-router-dom";
import TopNav from "../components/TopNav";
import BottomNav from "../components/BottomNav";
import Sidebar from "../components/Sidebar";
import AccountMenu from "../components/AccountMenu";

export default function MainLayout() {
  const [sheetOpen, setSheetOpen] = useState(false);
  const toggleSheet = useCallback(() => setSheetOpen((p) => !p), []);
  const closeSheet = useCallback(() => setSheetOpen(false), []);

  return (
    <div className="app-layout app-layout-with-sidebar">
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>
      <TopNav />
      <div className="app-shell-container">
        <Sidebar isOpen={false} onClose={() => {}} />
        <main className="main-content" id="main-content">
          <Outlet />
        </main>
      </div>
      <BottomNav onMoreClick={toggleSheet} />
      {sheetOpen && (
        <AccountMenu onClose={closeSheet} isMobile />
      )}
    </div>
  );
}
