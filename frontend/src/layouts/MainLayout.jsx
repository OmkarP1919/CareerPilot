import { useState, useCallback } from "react";
import { Outlet } from "react-router-dom";
import TopNav from "../components/TopNav";
import BottomNav from "../components/BottomNav";
import AccountMenu from "../components/AccountMenu";

export default function MainLayout() {
  const [sheetOpen, setSheetOpen] = useState(false);
  const toggleSheet = useCallback(() => setSheetOpen((p) => !p), []);
  const closeSheet = useCallback(() => setSheetOpen(false), []);

  return (
    <div className="app-layout">
      <TopNav />
      <main className="main-content">
        <Outlet />
      </main>
      <BottomNav onMoreClick={toggleSheet} />
      {sheetOpen && (
        <AccountMenu onClose={closeSheet} isMobile />
      )}
    </div>
  );
}
